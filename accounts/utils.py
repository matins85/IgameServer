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


def end_current_session():
    """End current active session and determine winners"""
    session = GameSession.objects.get_current_active_session()
    if not session:
        return None

    winning_number = session.winning_number
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


def game_session_manager():
    """Main function to manage game sessions - returns session info and time left"""
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    
    session = GameSession.objects.get_current_active_session()
    result = {}

    if session:
        time_remaining = session.time_remaining
        if time_remaining > 1:
            result['session'] = session
            result['time_left'] = time_remaining
        else:
            # End current session and create new one
            winning_number = session.winning_number
            session.end_session(winning_number)
            winners = list(
                session.participations.filter(
                    selected_number=winning_number
                ).values_list('user__username', flat=True)
            )
            participations = list(session.participations.values('user__username', 'selected_number', 'is_winner'))
            update_user_stats_for_session(session.id, winning_number)
            # Broadcast session ended to all clients
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                'game_room',
                {
                    'type': 'session_ended',
                    'winning_number': winning_number,
                    'winners': winners,
                    'participations': participations,
                }
            )
            new_session = create_new_session()
            result['session'] = new_session
            result['time_left'] = new_session.time_remaining
            result['ended_session_id'] = str(session.session_id)
            result['winning_number'] = winning_number
            result['winners'] = winners
    else:
        new_session = create_new_session()
        result['session'] = new_session
        result['time_left'] = new_session.time_remaining

    return result


def end_session_and_create_new(session_id):
    """End current session and create new one, return info for frontend to broadcast"""
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    try:
        session = GameSession.objects.get(id=session_id)
        if not session.is_active:
            return None  # Already ended
        winning_number = session.winning_number
        session.end_session(winning_number)
        winners = list(
            session.participations.filter(
                selected_number=winning_number
            ).values_list('user__username', flat=True)
        )
        # Update user stats
        update_user_stats_for_session(session.id, winning_number)
        # Optionally: broadcast game result via channel_layer if needed
        new_session = create_new_session()
        return {
            'ended_session_id': str(session.session_id),
            'winning_number': winning_number,
            'winners': winners,
            'new_session_id': str(new_session.session_id),
            'new_session_start_time': new_session.start_time.isoformat(),
        }
    except GameSession.DoesNotExist:
        return None


def update_user_stats_for_session(session_id, winning_number):
    """Update user statistics for a completed session"""
    try:
        session = GameSession.objects.get(id=session_id)
        # Update winner stats
        winner_participations = session.participations.filter(selected_number=winning_number)
        for participation in winner_participations:
            participation.is_winner = True
            participation.save()
            stats = get_or_create_user_stats(participation.user)
            stats.update_stats(is_winner=True)
        # Update loser stats
        loser_participations = session.participations.exclude(selected_number=winning_number)
        for participation in loser_participations:
            stats = get_or_create_user_stats(participation.user)
            stats.update_stats(is_winner=False)
    except GameSession.DoesNotExist:
        pass
