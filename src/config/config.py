import os
from dotenv import load_dotenv

load_dotenv()


def require_secret_key(key: str) -> str:
    """SECRET_KEY signs sessions and character previews (HS256). A short key can be
    brute-forced, which would let anyone sign in as any player, so refuse to start."""
    if len(key.encode()) < 32:
        raise RuntimeError(
            "SECRET_KEY must be at least 32 bytes. Generate one with: "
            "python3 -c 'import secrets; print(secrets.token_hex(32))'"
        )
    return key


DATABASE_URL = os.environ["DATABASE_URL"]
ANTHROPIC_API_KEY = os.environ["DUNGEON_ANTHROPIC_API_KEY"]
DISCORD_CLIENT_ID = os.environ["DISCORD_CLIENT_ID"]
DISCORD_CLIENT_SECRET = os.environ["DISCORD_CLIENT_SECRET"]
DISCORD_REDIRECT_URI = os.environ["DISCORD_REDIRECT_URI"]
SECRET_KEY = require_secret_key(os.environ["SECRET_KEY"])
VOYAGE_API_KEY = os.environ["VOYAGE_API_KEY"]
# The session cookie is Secure unless this is "false" (browsers accept Secure cookies
# on http://localhost, so local development does not need it).
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() != "false"
