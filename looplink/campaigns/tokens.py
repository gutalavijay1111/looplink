import secrets

TOKEN_BYTES = 9


def generate_campaign_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)
