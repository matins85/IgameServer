from django.apps import AppConfig


class GameLobbyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = 'Game Lobby Accounts'

    def ready(self):
        import accounts.signals
