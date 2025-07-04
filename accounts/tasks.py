from .models import GameSession
from .utils import create_new_session, generate_winning_number, game_session_manager, end_session_and_create_new, update_user_stats_for_session
import time

# The Celery tasks have been removed. Use the utility functions directly from utils.py.
