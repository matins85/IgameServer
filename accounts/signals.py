from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserGameStats


@receiver(post_save, sender=User)
def create_user_game_stats(sender, instance, created, **kwargs):
    """Create UserGameStats when a new user is created"""
    if created:
        UserGameStats.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_game_stats(sender, instance, **kwargs):
    """Save UserGameStats when user is saved"""
    if hasattr(instance, 'game_stats'):
        instance.game_stats.save()
        