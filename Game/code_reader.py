import sqlite3
from typing import List, Tuple

from .storage import load_game_catalog, resolve_level_key


def _resolve_level(conn: sqlite3.Connection, level_key: str) -> Tuple[str, List[List[str]], str]:
    catalog, levels = load_game_catalog(conn)
    if not levels:
        raise ValueError("Aucun niveau n'est disponible en base de donnees.")

    resolved_level = resolve_level_key(level_key, levels)
    data = catalog.get(resolved_level)
    if not isinstance(data, dict):
        raise ValueError("Niveau introuvable.")

    maze = data.get("maze")
    default_code = data.get("default_code")
    if not isinstance(maze, list):
        raise ValueError("Labyrinthe invalide.")
    if not isinstance(default_code, str):
        default_code = ""
    return resolved_level, maze, default_code


def read_code(conn: sqlite3.Connection, level_key: str = "maze1") -> str:
    _resolved_level, _maze, default_code = _resolve_level(conn, level_key)
    return default_code


def read_laby(conn: sqlite3.Connection, level_key: str = "maze1") -> List[List[str]]:
    _resolved_level, maze, _default_code = _resolve_level(conn, level_key)
    return maze
