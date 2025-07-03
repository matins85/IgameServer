import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .token import UntypedToken
from .exceptions import InvalidToken, TokenError
from django.contrib.auth.models import AnonymousUser
from .models import GameSession, GameParticipation
from .tasks import game_session_manager, end_session_and_create_new, update_user_stats_for_session


class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = 'game_room'

        # Authenticate user
        self.user = await self.get_user_from_token()
        if self.user is None or self.user.is_anonymous:
            await self.close()
            return

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

        # Send current session info
        session_data = await self.get_current_session()
        if session_data:
            await self.send(text_data=json.dumps({
                'type': 'session_info',
                'session': session_data
            }))

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')

        if message_type == 'join_session':
            await self.handle_join_session()
        elif message_type == 'select_number':
            await self.handle_select_number(data.get('number'))
        elif message_type == 'leave_session':
            await self.handle_leave_session()
        elif message_type == 'trigger_game_session_manager':
            await self.handle_game_session_manager()
        elif message_type == 'trigger_end_session':
            await self.handle_end_session_and_create_new(data.get('session_id'))
        elif message_type == 'trigger_update_user_stats':
            await self.handle_update_user_stats(data.get('session_id'), data.get('winning_number'))

    async def handle_join_session(self):
        """Handle user joining session"""
        result = await self.join_user_to_session()
        if result['success']:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'player_joined',
                    'username': self.user.username,
                    'player_count': result['player_count']
                }
            )

    async def handle_select_number(self, number):
        """Handle number selection"""
        if not number or not isinstance(number, int) or number < 1 or number > 10:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid number selection'
            }))
            return

        result = await self.select_number_for_user(number)
        await self.send(text_data=json.dumps({
            'type': 'number_selected',
            'success': result['success'],
            'selected_number': number if result['success'] else None,
            'message': result.get('message', '')
        }))

    # WebSocket event handlers
    async def session_countdown(self, event):
        """Send countdown update"""
        await self.send(text_data=json.dumps({
            'type': 'session_countdown',
            'time_left': event['time_left']
        }))

    async def session_ended(self, event):
        """Send session end notification"""
        await self.send(text_data=json.dumps({
            'type': 'session_ended',
            'winning_number': event['winning_number'],
            'winners': event['winners'],
            'is_winner': self.user.username in event['winners']
        }))

    async def session_started(self, event):
        """Send new session notification"""
        await self.send(text_data=json.dumps({
            'type': 'session_started',
            'session_id': str(event['session_id']),
            'start_time': event['start_time']
        }))

    async def player_joined(self, event):
        """Send player joined notification"""
        await self.send(text_data=json.dumps({
            'type': 'player_joined',
            'username': event['username'],
            'player_count': event['player_count']
        }))

    async def game_result(self, event):
        """Send game result"""
        await self.send(text_data=json.dumps({
            'type': 'game_result',
            'winning_number': event['winning_number'],
            'winners': event['winners'],
            'is_winner': self.user.username in event.get('winners', [])
        }))

    # Database operations
    @database_sync_to_async
    def get_user_from_token(self):
        """Authenticate user from WebSocket headers"""
        try:
            token = None
            for header_name, header_value in self.scope['headers']:
                if header_name == b'authorization':
                    token = header_value.decode().split(' ')[-1]
                    break

            if not token:
                return AnonymousUser()

            UntypedToken(token)
            return AnonymousUser()
        except (InvalidToken, TokenError):
            return AnonymousUser()

    @database_sync_to_async
    def get_current_session(self):
        """Get current active session data"""
        try:
            session = GameSession.objects.get_current_active_session()
            if session:
                return {
                    'id': str(session.session_id),
                    'time_remaining': session.time_remaining,
                    'player_count': session.player_count,
                    'is_active': session.is_active
                }
        except:
            pass
        return None

    @database_sync_to_async
    def join_user_to_session(self):
        """Add user to current session"""
        try:
            session = GameSession.objects.get_current_active_session()
            if not session:
                return {'success': False, 'message': 'No active session'}

            participation, created = GameParticipation.objects.get_or_create(
                user=self.user,
                session=session
            )

            if created:
                session.player_count += 1
                session.save()

            return {
                'success': True,
                'player_count': session.player_count,
                'already_joined': not created
            }
        except Exception as e:
            return {'success': False, 'message': str(e)}

    @database_sync_to_async
    def select_number_for_user(self, number):
        """Select number for user in current session"""
        try:
            session = GameSession.objects.get_current_active_session()
            if not session or not session.is_active:
                return {'success': False, 'message': 'No active session'}

            participation = GameParticipation.objects.get(
                user=self.user,
                session=session
            )
            participation.selected_number = number
            participation.save()

            return {'success': True}
        except GameParticipation.DoesNotExist:
            return {'success': False, 'message': 'Not joined to session'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    async def handle_game_session_manager(self):
        await database_sync_to_async(game_session_manager)()
        await self.send(text_data=json.dumps({'type': 'info', 'message': 'Game session manager triggered'}))

    async def handle_end_session_and_create_new(self, session_id):
        await database_sync_to_async(end_session_and_create_new)(session_id)
        await self.send(text_data=json.dumps({'type': 'info', 'message': 'End session and create new triggered'}))

    async def handle_update_user_stats(self, session_id, winning_number):
        await database_sync_to_async(update_user_stats_for_session)(session_id, winning_number)
        await self.send(text_data=json.dumps({'type': 'info', 'message': 'Update user stats triggered'}))
