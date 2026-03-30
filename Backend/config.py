from pathlib import Path
import re

BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "Assets"
DB_PATH = BASE_DIR / "auth.db"

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_MIN_LENGTH = 8
SESSION_COOKIE_NAME = "codearena_session"
DEFAULT_SESSION_SECONDS = 60 * 60 * 24
REMEMBER_SESSION_SECONDS = 60 * 60 * 24 * 30
PBKDF2_ROUNDS = 240000

HTML_SHORTCUTS = {
    "/index.html",
    "/login.html",
    "/dashboard.html",
    "/leaderboard.html",
    "/play.html",
}

