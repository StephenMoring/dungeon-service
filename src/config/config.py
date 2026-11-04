import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
ANTHROPIC_API_KEY = os.environ["DUNGEON_ANTHROPIC_API_KEY"]
DISCORD_CLIENT_ID = os.environ["DISCORD_CLIENT_ID"]
DISCORD_CLIENT_SECRET = os.environ["DISCORD_CLIENT_SECRET"]
DISCORD_REDIRECT_URI = os.environ["DISCORD_REDIRECT_URI"]
SECRET_KEY = os.environ["SECRET_KEY"]
VOYAGE_API_KEY = os.environ["VOYAGE_API_KEY"]
# The session cookie is Secure unless this is "false" (browsers accept Secure cookies
# on http://localhost, so local development does not need it).
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() != "false"
