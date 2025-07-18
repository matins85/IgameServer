from .backend import TokenBackend
from .jwtsetting import api_settings

token_backend = TokenBackend(
    api_settings.ALGORITHM,
    api_settings.SIGNING_KEY,
    api_settings.VERIFYING_KEY,
    api_settings.AUDIENCE,
    api_settings.ISSUER,
    api_settings.JWK_URL,
    api_settings.LEEWAY,
)
