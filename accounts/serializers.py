# Django Imports
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AbstractUser
from rest_framework import exceptions, serializers
from .jwtsetting import api_settings
from .token import RefreshToken, SlidingToken, UntypedToken
from .models import GameSession, GameParticipation, UserGameStats

auth_user: AbstractUser = get_user_model()
default_password = 'N$fnds123456'


class PasswordField(serializers.CharField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('style', {})
        kwargs['style']['input_type'] = 'password'
        kwargs['write_only'] = True

        super().__init__(*args, **kwargs)


class TokenSerializer(serializers.Serializer):
    username_field = auth_user.USERNAME_FIELD

    default_error_messages = {
        'no_active_account': _('User not found. Please register first.')
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields[self.username_field] = serializers.CharField()
        self.fields['password'] = default_password

    def validate(self, attrs):
        authenticate_kwargs = {
            self.username_field: attrs[self.username_field],
            'password': default_password,
        }
        self.user = authenticate(request=self.context, **authenticate_kwargs)
        if self.user is None or not self.user.is_active:
            raise exceptions.AuthenticationFailed(
                self.error_messages['no_active_account'],
                'no_active_account',
            )
        return {}

    @classmethod
    def get_token(cls, user):
        raise NotImplementedError('Must implement `get_token` method for `TokenObtainSerializer` subclasses')


class LoginSerializer(TokenSerializer):
    """ Serializer for Login Endpoint """

    @classmethod
    def get_token(cls, user):
        return RefreshToken.for_user(user)

    def validate(self, attrs):
        super().validate(attrs)
        token = self.get_token(self.user)
        user_uuid = self._kwargs.get('data').get('user_uuid')

        if user_uuid is None:
            pass
        else:
            self.user.user_uuid = user_uuid
            self.user.save()

        data = {
            'user_id': self.user.id,
            'is_staff': self.user.is_staff,
            'username': self.user.username,
            'is_active': self.user.is_active,
            'access_token': str(token.access_token),
            'user_uuid': self.user.user_uuid
        }
        return data


class TokenObtainSlidingSerializer(TokenSerializer):
    @classmethod
    def get_token(cls, user):
        return SlidingToken.for_user(user)

    def validate(self, attrs):
        data = super().validate(attrs)
        token = self.get_token(self.user)
        data['token'] = str(token)
        return data


class TokenRefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def validate(self, attrs):
        refresh = RefreshToken(attrs['refresh'])
        data = {'access': str(refresh.access_token)}
        if api_settings.ROTATE_REFRESH_TOKENS:
            if api_settings.BLACKLIST_AFTER_ROTATION:
                try:
                    # Attempt to blacklist the given refresh token
                    refresh.blacklist()
                except AttributeError:
                    # If blacklist app not installed, `blacklist` method will not be present
                    pass
            refresh.set_jti()
            refresh.set_exp()
            data['refresh'] = str(refresh)
        return data


class TokenRefreshSlidingSerializer(serializers.Serializer):
    token = serializers.CharField()

    def validate(self, attrs):
        token = SlidingToken(attrs['token'])
        # Check that the timestamp in the "refresh_exp" claim has not passed
        token.check_exp(api_settings.SLIDING_TOKEN_REFRESH_EXP_CLAIM)
        # Update the "exp" claim
        token.set_exp()

        return {'token': str(token)}


class TokenVerifySerializer(serializers.Serializer):
    token = serializers.CharField()

    def validate(self, attrs):
        UntypedToken(attrs['token'])
        return True


class CreateUserSerializer(serializers.ModelSerializer):
    """
        Serializer for create user Endpoint.
    """

    class Meta:
        model = auth_user
        fields = ['username', ]

    def save(self):
        password = default_password
        user = auth_user.objects.create(**self.validated_data)
        user.set_password(password)
        user.save()
        return user


class UserStatsSerializer(serializers.ModelSerializer):
    """Serializer for user game statistics"""
    username = serializers.CharField(source='user.username', read_only=True)
    win_rate = serializers.ReadOnlyField()

    class Meta:
        model = UserGameStats
        fields = [
            'username', 'wins', 'games_played', 'win_rate',
            'current_streak', 'best_streak', 'last_played'
        ]


class GameParticipationSerializer(serializers.ModelSerializer):
    """Serializer for game participation"""
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = GameParticipation
        fields = ['username', 'selected_number', 'is_winner', 'joined_at']


class GameSessionSerializer(serializers.ModelSerializer):
    """Serializer for game sessions"""
    participations = GameParticipationSerializer(many=True, read_only=True)
    time_remaining = serializers.ReadOnlyField()
    session_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = GameSession
        fields = [
            'id', 'session_id', 'start_time', 'end_time', 'winning_number',
            'is_active', 'player_count', 'time_remaining', 'participations'
        ]


class GameSessionDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for game sessions"""
    participations = GameParticipationSerializer(many=True, read_only=True)
    time_remaining = serializers.ReadOnlyField()

    class Meta:
        model = GameSession
        fields = '__all__'


class NumberSelectionSerializer(serializers.Serializer):
    """Serializer for number selection"""
    selected_number = serializers.IntegerField(min_value=1, max_value=10)

    def validate_selected_number(self, value):
        """Custom validation for selected number"""
        if not isinstance(value, int) or value < 1 or value > 10:
            raise serializers.ValidationError("Number must be between 1 and 10")
        return value


class LeaderboardSerializer(serializers.ModelSerializer):
    """Serializer for leaderboard data"""
    username = serializers.CharField(source='user.username')
    rank = serializers.IntegerField(read_only=True)

    class Meta:
        model = UserGameStats
        fields = ['rank', 'username', 'wins', 'games_played', 'win_rate', 'best_streak']
