import sys

from Backend.database import db_connection, init_db
from Game.storage import load_game_catalog, resolve_level_key
from Game.tester import tester


def main() -> None:
    requested_level = "maze1"
    if len(sys.argv) > 1 and sys.argv[1].strip():
        requested_level = sys.argv[1].strip()

    init_db()
    with db_connection() as conn:
        catalog, levels = load_game_catalog(conn)
    if not levels:
        raise RuntimeError("Aucun niveau de jeu n'est disponible en base de donnees.")

    level_key = resolve_level_key(requested_level, levels)
    level_data = catalog[level_key]
    code = str(level_data.get("default_code", ""))
    laby = level_data.get("maze")
    if not isinstance(laby, list):
        raise RuntimeError("Labyrinthe invalide en base de donnees.")

    tester(code, laby)


if __name__ == "__main__":
    main()
