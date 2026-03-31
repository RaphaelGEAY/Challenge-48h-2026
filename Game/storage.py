import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_MAZE_PATH = Path(__file__).resolve().parent / "maze.json"


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


def _read_payload(maze_path: Path) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if maze_path.exists():
        try:
            with maze_path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
            if isinstance(raw, dict):
                payload = raw
        except (json.JSONDecodeError, OSError):
            payload = {}
    return payload


def load_game_catalog(maze_path: Optional[Path] = None) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    source_path = maze_path or DEFAULT_MAZE_PATH
    payload = _read_payload(source_path)
    levels_payload = _levels_from_json_payload(payload)
    if not levels_payload:
        levels_payload = {"maze1": _fallback_level()}

    default_code = payload.get("content")
    if not isinstance(default_code, str) or not default_code.strip():
        default_code = default_code_template()

    catalog: Dict[str, Dict[str, Any]] = {}
    for level_key, maze in levels_payload.items():
        catalog[level_key] = {
            "maze": maze,
            "default_code": default_code if default_code.strip() else default_code_template(),
        }

    levels = sorted(catalog.keys(), key=level_sort_key)
    return catalog, levels

