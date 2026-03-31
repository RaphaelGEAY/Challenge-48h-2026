import sys
import time
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_SAFE_BUILTINS: Dict[str, Any] = {
    "range": range,
    "len": len,
    "enumerate": enumerate,
    "min": min,
    "max": max,
    "abs": abs,
    "int": int,
    "str": str,
    "sum": sum,
    "print": print,
}


def display_laby(laby: List[List[str]], current_pos: Tuple[int, int]) -> None:
    symbols = {" ": " ", "#": "#", "S": "S", "O": "O", "X": "X"}
    for i in range(len(laby)):
        row = ""
        for j in range(len(laby[i])):
            if (i, j) == current_pos:
                row += "P"
            else:
                row += symbols.get(laby[i][j], " ")
        print(row)


def _find_start(laby: List[List[str]]) -> Optional[Tuple[int, int]]:
    for i in range(len(laby)):
        for j in range(len(laby[i])):
            if laby[i][j] in ("S", "P"):
                return (i, j)
    return None


def tester(
    code: str,
    laby: List[List[str]],
    return_history: bool = False,
    max_trace_steps: int = 10000,
    exec_globals: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    if not laby:
        message = "Labyrinthe vide"
        if return_history:
            return {
                "error": message,
                "history": [],
                "trace": [],
                "current": None,
                "status": "failed",
                "message": message,
            }
        print(f"✗ {message}")
        return None

    start = _find_start(laby)
    if start is None:
        message = "Depart introuvable (case 2 ou 4)"
        if return_history:
            return {
                "error": message,
                "history": [],
                "trace": [],
                "current": None,
                "status": "failed",
                "message": message,
            }
        print(f"✗ {message}")
        return None

    current_pos = [start]
    history: List[Tuple[int, int]] = [start]
    trace: List[Dict[str, Any]] = []
    code_lines = code.splitlines()
    executed_steps = [0]
    moves_count = [0]  # move() calls
    jumps_count = [0]  # jump() calls

    def tracer(frame: Any, event: str, arg: Any) -> Any:
        if event == "line" and frame.f_code.co_filename == "<string>":
            executed_steps[0] += 1
            if executed_steps[0] > max(1, int(max_trace_steps)):
                raise RuntimeError("Limite de trace depassee (boucle potentiellement infinie).")

            lineno = frame.f_lineno
            line = code_lines[lineno - 1] if 1 <= lineno <= len(code_lines) else ""
            trace.append(
                {
                    "lineno": lineno,
                    "line": line,
                    "position": list(current_pos[0]),
                }
            )
        return tracer

    def move(direction: str) -> Tuple[int, int]:
        moves = {
            "left": (0, -1),
            "right": (0, 1),
            "up": (-1, 0),
            "down": (1, 0),
        }

        if direction not in moves:
            raise ValueError("Direction invalide. Utilise: left, right, up, down")

        dx, dy = moves[direction]
        x, y = current_pos[0]
        nx, ny = x + dx, y + dy

        if not (0 <= nx < len(laby) and 0 <= ny < len(laby[0])):
            raise ValueError(f"Sortie des limites: {(nx, ny)}")
        if laby[nx][ny] == "#":
            raise ValueError(f"Mur rencontre: {(nx, ny)}")
        if laby[nx][ny] == "X":
            raise ValueError(f"Piege touche: {(nx, ny)}")

        moves_count[0] += 1
        current_pos[0] = (nx, ny)
        history.append((nx, ny))
        return current_pos[0]

    def jump(direction: str) -> Tuple[int, int]:
        moves = {
            "left": (0, -1),
            "right": (0, 1),
            "up": (-1, 0),
            "down": (1, 0),
        }

        if direction not in moves:
            raise ValueError("Direction invalide pour jump. Utilise: left, right, up, down")

        dx, dy = moves[direction]
        x, y = current_pos[0]
        mx, my = x + dx, y + dy  # Case intermédiaire
        nx, ny = x + 2 * dx, y + 2 * dy

        if not (0 <= mx < len(laby) and 0 <= my < len(laby[0])):
            raise ValueError(f"Jump hors limites: {(mx, my)}")

        if laby[mx][my] == "#":
            raise ValueError(f"Mur bloque le jump: {(mx, my)}")

        if not (0 <= nx < len(laby) and 0 <= ny < len(laby[0])):
            raise ValueError(f"Jump hors limites: {(nx, ny)}")
        if laby[nx][ny] == "#":
            raise ValueError(f"Mur rencontre au jump: {(nx, ny)}")
        if laby[nx][ny] == "X":
            raise ValueError(f"Piege touche au jump: {(nx, ny)}")

        jumps_count[0] += 1
        current_pos[0] = (nx, ny)
        history.append((nx, ny))
        return current_pos[0]

    error: Optional[str] = None
    try:
        sys.settrace(tracer)
        globals_scope: Dict[str, Any] = {"laby": laby, "move": move, "jump": jump}
        if isinstance(exec_globals, dict):
            globals_scope.update(exec_globals)
        if "__builtins__" not in globals_scope:
            globals_scope["__builtins__"] = DEFAULT_SAFE_BUILTINS
        exec(code, globals_scope)
    except Exception as exc:
        error = f"Erreur pendant l'execution: {exc}"
    finally:
        sys.settrace(None)

    x, y = current_pos[0]
    if error:
        status = "failed"
        message = error
    else:
        status = "success" if laby[x][y] == "O" else "failed"
        message = "Arrivee atteinte" if status == "success" else f"Arrivee non atteinte. Position finale: {current_pos[0]}"

    if return_history:
        code_length = len(code)
        code_lines_count = len(code_lines)
        
        if error:
            score = 0
        else:
            # Base score: 500 points
            base = 500
            move_cost = moves_count[0]
            jump_cost = jumps_count[0] * 3      # Un jump coûte plus cher (less optimal)
            code_cost = code_length // 10       # 1 point par 10 caractères
            score = max(0, base - move_cost - jump_cost - code_cost) if status == "success" else 0
        
        return {
            "error": error,
            "history": history,
            "trace": trace,
            "current": current_pos[0],
            "status": status,
            "message": message,
            "moves": moves_count[0],
            "jumps": jumps_count[0],
            "code_length": code_length,
            "code_lines": code_lines_count,
            "score": score,
        }

    if error:
        print(f"✗ {error}")

    for pos in history:
        display_laby(laby, pos)
        print()
        time.sleep(1)

    if laby[x][y] == "O":
        print("✓ Arrivee atteinte")
    else:
        print(f"✗ Arrivee non atteinte. Position finale: {current_pos[0]}")
    return None
