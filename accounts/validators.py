from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_game_number(value):
    """Validate that the number is between 1 and 10"""
    if not isinstance(value, int) or value < 1 or value > 10:
        raise ValidationError(
            _('%(value)s is not a valid game number. Must be between 1 and 10.'),
            params={'value': value},
        )


def validate_username_game_rules(value):
    """Validate username according to game rules"""
    if len(value) < 3:
        raise ValidationError(
            _('Username must be at least 3 characters long.')
        )
    
    if len(value) > 50:
        raise ValidationError(
            _('Username must be no more than 50 characters long.')
        )
    
    # Add any other game-specific username rules here
    banned_words = ['admin', 'bot', 'system', 'moderator']
    if any(word in value.lower() for word in banned_words):
        raise ValidationError(
            _('Username contains forbidden words.')
        )
