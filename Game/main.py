import sys

from Game.storage import load_game_catalog, resolve_level_key
from Game.tester import tester


def main() -> None:
    requested_level = "maze1"
    if len(sys.argv) > 1 and sys.argv[1].strip():
        requested_level = sys.argv[1].strip()

    catalog, levels = load_game_catalog()
    if not levels:
        raise RuntimeError("Aucun niveau de jeu n'est disponible dans maze.json.")

    level_key = resolve_level_key(requested_level, levels)
    level_data = catalog[level_key]
    code = str(level_data.get("default_code", ""))
    laby = level_data.get("maze")
    if not isinstance(laby, list):
        raise RuntimeError("Labyrinthe invalide dans maze.json.")

    tester(code, laby)


if __name__ == "__main__":
    main()
