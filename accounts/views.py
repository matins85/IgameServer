from django.http import HttpResponse
from rest_framework import generics
from rest_framework.generics import GenericAPIView, ListAPIView, RetrieveAPIView
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from .serializers import (CreateUserSerializer, LoginSerializer, TokenRefreshSerializer, )
from .jwtauth import AUTH_HEADER_TYPES
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.db.models import F
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import GameSession, GameParticipation, UserGameStats
from .serializers import (
    GameSessionSerializer, NumberSelectionSerializer,
    UserStatsSerializer, LeaderboardSerializer, GameSessionDetailSerializer
)
from .utils import get_or_create_user_stats

auth_user: AbstractUser = get_user_model()


class LoginView(generics.GenericAPIView):
    """ Login endpoint """

    permission_classes = []
    authentication_classes = []
    serializer_class = LoginSerializer

    www_authenticate_realm = 'api'

    def get_authenticate_header(self, request):
        return '{0} realm="{1}"'.format(
            AUTH_HEADER_TYPES[0],
            self.www_authenticate_realm,
        )

    def post(self, request, *args, **kwargs) -> Response:
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(data=serializer.validated_data, status=status.HTTP_200_OK)


class TokenRefreshView(LoginView):
    """
    Takes a refresh type JSON web token and returns an access type JSON web
    token if the refresh token is valid.
    """
    serializer_class = TokenRefreshSerializer


class RegisterUserView(GenericAPIView):
    """ Endpoint for create user """

    permission_classes = []
    authentication_classes = []
    queryset = auth_user.objects.all()
    serializer_class = CreateUserSerializer

    def post(self, request, *args, **kwargs) -> Response:
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(data={'detail': serializer.data}, status=status.HTTP_201_CREATED)


class CurrentSessionView(APIView):
    """Get current active game session"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        session = GameSession.objects.get_current_active_session()
        if not session:
            return Response(
                {'error': 'No active session found'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = GameSessionSerializer(session)
        return Response(serializer.data)


class JoinSessionView(APIView):
    """Join current active game session"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        session = GameSession.objects.get_current_active_session()
        if not session:
            return Response(
                {'error': 'No active session available'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if user already joined this session
        participation, created = GameParticipation.objects.get_or_create(
            user=request.user,
            session=session
        )

        if not created:
            return Response(
                {'error': 'Already joined this session'},
                status=status.HTTP_409_CONFLICT
            )

        # Update player count
        session.player_count = F('player_count') + 1
        session.save()
        session.refresh_from_db()

        # Broadcast player joined
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'game_room',
            {
                'type': 'player_joined',
                'username': request.user.username,
                'player_count': session.player_count
            }
        )

        serializer = GameSessionSerializer(session)
        return Response({'success': True, 'session': serializer.data})


class SelectNumberView(APIView):
    """Select number for current game session"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id=None):
        # Get session by UUID
        if session_id:
            session = get_object_or_404(GameSession, session_id=session_id)
        else:
            session = GameSession.objects.get_current_active_session()

        if not session or not session.is_active:
            return Response(
                {'error': 'Session not active'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if session has ended
        if session.time_remaining <= 0:
            return Response(
                {'error': 'Session has ended'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = NumberSelectionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Get or create participation
        try:
            participation = GameParticipation.objects.get(
                user=request.user,
                session=session
            )
        except GameParticipation.DoesNotExist:
            return Response(
                {'error': 'You must join the session first'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update selected number (allow changing until session ends)
        participation.selected_number = serializer.validated_data['selected_number']
        participation.save()

        return Response({
            'success': True,
            'selected_number': participation.selected_number
        })


class SessionStatusView(APIView):
    """Get status of a specific session"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, session_id):
        session = get_object_or_404(GameSession, session_id=session_id)
        serializer = GameSessionDetailSerializer(session)
        return Response(serializer.data)


class SessionHistoryView(ListAPIView):
    """Get user's game session history"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = GameSessionSerializer

    def get_queryset(self):
        return GameSession.objects.filter(
            participations__user=self.request.user
        ).order_by('-created_at')[:20]


class LeaderboardView(ListAPIView):
    """Get top 10 leaderboard"""
    serializer_class = LeaderboardSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = UserGameStats.objects.get_leaderboard(limit=10)
        # Add rank to each item
        for idx, stats in enumerate(queryset, 1):
            stats.rank = idx
        return queryset


class UserStatsView(RetrieveAPIView):
    """Get specific user's stats"""
    serializer_class = UserStatsSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'user_id'

    def get_object(self):
        user_id = self.kwargs['user_id']
        user = get_object_or_404(User, id=user_id)
        return get_or_create_user_stats(user)


class GameHistoryView(ListAPIView):
    """Get user's detailed game history"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = GameSessionDetailSerializer

    def get_queryset(self):
        return GameSession.objects.filter(
            participations__user=self.request.user,
            is_active=False
        ).order_by('-end_time')[:50]


def index(request):
    return HttpResponse('Welcome to Igame Server API Page')
