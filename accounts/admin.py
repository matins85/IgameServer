from django.contrib import admin
from .models import User, GameSession, GameParticipation, UserGameStats


@admin.register(GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    list_display = [
        'session_id', 'start_time', 'end_time', 'winning_number', 
        'is_active', 'player_count', 'session_duration'
    ]
    list_filter = ['is_active', 'start_time', 'winning_number']
    search_fields = ['session_id']
    readonly_fields = ['session_id', 'created_at', 'updated_at', 'session_duration']
    ordering = ['-created_at']

    def session_duration(self, obj):
        if obj.end_time and obj.start_time:
            duration = obj.end_time - obj.start_time
            return f"{duration.total_seconds():.1f}s"
        return "Active" if obj.is_active else "N/A"
    session_duration.short_description = "Duration"


@admin.register(GameParticipation)
class GameParticipationAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'session_id_short', 'selected_number', 'is_winner', 'joined_at'
    ]
    list_filter = ['is_winner', 'selected_number', 'joined_at']
    search_fields = ['user__username', 'session__session_id']
    raw_id_fields = ['user', 'session']

    def session_id_short(self, obj):
        return str(obj.session.session_id)[:8] + "..."
    session_id_short.short_description = "Session ID"


@admin.register(UserGameStats)
class UserGameStatsAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'wins', 'games_played', 'win_rate_display', 
        'current_streak', 'best_streak', 'last_played'
    ]
    list_filter = ['last_played', 'current_streak']
    search_fields = ['user__username']
    readonly_fields = ['win_rate_display', 'created_at', 'updated_at']
    ordering = ['-wins', '-games_played']

    def win_rate_display(self, obj):
        return f"{obj.win_rate}%"
    win_rate_display.short_description = "Win Rate"


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'is_active', 'is_staff', 'date_joined']
    search_fields = ['username',]
    list_filter = ['is_active', 'is_staff']
    ordering = ['-date_joined']
