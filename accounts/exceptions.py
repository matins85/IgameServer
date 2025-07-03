from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions, status
from rest_framework.views import exception_handler


class TokenError(Exception):
    pass


class TokenBackendError(Exception):
    pass


class DetailDictMixin:
    def __init__(self, detail=None, code=None):
        """
        Builds a detail dictionary for the error to give more information to API
        users.
        """
        detail_dict = {"detail": self.default_detail, "code": self.default_code}

        if isinstance(detail, dict):
            detail_dict.update(detail)
        elif detail is not None:
            detail_dict["detail"] = detail

        if code is not None:
            detail_dict["code"] = code

        super().__init__(detail_dict)


class AuthenticationFailed(DetailDictMixin, exceptions.AuthenticationFailed):
    pass


class InvalidToken(AuthenticationFailed):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = _("Token is invalid or expired")
    default_code = "token_not_valid"


class GameLobbyException(Exception):
    """Base exception for game lobby"""
    pass


class SessionNotActiveException(GameLobbyException):
    """Raised when trying to interact with inactive session"""
    pass


class AlreadyJoinedException(GameLobbyException):
    """Raised when user tries to join session they're already in"""
    pass


class SessionFullException(GameLobbyException):
    """Raised when session is at maximum capacity"""
    pass


class InvalidNumberSelectionException(GameLobbyException):
    """Raised when invalid number is selected"""
    pass


def custom_exception_handler(exc, context):
    """Custom exception handler for game lobby"""
    response = exception_handler(exc, context)

    if response is not None:
        custom_response_data = {
            'error': True,
            'message': 'An error occurred',
            'details': response.data
        }

        if isinstance(exc, SessionNotActiveException):
            custom_response_data['message'] = 'No active game session available'
            custom_response_data['code'] = 'SESSION_NOT_ACTIVE'
        elif isinstance(exc, AlreadyJoinedException):
            custom_response_data['message'] = 'You have already joined this session'
            custom_response_data['code'] = 'ALREADY_JOINED'
        elif isinstance(exc, SessionFullException):
            custom_response_data['message'] = 'Session is full'
            custom_response_data['code'] = 'SESSION_FULL'
        elif isinstance(exc, InvalidNumberSelectionException):
            custom_response_data['message'] = 'Invalid number selection'
            custom_response_data['code'] = 'INVALID_NUMBER'

        response.data = custom_response_data

    return response
