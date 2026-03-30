import secrets
import threading
import time
from typing import Dict, Optional, Tuple

SESSIONS: Dict[str, Tuple[int, float]] = {}
SESSION_LOCK = threading.Lock()


def create_session(user_id: int, ttl_seconds: int) -> str:
    token = secrets.token_urlsafe(48)
    expires_at = time.time() + ttl_seconds
    with SESSION_LOCK:
        SESSIONS[token] = (user_id, expires_at)
    return token


def get_session_user_id(token: Optional[str]) -> Optional[int]:
    if not token:
        return None

    with SESSION_LOCK:
        session_data = SESSIONS.get(token)
        if not session_data:
            return None

        user_id, expires_at = session_data
        if expires_at <= time.time():
            del SESSIONS[token]
            return None

        return user_id


def destroy_session(token: Optional[str]) -> None:
    if not token:
        return
    with SESSION_LOCK:
        SESSIONS.pop(token, None)


def cleanup_sessions() -> None:
    now = time.time()
    with SESSION_LOCK:
        expired_tokens = [token for token, (_, expires_at) in SESSIONS.items() if expires_at <= now]
        for token in expired_tokens:
            del SESSIONS[token]

