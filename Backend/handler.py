import ast
import json
import mimetypes
import sqlite3
from datetime import datetime, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from .config import (
    ASSETS_DIR,
    BASE_DIR,
    DEFAULT_SESSION_SECONDS,
    HTML_SHORTCUTS,
    PASSWORD_MIN_LENGTH,
    SESSION_COOKIE_NAME,
)
from .database import db_connection
from .security import hash_password, is_valid_email, normalize_email, verify_password
from .sessions import cleanup_sessions, create_session, destroy_session, get_session_user_id
from Game.storage import load_game_catalog as game_load_catalog
from Game.storage import resolve_level_key as game_resolve_level_key
from Game.tester import tester

SAFE_EXEC_BUILTINS: Dict[str, Any] = {
    "range": range,
    "len": len,
    "enumerate": enumerate,
    "min": min,
    "max": max,
    "abs": abs,
    "sum": sum,
    "int": int,
    "str": str,
    "print": print,
}

BANNED_CALLS = {"open", "exec", "eval", "compile", "__import__", "input"}
BANNED_MODULES = {"os", "sys", "subprocess", "pathlib", "shutil", "socket"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def is_valid_profile_name(value: str) -> bool:
    trimmed = value.strip()
    return 2 <= len(trimmed) <= 40


def validate_game_code(code: str) -> None:
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        raise ValueError(f"Erreur de syntaxe: {exc.msg} (line {exc.lineno})") from exc

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ValueError("Les imports ne sont pas autorises.")

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in BANNED_CALLS:
            raise ValueError(f"Appel interdit: {node.func.id}")

        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in BANNED_MODULES:
            raise ValueError(f"Module interdit: {node.value.id}")


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
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path == "/api/auth/me":
            self._handle_me()
            return

        if path == "/api/game/levels":
            self._handle_game_levels()
            return

        if path == "/api/game/maze":
            self._handle_game_maze()
            return

        if path == "/api/game/code":
            self._handle_game_code()
            return

        if path == "/api/dashboard/me":
            self._handle_dashboard_me()
            return

        if path == "/api/health":
            self._send_json(HTTPStatus.OK, {"ok": True, "status": "healthy"})
            return

        self._serve_static(path)

    def do_POST(self) -> None:
        cleanup_sessions()
        path = urlparse(self.path).path

        if path == "/api/auth/register":
            self._handle_register()
            return

        if path == "/api/auth/login":
            self._handle_login()
            return

        if path == "/api/auth/logout":
            self._handle_logout()
            return

        if path == "/api/attempts":
            self._handle_create_attempt()
            return

        if path == "/api/account/update":
            self._handle_account_update()
            return

        if path == "/api/game/run":
            self._handle_game_run()
            return

        if path == "/api/game/submit":
            self._handle_game_submit()
            return

        if path == "/api/game/code/save":
            self._handle_game_save_code()
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Route not found"})

    def _handle_register(self) -> None:
        body, error = self._read_json_body()
        if error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": error})
            return

        username = str(body.get("username", "")).strip()
        first_name = str(body.get("first_name", "")).strip()
        last_name = str(body.get("last_name", "")).strip()
        email = normalize_email(str(body.get("email", "")))
        password = str(body.get("password", ""))

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

        if not is_valid_profile_name(first_name):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "Le prenom doit contenir entre 2 et 40 caracteres."},
            )
            return

        if not is_valid_profile_name(last_name):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "Le nom doit contenir entre 2 et 40 caracteres."},
            )
            return

        if not is_valid_email(email):
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
                    INSERT INTO users (username, first_name, last_name, email, password_hash, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (username, first_name, last_name, email, password_hash, utc_now_iso()),
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

        ttl = DEFAULT_SESSION_SECONDS
        token = create_session(user_id, ttl)

        self._send_json(
            HTTPStatus.CREATED,
            {
                "ok": True,
                "message": "Inscription reussie.",
                "user": {
                    "id": user_id,
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                },
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

        if not email or not password:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "Email et mot de passe obligatoires."},
            )
            return

        with db_connection() as conn:
            user = conn.execute(
                """
                SELECT id, username, first_name, last_name, email, password_hash
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

        ttl = DEFAULT_SESSION_SECONDS
        token = create_session(int(user["id"]), ttl)

        self._send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "message": "Connexion reussie.",
                "user": {
                    "id": int(user["id"]),
                    "username": str(user["username"]),
                    "first_name": str(user["first_name"]),
                    "last_name": str(user["last_name"]),
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
                SELECT id, username, first_name, last_name, email, created_at
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
                    "first_name": str(user["first_name"]),
                    "last_name": str(user["last_name"]),
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

    def _handle_account_update(self) -> None:
        user_id = self._require_user_id()
        if user_id is None:
            return

        body, error = self._read_json_body()
        if error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": error})
            return

        username = str(body.get("username", "")).strip()
        first_name = str(body.get("first_name", "")).strip()
        last_name = str(body.get("last_name", "")).strip()
        email = normalize_email(str(body.get("email", "")))
        current_password = str(body.get("current_password", ""))
        new_password = str(body.get("new_password", ""))

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

        if not is_valid_profile_name(first_name):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "Le prenom doit contenir entre 2 et 40 caracteres."},
            )
            return

        if not is_valid_profile_name(last_name):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "Le nom doit contenir entre 2 et 40 caracteres."},
            )
            return

        if not is_valid_email(email):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "Adresse email invalide."},
            )
            return

        with db_connection() as conn:
            user = conn.execute(
                "SELECT id, username, first_name, last_name, email, password_hash, created_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()

            if not user:
                self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Utilisateur introuvable."})
                return

            updates: Dict[str, Any] = {}

            if username != str(user["username"]):
                updates["username"] = username

            if first_name != str(user["first_name"]):
                updates["first_name"] = first_name

            if last_name != str(user["last_name"]):
                updates["last_name"] = last_name

            if email != str(user["email"]):
                updates["email"] = email

            if new_password:
                if len(new_password) < PASSWORD_MIN_LENGTH:
                    self._send_json(
                        HTTPStatus.BAD_REQUEST,
                        {
                            "ok": False,
                            "error": f"Le mot de passe doit contenir au moins {PASSWORD_MIN_LENGTH} caracteres.",
                        },
                    )
                    return

                if not current_password:
                    self._send_json(
                        HTTPStatus.BAD_REQUEST,
                        {"ok": False, "error": "Mot de passe actuel requis pour le changement."},
                    )
                    return

                if not verify_password(current_password, str(user["password_hash"])):
                    self._send_json(
                        HTTPStatus.UNAUTHORIZED,
                        {"ok": False, "error": "Mot de passe actuel invalide."},
                    )
                    return

                updates["password_hash"] = hash_password(new_password)

            if not updates:
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "message": "Aucune modification detectee.",
                        "user": {
                            "id": int(user["id"]),
                            "username": str(user["username"]),
                            "first_name": str(user["first_name"]),
                            "last_name": str(user["last_name"]),
                            "email": str(user["email"]),
                            "created_at": str(user["created_at"]),
                        },
                    },
                )
                return

            set_clauses: List[str] = []
            values: List[Any] = []
            if "username" in updates:
                set_clauses.append("username = ?")
                values.append(updates["username"])
            if "first_name" in updates:
                set_clauses.append("first_name = ?")
                values.append(updates["first_name"])
            if "last_name" in updates:
                set_clauses.append("last_name = ?")
                values.append(updates["last_name"])
            if "email" in updates:
                set_clauses.append("email = ?")
                values.append(updates["email"])
            if "password_hash" in updates:
                set_clauses.append("password_hash = ?")
                values.append(updates["password_hash"])

            values.append(user_id)

            try:
                conn.execute(
                    f"UPDATE users SET {', '.join(set_clauses)} WHERE id = ?",
                    values,
                )
                conn.commit()
            except sqlite3.IntegrityError:
                self._send_json(
                    HTTPStatus.CONFLICT,
                    {"ok": False, "error": "Un compte avec cet email existe deja."},
                )
                return

            updated_user = conn.execute(
                "SELECT id, username, first_name, last_name, email, created_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()

        if not updated_user:
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Utilisateur introuvable."})
            return

        self._send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "message": "Parametres mis a jour.",
                "user": {
                    "id": int(updated_user["id"]),
                    "username": str(updated_user["username"]),
                    "first_name": str(updated_user["first_name"]),
                    "last_name": str(updated_user["last_name"]),
                    "email": str(updated_user["email"]),
                    "created_at": str(updated_user["created_at"]),
                },
            },
        )

    def _load_game_catalog(self) -> Tuple[Optional[Dict[str, Any]], Optional[List[str]], Optional[str]]:
        with db_connection() as conn:
            catalog, levels = game_load_catalog(conn)

        if not levels:
            return None, None, "Aucun niveau exploitable trouve en base de donnees."

        return catalog, levels, None

    def _read_requested_level(self) -> str:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        level = query.get("level", [""])[0]
        return str(level).strip()

    def _resolve_level_key(
        self,
        requested_level: str,
        available_levels: List[str],
    ) -> str:
        return game_resolve_level_key(requested_level, available_levels)

    def _level_to_challenge_id(self, level_key: str) -> int:
        digits = "".join(ch for ch in level_key if ch.isdigit())
        if not digits:
            return 0
        return int(digits)

    def _clone_maze(self, maze: List[List[Any]]) -> List[List[str]]:
        clone: List[List[str]] = []
        for row in maze:
            clone.append([str(cell) for cell in row])
        return clone

    def _execute_game_run(self, code: str, maze: List[List[str]]) -> Dict[str, Any]:
        run = tester(
            code,
            self._clone_maze(maze),
            return_history=True,
            max_trace_steps=2000,
            exec_globals={"__builtins__": SAFE_EXEC_BUILTINS},
        )
        if not run:
            return {
                "status": "failed",
                "message": "Aucun resultat retourne par le moteur de test.",
                "error": "Execution impossible",
                "history": [],
                "trace": [],
                "current": None,
                "steps": 0,
            }

        raw_history = run.get("history", [])
        raw_trace = run.get("trace", [])
        raw_current = run.get("current")

        history = [list(pos) for pos in raw_history if isinstance(pos, (list, tuple)) and len(pos) == 2]
        trace: List[Dict[str, Any]] = []
        for event in raw_trace[:500]:
            if not isinstance(event, dict):
                continue
            line_no = event.get("lineno")
            line_text = event.get("line")
            position = event.get("position")
            if not isinstance(line_no, int):
                continue
            if not isinstance(line_text, str):
                line_text = ""
            if not (isinstance(position, list) and len(position) == 2):
                position = None
            trace.append(
                {
                    "lineno": line_no,
                    "line": line_text,
                    "position": position,
                }
            )

        current = list(raw_current) if isinstance(raw_current, (list, tuple)) and len(raw_current) == 2 else None
        status = str(run.get("status") or "failed").lower()
        message = str(run.get("message") or "")
        error = run.get("error")
        error_text = str(error) if error else None
        steps = max(0, len(history) - 1)

        if status not in {"success", "failed"}:
            status = "failed"

        return {
            "status": status,
            "message": message,
            "error": error_text,
            "history": history,
            "trace": trace,
            "current": current,
            "steps": steps,
        }

    def _handle_game_levels(self) -> None:
        catalog, levels, error = self._load_game_catalog()
        if error or catalog is None or levels is None:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": error or "Erreur jeu"})
            return

        payload_levels: List[Dict[str, Any]] = []
        for level_key in levels:
            level_data = catalog.get(level_key)
            if not isinstance(level_data, dict):
                continue
            maze = level_data.get("maze")
            if not isinstance(maze, list):
                continue
            rows = len(maze)
            cols = max((len(row) for row in maze if isinstance(row, list)), default=0)
            payload_levels.append(
                {
                    "key": level_key,
                    "name": f"Niveau {self._level_to_challenge_id(level_key) or level_key}",
                    "rows": rows,
                    "cols": cols,
                }
            )

        self._send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "default_level": levels[0],
                "levels": payload_levels,
            },
        )

    def _handle_game_maze(self) -> None:
        catalog, levels, error = self._load_game_catalog()
        if error or catalog is None or levels is None:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": error or "Erreur jeu"})
            return

        requested_level = self._read_requested_level()
        level_key = self._resolve_level_key(requested_level, levels)
        level_data = catalog.get(level_key)
        if not isinstance(level_data, dict):
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Niveau introuvable."})
            return

        maze = level_data.get("maze")
        if not isinstance(maze, list):
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": "Labyrinthe invalide."})
            return

        self._send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "level": level_key,
                "maze": self._clone_maze(maze),
            },
        )

    def _handle_game_code(self) -> None:
        catalog, levels, error = self._load_game_catalog()
        if error or catalog is None or levels is None:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": error or "Erreur jeu"})
            return

        requested_level = self._read_requested_level()
        level_key = self._resolve_level_key(requested_level, levels)

        level_data = catalog.get(level_key)
        if not isinstance(level_data, dict):
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Niveau introuvable."})
            return

        default_code = level_data.get("default_code")
        if not isinstance(default_code, str):
            default_code = ""
        resolved_code = default_code
        from_saved = False

        token = self._session_token_from_cookie()
        user_id = get_session_user_id(token)
        if user_id:
            with db_connection() as conn:
                saved = conn.execute(
                    "SELECT code FROM user_level_code WHERE user_id = ? AND level_key = ?",
                    (user_id, level_key),
                ).fetchone()
            if saved and isinstance(saved["code"], str):
                resolved_code = str(saved["code"])
                from_saved = True

        self._send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "level": level_key,
                "content": resolved_code,
                "from_saved": from_saved,
            },
        )

    def _handle_game_save_code(self) -> None:
        user_id = self._require_user_id()
        if user_id is None:
            return

        body, error = self._read_json_body()
        if error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": error})
            return

        catalog, levels, catalog_error = self._load_game_catalog()
        if catalog_error or catalog is None or levels is None:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error": catalog_error or "Erreur jeu"},
            )
            return

        requested_level = str(body.get("level", "")).strip()
        level_key = self._resolve_level_key(requested_level, levels)
        content = body.get("content")
        if not isinstance(content, str):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "Le contenu du code doit etre une chaine."},
            )
            return

        trimmed = content.strip()
        if not trimmed:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "Le code ne peut pas etre vide."},
            )
            return

        if len(content) > 20_000:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "Le code est trop long (max 20000 caracteres)."},
            )
            return

        with db_connection() as conn:
            conn.execute(
                """
                INSERT INTO user_level_code (user_id, level_key, code, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, level_key)
                DO UPDATE SET code = excluded.code, updated_at = excluded.updated_at
                """,
                (user_id, level_key, content, utc_now_iso()),
            )
            conn.commit()

        self._send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "message": "Code sauvegarde.",
                "level": level_key,
            },
        )

    def _handle_game_run(self) -> None:
        body, error = self._read_json_body()
        if error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": error})
            return

        catalog, levels, catalog_error = self._load_game_catalog()
        if catalog_error or catalog is None or levels is None:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error": catalog_error or "Erreur jeu"},
            )
            return

        requested_level = str(body.get("level", "")).strip()
        level_key = self._resolve_level_key(requested_level, levels)
        level_data = catalog.get(level_key)
        if not isinstance(level_data, dict):
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Niveau introuvable."})
            return

        content = body.get("content")
        if not isinstance(content, str) or not content.strip():
            default_code = level_data.get("default_code")
            content = str(default_code) if isinstance(default_code, str) else ""
        if not content.strip():
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Le code ne peut pas etre vide."})
            return
        try:
            validate_game_code(content)
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return

        maze = level_data.get("maze")
        if not isinstance(maze, list):
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": "Labyrinthe invalide."})
            return

        run = self._execute_game_run(content, maze)
        success = run["status"] == "success" and not run["error"]

        self._send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "level": level_key,
                "run": {
                    "status": "passed" if success else "failed",
                    "message": run["message"],
                    "error": run["error"],
                    "history": run["history"],
                    "trace": run["trace"],
                    "current": run["current"],
                    "steps": run["steps"],
                },
            },
        )

    def _handle_game_submit(self) -> None:
        user_id = self._require_user_id()
        if user_id is None:
            return

        body, error = self._read_json_body()
        if error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": error})
            return

        catalog, levels, catalog_error = self._load_game_catalog()
        if catalog_error or catalog is None or levels is None:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error": catalog_error or "Erreur jeu"},
            )
            return

        requested_level = str(body.get("level", "")).strip()
        level_key = self._resolve_level_key(requested_level, levels)
        level_data = catalog.get(level_key)
        if not isinstance(level_data, dict):
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Niveau introuvable."})
            return

        content = body.get("content")
        if not isinstance(content, str) or not content.strip():
            default_code = level_data.get("default_code")
            content = str(default_code) if isinstance(default_code, str) else ""
        if not content.strip():
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Le code ne peut pas etre vide."})
            return

        if len(content) > 20_000:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "Le code est trop long (max 20000 caracteres)."},
            )
            return
        try:
            validate_game_code(content)
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return

        maze = level_data.get("maze")
        if not isinstance(maze, list):
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": "Labyrinthe invalide."})
            return

        run = self._execute_game_run(content, maze)
        success = run["status"] == "success" and not run["error"]

        try:
            raw_time = int(body.get("time_seconds", 0))
        except (TypeError, ValueError):
            raw_time = 0
        time_seconds = max(0, raw_time)

        status = "passed" if success else "failed"
        tests_total = 1
        tests_passed = 1 if success else 0
        steps = int(run["steps"])

        if success:
            xp_delta = max(20, 120 - max(0, steps - 12) * 4)
        else:
            xp_delta = 5

        challenge_id = self._level_to_challenge_id(level_key)
        created_at = utc_now_iso()
        with db_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO attempts (
                    user_id, challenge_id, status, tests_passed, tests_total, time_seconds, xp_delta, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    challenge_id,
                    status,
                    tests_passed,
                    tests_total,
                    time_seconds,
                    xp_delta,
                    created_at,
                ),
            )
            conn.execute(
                """
                INSERT INTO user_level_code (user_id, level_key, code, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, level_key)
                DO UPDATE SET code = excluded.code, updated_at = excluded.updated_at
                """,
                (user_id, level_key, content, created_at),
            )
            conn.commit()

            attempt_id = cursor.lastrowid

        self._send_json(
            HTTPStatus.CREATED,
            {
                "ok": True,
                "message": "Tentative enregistree.",
                "level": level_key,
                "run": {
                    "status": status,
                    "message": run["message"],
                    "error": run["error"],
                    "steps": steps,
                    "history": run["history"],
                    "trace": run["trace"],
                    "current": run["current"],
                },
                "attempt": {
                    "id": int(attempt_id) if attempt_id is not None else None,
                    "challenge_id": challenge_id,
                    "status": status,
                    "tests_passed": tests_passed,
                    "tests_total": tests_total,
                    "time_seconds": time_seconds,
                    "xp_delta": xp_delta,
                },
            },
        )

    def _require_user_id(self) -> Optional[int]:
        token = self._session_token_from_cookie()
        user_id = get_session_user_id(token)
        if not user_id:
            self._send_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "Non authentifie."})
            return None
        return user_id

    def _handle_create_attempt(self) -> None:
        user_id = self._require_user_id()
        if user_id is None:
            return

        body, error = self._read_json_body()
        if error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": error})
            return

        try:
            challenge_id = int(body.get("challenge_id"))
        except (TypeError, ValueError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "challenge_id invalide."})
            return

        status = str(body.get("status", "")).strip().lower()
        if status not in {"passed", "partial", "failed"}:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "status invalide (attendu: passed, partial, failed)."},
            )
            return

        def to_int(key: str, default: int = 0) -> int:
            try:
                return int(body.get(key, default))
            except (TypeError, ValueError):
                return default

        tests_passed = max(0, to_int("tests_passed", 0))
        tests_total = max(0, to_int("tests_total", 0))
        time_seconds = max(0, to_int("time_seconds", 0))
        xp_delta = to_int("xp_delta", 0)

        with db_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO attempts (
                    user_id, challenge_id, status, tests_passed, tests_total, time_seconds, xp_delta, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, challenge_id, status, tests_passed, tests_total, time_seconds, xp_delta, utc_now_iso()),
            )
            conn.commit()
            attempt_id = cursor.lastrowid

        self._send_json(
            HTTPStatus.CREATED,
            {
                "ok": True,
                "attempt": {
                    "id": int(attempt_id) if attempt_id is not None else None,
                    "challenge_id": challenge_id,
                    "status": status,
                    "tests_passed": tests_passed,
                    "tests_total": tests_total,
                    "time_seconds": time_seconds,
                    "xp_delta": xp_delta,
                },
            },
        )

    def _handle_dashboard_me(self) -> None:
        user_id = self._require_user_id()
        if user_id is None:
            return

        with db_connection() as conn:
            user = conn.execute(
                "SELECT id, username, first_name, last_name, email, created_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            attempts = conn.execute(
                """
                SELECT challenge_id, status, tests_passed, tests_total, time_seconds, xp_delta, created_at
                FROM attempts
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 20
                """,
                (user_id,),
            ).fetchall()

        attempts_payload: List[Dict[str, Any]] = []
        total_tests_passed = 0
        total_tests = 0
        xp_total = 0
        passed_count = 0
        partial_count = 0
        failed_count = 0

        for row in attempts:
            status = str(row["status"])
            if status == "passed":
                passed_count += 1
            elif status == "partial":
                partial_count += 1
            else:
                failed_count += 1

            tp = int(row["tests_passed"] or 0)
            tt = int(row["tests_total"] or 0)
            total_tests_passed += max(0, tp)
            total_tests += max(0, tt)
            xp_total += int(row["xp_delta"] or 0)

            attempts_payload.append(
                {
                    "challengeId": int(row["challenge_id"]),
                    "status": status,
                    "testsPassed": int(row["tests_passed"]),
                    "testsTotal": int(row["tests_total"]),
                    "timeSeconds": int(row["time_seconds"]),
                    "xp": int(row["xp_delta"]),
                    "createdAt": str(row["created_at"]),
                }
            )

        accuracy = 0.0
        if total_tests > 0:
            accuracy = (total_tests_passed / total_tests) * 100.0

        total_attempts = passed_count + partial_count + failed_count
        base = 0.0 if total_attempts == 0 else (passed_count + 0.5 * partial_count) / total_attempts
        progress = {
            "arrays": round(base * 100.0),
            "strings": round(clamp(base * 100.0 + 8.0, 0.0, 100.0)),
            "conditionals": round(clamp(base * 100.0 + 18.0, 0.0, 100.0)),
        }

        self._send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "user": {
                    "id": int(user["id"]) if user else user_id,
                    "username": str(user["username"]) if user else "",
                    "first_name": str(user["first_name"]) if user else "",
                    "last_name": str(user["last_name"]) if user else "",
                    "email": str(user["email"]) if user else "",
                    "created_at": str(user["created_at"]) if user else "",
                },
                "stats": {
                    "xpTotal": xp_total,
                    "attemptsTotal": total_attempts,
                    "passed": passed_count,
                    "partial": partial_count,
                    "failed": failed_count,
                    "accuracy": accuracy,
                },
                "progress": progress,
                "attempts": attempts_payload,
            },
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

