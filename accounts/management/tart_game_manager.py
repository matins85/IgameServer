from django.core.management.base import BaseCommand
import time
import threading
from accounts.tasks import game_session_manager


class Command(BaseCommand):
    help = 'Start the game session manager'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=1,
            help='Interval in seconds between checks (default: 1)'
        )

    def handle(self, *args, **options):
        interval = options['interval']
        self.stdout.write(
            self.style.SUCCESS(f'Starting game session manager (interval: {interval}s)')
        )

        def run_manager():
            while True:
                try:
                    game_session_manager()
                    time.sleep(interval)
                except KeyboardInterrupt:
                    self.stdout.write(self.style.WARNING('Stopping game manager...'))
                    break
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error in game manager: {e}')
                    )
                    time.sleep(interval)

        # Run in separate thread to allow for graceful shutdown
        manager_thread = threading.Thread(target=run_manager)
        manager_thread.daemon = True
        manager_thread.start()

        try:
            manager_thread.join()
        except KeyboardInterrupt:
            self.stdout.write(self.style.SUCCESS('Game manager stopped'))
