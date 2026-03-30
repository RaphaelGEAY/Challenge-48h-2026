import argparse
import base64
import binascii
import hashlib
import hmac
import json
import mimetypes
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "Assets"
DB_PATH = BASE_DIR / "auth.db"

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_MIN_LENGTH = 8
SESSION_COOKIE_NAME = "codearena_session"
DEFAULT_SESSION_SECONDS = 60 * 60 * 24
REMEMBER_SESSION_SECONDS = 60 * 60 * 24 * 30
PBKDF2_ROUNDS = 240000

SESSIONS: Dict[str, Tuple[int, float]] = {}
SESSION_LOCK = threading.Lock()

HTML_SHORTCUTS = {
    "/index.html",
    "/login.html",
    "/dashboard.html",
    "/leaderboard.html",
    "/play.html",
}


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    salt_b64 = base64.b64encode(salt).decode("ascii")
    digest_b64 = base64.b64encode(digest).decode("ascii")
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${salt_b64}${digest_b64}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, rounds_raw, salt_b64, digest_b64 = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        rounds = int(rounds_raw)
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected_digest = base64.b64decode(digest_b64.encode("ascii"))
    except (ValueError, TypeError, binascii.Error):
        return False

    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return hmac.compare_digest(digest, expected_digest)


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


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuthRequestHandler(BaseHTTPRequestHandler):
    server_version = "CodeArenaAuth/1.0"

    def do_OPTIONS(self) -> None:
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        self.send_response(HTTPStatus.NO_CONTENT)
        self._write_cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_GET(self) -> None:
        cleanup_sessions()

        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/auth/me":
            self._handle_me()
            return

        if path == "/api/health":
            self._send_json(HTTPStatus.OK, {"ok": True, "status": "healthy"})
            return

        self._serve_static(path)

    def do_POST(self) -> None:
        cleanup_sessions()

        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/auth/register":
            self._handle_register()
            return

        if path == "/api/auth/login":
            self._handle_login()
            return

        if path == "/api/auth/logout":
            self._handle_logout()
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Route not found"})

    def _handle_register(self) -> None:
        body, error = self._read_json_body()
        if error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": error})
            return

        username = str(body.get("username", "")).strip()
        email = normalize_email(str(body.get("email", "")))
        password = str(body.get("password", ""))
        remember = bool(body.get("remember", False))

        if len(username) < 3:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "Le pseudo doit contenir au moins 3 caracteres."},
            )
            return

        if len(username) > 30:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "Le pseudo ne peut pas depasser 30 caracteres."},
            )
            return

        if not EMAIL_REGEX.match(email):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "Adresse email invalide."},
            )
            return

        if len(password) < PASSWORD_MIN_LENGTH:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {
                    "ok": False,
                    "error": f"Le mot de passe doit contenir au moins {PASSWORD_MIN_LENGTH} caracteres.",
                },
            )
            return

        password_hash = hash_password(password)

        try:
            with db_connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO users (username, email, password_hash, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (username, email, password_hash, utc_now_iso()),
                )
                conn.commit()
                last_row_id = cursor.lastrowid
                if last_row_id is None:
                    self._send_json(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        {"ok": False, "error": "Impossible de finaliser l'inscription."},
                    )
                    return
                user_id = last_row_id
        except sqlite3.IntegrityError:
            self._send_json(
                HTTPStatus.CONFLICT,
                {"ok": False, "error": "Un compte avec cet email existe deja."},
            )
            return

        ttl = REMEMBER_SESSION_SECONDS if remember else DEFAULT_SESSION_SECONDS
        token = create_session(user_id, ttl)

        self._send_json(
            HTTPStatus.CREATED,
            {
                "ok": True,
                "message": "Inscription reussie.",
                "user": {"id": user_id, "username": username, "email": email},
            },
            headers=[("Set-Cookie", self._build_session_cookie(token, ttl))],
        )

    def _handle_login(self) -> None:
        body, error = self._read_json_body()
        if error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": error})
            return

        email = normalize_email(str(body.get("email", "")))
        password = str(body.get("password", ""))
        remember = bool(body.get("remember", False))

        if not email or not password:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "Email et mot de passe obligatoires."},
            )
            return

        with db_connection() as conn:
            user = conn.execute(
                """
                SELECT id, username, email, password_hash
                FROM users
                WHERE email = ?
                """,
                (email,),
            ).fetchone()

        if not user or not verify_password(password, str(user["password_hash"])):
            self._send_json(
                HTTPStatus.UNAUTHORIZED,
                {"ok": False, "error": "Email ou mot de passe invalide."},
            )
            return

        ttl = REMEMBER_SESSION_SECONDS if remember else DEFAULT_SESSION_SECONDS
        token = create_session(int(user["id"]), ttl)

        self._send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "message": "Connexion reussie.",
                "user": {
                    "id": int(user["id"]),
                    "username": str(user["username"]),
                    "email": str(user["email"]),
                },
            },
            headers=[("Set-Cookie", self._build_session_cookie(token, ttl))],
        )

    def _handle_me(self) -> None:
        token = self._session_token_from_cookie()
        user_id = get_session_user_id(token)

        if not user_id:
            self._send_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "Non authentifie."})
            return

        with db_connection() as conn:
            user = conn.execute(
                """
                SELECT id, username, email, created_at
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()

        if not user:
            destroy_session(token)
            self._send_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "Session invalide."})
            return

        self._send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "user": {
                    "id": int(user["id"]),
                    "username": str(user["username"]),
                    "email": str(user["email"]),
                    "created_at": str(user["created_at"]),
                },
            },
        )

    def _handle_logout(self) -> None:
        token = self._session_token_from_cookie()
        destroy_session(token)

        self._send_json(
            HTTPStatus.OK,
            {"ok": True, "message": "Deconnexion reussie."},
            headers=[("Set-Cookie", self._build_cleared_session_cookie())],
        )

    def _serve_static(self, path: str) -> None:
        if path == "/":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/Assets/html/index.html")
            self.end_headers()
            return

        requested = unquote(path)

        if requested.startswith("/Assets/"):
            target = (BASE_DIR / requested.lstrip("/")).resolve()
        elif requested in HTML_SHORTCUTS:
            target = (ASSETS_DIR / "html" / requested.lstrip("/")).resolve()
        else:
            self._send_text(HTTPStatus.NOT_FOUND, "Not Found")
            return

        try:
            target.relative_to(BASE_DIR.resolve())
        except ValueError:
            self._send_text(HTTPStatus.FORBIDDEN, "Forbidden")
            return

        if not target.is_file():
            self._send_text(HTTPStatus.NOT_FOUND, "Not Found")
            return

        content = target.read_bytes()
        content_type, _ = mimetypes.guess_type(str(target))
        if not content_type:
            content_type = "application/octet-stream"

        if content_type.startswith("text/") or content_type in {
            "application/javascript",
            "application/json",
            "image/svg+xml",
        }:
            content_type = f"{content_type}; charset=utf-8"

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _read_json_body(self) -> Tuple[Dict[str, Any], Optional[str]]:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            return {}, "Corps de requete manquant."

        try:
            length = int(raw_length)
        except ValueError:
            return {}, "En-tete Content-Length invalide."

        if length <= 0:
            return {}, "Corps de requete manquant."

        if length > 1_000_000:
            return {}, "Corps de requete trop volumineux."

        raw_body = self.rfile.read(length)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}, "JSON invalide."

        if not isinstance(payload, dict):
            return {}, "Le JSON doit etre un objet."

        return payload, None

    def _send_json(
        self,
        status: HTTPStatus,
        payload: Dict[str, Any],
        headers: Optional[List[Tuple[str, str]]] = None,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")

        self.send_response(status)
        self._write_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))

        if headers:
            for key, value in headers:
                self.send_header(key, value)

        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, status: HTTPStatus, body: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _write_cors_headers(self) -> None:
        origin = self.headers.get("Origin")

        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        else:
            self.send_header("Access-Control-Allow-Origin", "*")

        self.send_header("Access-Control-Allow-Credentials", "true")

    def _session_token_from_cookie(self) -> Optional[str]:
        raw_cookie = self.headers.get("Cookie")
        if not raw_cookie:
            return None

        cookie = SimpleCookie()
        cookie.load(raw_cookie)

        token = cookie.get(SESSION_COOKIE_NAME)
        if not token:
            return None

        return str(token.value)

    def _build_session_cookie(self, token: str, max_age: int) -> str:
        cookie = SimpleCookie()
        cookie[SESSION_COOKIE_NAME] = token
        morsel = cookie[SESSION_COOKIE_NAME]
        morsel["path"] = "/"
        morsel["httponly"] = ""
        morsel["samesite"] = "Lax"
        morsel["max-age"] = str(max_age)
        return morsel.OutputString()

    def _build_cleared_session_cookie(self) -> str:
        cookie = SimpleCookie()
        cookie[SESSION_COOKIE_NAME] = ""
        morsel = cookie[SESSION_COOKIE_NAME]
        morsel["path"] = "/"
        morsel["httponly"] = ""
        morsel["samesite"] = "Lax"
        morsel["expires"] = "Thu, 01 Jan 1970 00:00:00 GMT"
        morsel["max-age"] = "0"
        return morsel.OutputString()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CodeArena auth backend")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    init_db()

    server = ThreadingHTTPServer((args.host, args.port), AuthRequestHandler)
    print(f"Server listening on http://{args.host}:{args.port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
