"""Autenticación por token: un token por consumidor, leído de variables de entorno."""

import hmac
import os

CONSUMER_TOKENS = {"portal": "PORTAL_TOKEN", "subsidios": "SUBSIDIOS_TOKEN", "mobile": "MOBILE_TOKEN"}
READ_ONLY = {"mobile"}


def consumer_for(authorization):
    """Devuelve el consumidor dueño del token Bearer, o None si no es válido."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization[7:].strip()
    for consumer, variable in CONSUMER_TOKENS.items():
        expected = os.environ.get(variable, "")
        if expected and hmac.compare_digest(token.encode(), expected.encode()):
            return consumer
    return None


def can_write(consumer):
    return consumer not in READ_ONLY
