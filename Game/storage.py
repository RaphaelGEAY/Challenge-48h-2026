import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def default_code_template() -> str:
    return "\n".join(
        [
            "# Use move('up'|'down'|'left'|'right') to reach O",
            "for _ in range(3):",
            "    move('right')",
        ]
    )


def level_sort_key(level_key: str) -> Tuple[int, str]:
    digits = "".join(ch for ch in level_key if ch.isdigit())
    if not digits:
        return (10_000, level_key)
    return (int(digits), level_key)


def resolve_level_key(requested_level: str, available_levels: List[str]) -> str:
    if requested_level in available_levels:
        return requested_level
    if not available_levels:
        return "maze1"
    return available_levels[0]


def _normalize_maze(value: Any) -> Optional[List[List[str]]]:
    if not isinstance(value, list) or not value:
        return None

    normalized: List[List[str]] = []
    for row in value:
        if not isinstance(row, list):
            return None
        normalized_row = [str(cell) for cell in row]
        normalized.append(normalized_row)

    return normalized


def _levels_from_json_payload(payload: Dict[str, Any]) -> Dict[str, List[List[str]]]:
    levels: Dict[str, List[List[str]]] = {}
    for key, value in payload.items():
        if not key.startswith("maze"):
            continue
        normalized = _normalize_maze(value)
        if normalized:
            levels[key] = normalized
    return levels


def _fallback_level() -> List[List[str]]:
    return [
        ["#", "#", "#", "#", "#", "#"],
        ["#", "S", " ", " ", "O", "#"],
        ["#", "#", "#", "#", "#", "#"],
    ]


def seed_game_levels(conn: sqlite3.Connection, maze_path: Path) -> None:
    row = conn.execute("SELECT COUNT(*) FROM game_levels").fetchone()
    existing_count = int(row[0]) if row and row[0] is not None else 0
    if existing_count > 0:
        return

    payload: Dict[str, Any] = {}
    if maze_path.exists():
        try:
            with maze_path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
            if isinstance(raw, dict):
                payload = raw
        except (json.JSONDecodeError, OSError):
            payload = {}

    levels = _levels_from_json_payload(payload)
    if not levels:
        levels = {"maze1": _fallback_level()}

    default_code = payload.get("content")
    if not isinstance(default_code, str) or not default_code.strip():
        default_code = default_code_template()

    now = datetime.now(timezone.utc).isoformat()
    for level_key in sorted(levels.keys(), key=level_sort_key):
        conn.execute(
            """
            INSERT INTO game_levels (level_key, maze_json, default_code, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                level_key,
                json.dumps(levels[level_key], ensure_ascii=True),
                default_code,
                now,
            ),
        )


def load_game_catalog(conn: sqlite3.Connection) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    rows = conn.execute(
        """
        SELECT level_key, maze_json, default_code
        FROM game_levels
        ORDER BY level_key ASC
        """
    ).fetchall()

    catalog: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        level_key = str(row["level_key"])
        maze_json = row["maze_json"]
        default_code = row["default_code"]
        if not isinstance(maze_json, str):
            continue
        if not isinstance(default_code, str):
            default_code = default_code_template()
        try:
            raw_maze = json.loads(maze_json)
        except json.JSONDecodeError:
            continue

        maze = _normalize_maze(raw_maze)
        if not maze:
            continue

        catalog[level_key] = {
            "maze": maze,
            "default_code": default_code if default_code.strip() else default_code_template(),
        }

    levels = sorted(catalog.keys(), key=level_sort_key)
    return catalog, levels

