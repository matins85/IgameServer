import random
from calendar import timegm
from datetime import datetime
from django.conf import settings
from django.utils.functional import lazy
from django.utils.timezone import is_naive, make_aware, utc
from .models import UserGameStats, GameSession


def make_utc(dt):
    if settings.USE_TZ and is_naive(dt):
        return make_aware(dt, timezone=utc)
    return dt


def aware_utcnow():
    return make_utc(datetime.utcnow())


def datetime_to_epoch(dt):
    return timegm(dt.utctimetuple())


def datetime_from_epoch(ts):
    return make_utc(datetime.utcfromtimestamp(ts))


def format_lazy(s, *args, **kwargs):
    return s.format(*args, **kwargs)


format_lazy = lazy(format_lazy, str)


def get_or_create_user_stats(user):
    """Get or create user game statistics"""
    stats, created = UserGameStats.objects.get_or_create(user=user)
    return stats


def generate_winning_number():
    """Generate random winning number between 1-10"""
    return random.randint(1, 10)


def end_current_session():
    """End current active session and determine winners"""
    session = GameSession.objects.get_current_active_session()
    if not session:
        return None

    winning_number = generate_winning_number()
    session.end_session(winning_number)

    # Determine winners and update stats
    participations = session.participations.filter(selected_number=winning_number)

    for participation in participations:
        participation.is_winner = True
        participation.save()

        # Update user stats
        stats = get_or_create_user_stats(participation.user)
        stats.update_stats(is_winner=True)

    # Update losers
    losing_participations = session.participations.exclude(selected_number=winning_number)
    for participation in losing_participations:
        stats = get_or_create_user_stats(participation.user)
        stats.update_stats(is_winner=False)

    return session, participations


def create_new_session():
    """Create a new game session"""
    return GameSession.objects.create_new_session()
