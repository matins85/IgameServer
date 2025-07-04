import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .token import UntypedToken
from .exceptions import InvalidToken, TokenError
from django.contrib.auth.models import AnonymousUser
from .models import GameSession, GameParticipation
from .utils import game_session_manager, end_session_and_create_new, update_user_stats_for_session
from django.contrib.auth import get_user_model
from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


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
            # Parse request_details from the incoming message
            number = data.get('number')
            request_details = data.get('request_details', False)
            await self.handle_select_number(number, request_details)
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

    async def handle_select_number(self, number, request_details=False):
        """Handle number selection"""
        if not number or not isinstance(number, int) or number < 1 or number > 10:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid number selection'
            }))
            return

        # Always get the current session
        session = await database_sync_to_async(GameSession.objects.get_current_active_session)()
        if not session:
            await self.send(text_data=json.dumps({'type': 'error', 'message': 'No active session'}))
            return

        # Helper to get or create participation and set selected_number and is_winner
        @sync_to_async
        def get_or_create_participation(user, session, number):
            from .models import GameParticipation
            winning_number = session.winning_number
            is_winner = bool(winning_number and number == winning_number)
            participation, created = GameParticipation.objects.get_or_create(
                user=user,
                session=session,
                defaults={
                    'selected_number': number,
                    'is_winner': is_winner
                }
            )
            if created:
                session.player_count += 1
                session.save()
            else:
                participation.selected_number = number
                participation.is_winner = is_winner
                participation.save()
            return participation, created

        # Ensure the user is a participant and set their number and is_winner
        participation, created = await get_or_create_participation(self.user, session, number)
        if created:
            # Broadcast updated player count
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'player_joined',
                    'username': self.user.username,
                    'player_count': session.player_count
                }
            )

        # Helper to get participations
        @sync_to_async
        def get_participations(session):
            return list(session.participations.values('user__username', 'selected_number', 'is_winner'))

        # Helper to refresh session from db
        @sync_to_async
        def refresh_session(session):
            session.refresh_from_db()
            return session

        if not session.is_active or session.time_remaining <= 0 or request_details:
            winning_number = session.winning_number
            participations = await get_participations(session)
            winners = [p['user__username'] for p in participations if p['is_winner']]
            your_participation = next((p for p in participations if p['user__username'] == self.user.username), None)
            await self.send(text_data=json.dumps({
                'type': 'session_result',
                'winning_number': winning_number,
                'participations': participations,
                'winners': winners,
                'your_participation': your_participation,
            }))
            return
    

        result = await self.select_number_for_user(number)
        # After selection, return updated participations and session info
        session = await refresh_session(session)
        participations = await get_participations(session)
        winners = [p['user__username'] for p in participations if p['is_winner']]
        your_participation = next((p for p in participations if p['user__username'] == self.user.username), None)
        print(f"your_participation: {your_participation}")
        await self.send(text_data=json.dumps({
            'type': 'number_selected',
            'success': result['success'],
            'selected_number': number if result['success'] else None,
            'participations': participations,
            'winners': winners,
            'your_participation': your_participation,
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
        await self.send(text_data=json.dumps({
            'type': 'session_ended',
            'winning_number': event['winning_number'],
            'winners': event['winners'],
            'participations': event.get('participations', []),
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

    async def session_result(self, event):
        await self.send(text_data=json.dumps({
            'type': 'session_result',
            'winning_number': event['winning_number'],
            'winners': event['winners'],
            'participations': event.get('participations', []),
            'your_participation': event.get('your_participation'),
        }))

    # Database operations
    @database_sync_to_async
    def get_user_from_token(self):
        """Authenticate user from WebSocket headers or query string and return the actual user object"""
        try:
            token = None
            # Try headers first
            for header_name, header_value in self.scope['headers']:
                if header_name == b'authorization':
                    token = header_value.decode().split(' ')[-1]
                    break
            # Fallback: try query string
            if not token:
                query_string = self.scope.get('query_string', b'').decode()
                from urllib.parse import parse_qs
                params = parse_qs(query_string)
                token = params.get('token', [None])[0]
            if not token:
                return AnonymousUser()
            validated_token = UntypedToken(token)
            user_id = validated_token['user_id']  # Adjust this if your claim is different
            User = get_user_model()
            user = User.objects.get(id=user_id)
            return user
        except (InvalidToken, TokenError, KeyError, User.DoesNotExist):
            return AnonymousUser()

    @database_sync_to_async
    def get_current_session(self):
        """Get current active session data, including total users joined and user's total wins"""
        try:
            session = GameSession.objects.get_current_active_session()
            if session:
                # Count total users joined in this session
                total_users_joined = session.participations.count()
                # Get total wins for this user
                user_wins = 0
                if hasattr(self, 'user') and self.user and not self.user.is_anonymous:
                    if hasattr(self.user, 'game_stats'):
                        user_wins = self.user.game_stats.wins
                return {
                    'id': str(session.session_id),
                    'time_remaining': session.time_remaining,
                    'player_count': session.player_count,
                    'is_active': session.is_active,
                    'total_users_joined': total_users_joined,
                    'user_total_wins': user_wins
                }
        except Exception:
            pass
        return None

    @database_sync_to_async
    def join_user_to_session(self):
        """Add user to current session"""
        try:
            session = GameSession.objects.get_current_active_session()
            if not session:
                return {'success': False, 'message': 'No active session'}

            return {
                'success': True,
                'player_count': session.player_count,
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

            winning_number = session.winning_number
            is_winner = bool(winning_number and number == winning_number)
            participation, _ = GameParticipation.objects.get_or_create(
                user=self.user,
                session=session,
                defaults={
                    'selected_number': number,
                    'is_winner': is_winner
                }
            )
            participation.selected_number = number
            participation.is_winner = is_winner
            participation.save()

            return {'success': True}
        except GameParticipation.DoesNotExist:
            return {'success': False, 'message': 'Not joined to session'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    async def handle_game_session_manager(self):
        result = await database_sync_to_async(game_session_manager)()
        await self.send(text_data=json.dumps({'type': 'game_session_manager_result', 'result': self.serialize_session_manager_result(result)}))

    async def handle_end_session_and_create_new(self, session_id):
        result = await database_sync_to_async(end_session_and_create_new)(session_id)
        await self.send(text_data=json.dumps({'type': 'end_session_and_create_new_result', 'result': result}))

    async def handle_update_user_stats(self, session_id, winning_number):
        await database_sync_to_async(update_user_stats_for_session)(session_id, winning_number)
        await self.send(text_data=json.dumps({'type': 'update_user_stats_result', 'success': True}))

    def serialize_session_manager_result(self, result):
        # Helper to serialize the session manager result for frontend
        if not result:
            return None
        session = result.get('session')
        return {
            'session_id': str(session.session_id) if session else None,
            'time_left': result.get('time_left'),
            'is_active': getattr(session, 'is_active', None) if session else None,
            'player_count': getattr(session, 'player_count', None) if session else None,
        }
