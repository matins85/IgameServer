from django.contrib.auth.models import AbstractUser
from django.db import models
from .managers import UserManager
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid
from django.conf import settings


class User(AbstractUser):
    username = models.CharField(max_length=50, unique=True)
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []
    objects = UserManager()
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_superuser = models.BooleanField(default=False)


class GameSession(models.Model):
    """Model for game sessions"""
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    winning_number = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    is_active = models.BooleanField(default=True)
    player_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'game_sessions'
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['created_at']),
            models.Index(fields=['session_id']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Session {self.session_id} - {'Active' if self.is_active else 'Ended'}"

    @property
    def time_remaining(self):
        """Calculate remaining time in seconds"""
        if not self.is_active or self.end_time:
            return 0
        elapsed = timezone.now() - self.start_time
        remaining = settings.GAME_SESSION_DURATION - elapsed.total_seconds()
        return max(0, int(remaining))

    def end_session(self, winning_number):
        """End the session and set winning number"""
        self.is_active = False
        self.end_time = timezone.now()
        self.winning_number = winning_number
        self.save()


class GameParticipation(models.Model):
    """Model for tracking user participation in game sessions"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='game_participations')
    session = models.ForeignKey(GameSession, on_delete=models.CASCADE, related_name='participations')
    selected_number = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    is_winner = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'game_participations'
        unique_together = ['user', 'session']
        indexes = [
            models.Index(fields=['user', 'session']),
            models.Index(fields=['is_winner']),
            models.Index(fields=['joined_at']),
        ]

    def __str__(self):
        return f"{self.user.username} in {self.session.session_id}"


class UserGameStats(models.Model):
    """Extended user statistics for games"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='game_stats')
    wins = models.IntegerField(default=0)
    games_played = models.IntegerField(default=0)
    current_streak = models.IntegerField(default=0)
    best_streak = models.IntegerField(default=0)
    last_played = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_game_stats'
        indexes = [
            models.Index(fields=['wins']),
            models.Index(fields=['games_played']),
            models.Index(fields=['current_streak']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.wins}W/{self.games_played}G"

    @property
    def win_rate(self):
        """Calculate win rate percentage"""
        if self.games_played == 0:
            return 0
        return round((self.wins / self.games_played) * 100, 2)

    def update_stats(self, is_winner):
        """Update user statistics after a game"""
        self.games_played += 1
        self.last_played = timezone.now()
        
        if is_winner:
            self.wins += 1
            self.current_streak += 1
            if self.current_streak > self.best_streak:
                self.best_streak = self.current_streak
        else:
            self.current_streak = 0
        
        self.save()
