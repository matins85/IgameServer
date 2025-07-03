from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import GameSession
from .utils import create_new_session, generate_winning_number
import time


@shared_task
def game_session_manager():
    """Main task to manage game sessions - run every second"""
    channel_layer = get_channel_layer()
    
    # Get current active session
    session = GameSession.objects.get_current_active_session()
    
    if session:
        time_remaining = session.time_remaining
        
        # Send countdown updates
        if time_remaining > 0:
            async_to_sync(channel_layer.group_send)(
                'game_room',
                {
                    'type': 'session_countdown',
                    'time_left': time_remaining
                }
            )
        
        # End session when time is up
        if time_remaining <= 0:
            end_session_and_create_new.delay(session.id)
    
    else:
        # No active session, create one
        new_session = create_new_session()
        async_to_sync(channel_layer.group_send)(
            'game_room',
            {
                'type': 'session_started',
                'session_id': new_session.session_id,
                'start_time': new_session.start_time.isoformat()
            }
        )


@shared_task
def end_session_and_create_new(session_id):
    """End current session and create new one"""
    try:
        session = GameSession.objects.get(id=session_id)
        if not session.is_active:
            return  # Already ended
        
        # Generate winning number and end session
        winning_number = generate_winning_number()
        session.end_session(winning_number)
        
        # Get winners
        winners = list(
            session.participations.filter(
                selected_number=winning_number
            ).values_list('user__username', flat=True)
        )
        
        # Update user stats
        update_user_stats_for_session.delay(session.id, winning_number)
        
        # Broadcast game result
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'game_room',
            {
                'type': 'game_result',
                'winning_number': winning_number,
                'winners': winners,
                'session_id': str(session.session_id)
            }
        )
        
        # Wait 3 seconds then create new session
        time.sleep(3)
        
        new_session = create_new_session()
        async_to_sync(channel_layer.group_send)(
            'game_room',
            {
                'type': 'session_started',
                'session_id': new_session.session_id,
                'start_time': new_session.start_time.isoformat()
            }
        )
        
    except GameSession.DoesNotExist:
        pass


@shared_task
def update_user_stats_for_session(session_id, winning_number):
    """Update user statistics for a completed session"""
    from .utils import get_or_create_user_stats
    
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
