from django.urls import path
from .views import (
    CurrentSessionView, JoinSessionView, SelectNumberView,
    SessionStatusView, SessionHistoryView,
    LeaderboardView, UserStatsView, GameHistoryView, LoginView, RegisterUserView
)

urlpatterns = [
    # Auth endpoints
    path('login-token/', LoginView.as_view(), name='login-token'),
    path('create-user/', RegisterUserView.as_view(), name='create-user'),
    
    # Game session endpoints
    path('sessions/current/', CurrentSessionView.as_view(), name='current_session'),
    path('sessions/join/', JoinSessionView.as_view(), name='join_session'),
    path('sessions/select-number/', SelectNumberView.as_view(), name='select_number'),
    path('sessions/<uuid:session_id>/select-number/', SelectNumberView.as_view(), name='select_number_by_id'),
    path('sessions/<uuid:session_id>/status/', SessionStatusView.as_view(), name='session_status'),
    path('sessions/history/', SessionHistoryView.as_view(), name='session_history'),
    
    # User and leaderboard endpoints
    path('users/<int:user_id>/stats/', UserStatsView.as_view(), name='user_stats'),
    path('users/game-history/', GameHistoryView.as_view(), name='game_history'),
    path('leaderboard/top10/', LeaderboardView.as_view(), name='leaderboard'),
]
