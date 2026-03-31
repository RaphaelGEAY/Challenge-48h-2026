import sys
import time
from typing import Any, Dict, List, Optional, Tuple


def display_laby(laby: List[List[str]], current_pos: Tuple[int, int]) -> None:
    symbols = {" ": " ", "#": "#", "S": "S", "O": "O"}
    for i in range(len(laby)):
        row = ""
        for j in range(len(laby[i])):
            if (i, j) == current_pos:
                row += "P"
            else:
                row += symbols.get(laby[i][j], " ")
        print(row)


def tester(
    code: str,
    laby: List[List[str]],
    return_history: bool = False,
    max_trace_steps: int = 1500,
) -> Optional[Dict[str, Any]]:
    if not laby:
        message = "Labyrinthe vide"
        if return_history:
            return {"error": message, "history": [], "current": None}
        print(f"✗ {message}")
        return

    start = None
    for i in range(len(laby)):
        for j in range(len(laby[i])):
            if laby[i][j] in ('S', 'P'):
                start = (i, j)
                break
        if start is not None:
            break

    if start is None:
        message = "Depart introuvable (case 2 ou 4)"
        if return_history:
            return {"error": message, "history": [], "current": None}
        print(f"✗ {message}")
        return

    current_pos = [start]
    history = [start]
    trace = []
    code_lines = code.splitlines()

    executed_steps = [0]

    def tracer(frame, event, arg):
        if event == "line" and frame.f_code.co_filename == "<string>":
            executed_steps[0] += 1
            if executed_steps[0] > max(1, max_trace_steps):
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

    def move(direction):
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

        current_pos[0] = (nx, ny)
        history.append((nx, ny))
        return current_pos[0]

    error = None
    try:
        sys.settrace(tracer)
        safe_builtins = {
            "range": range,
            "len": len,
            "enumerate": enumerate,
            "min": min,
            "max": max,
            "abs": abs,
            "int": int,
            "str": str,
            "print": print,
        }
        exec(code, {"laby": laby, "move": move, "__builtins__": safe_builtins})
    except Exception as exc:
        error = f"Erreur pendant l'execution: {exc}"
    finally:
        sys.settrace(None)

    if return_history:
        x, y = current_pos[0]
        status = "success" if laby[x][y] == "O" else "failed"
        message = "Arrivee atteinte" if status == "success" else f"Arrivee non atteinte. Position finale: {current_pos[0]}"
        result = {
            "error": error,
            "history": history,
            "trace": trace,
            "current": current_pos[0],
            "status": status,
            "message": message,
        }
        return result

    if error:
        print(f"✗ {error}")

    for pos in history:
        display_laby(laby, pos)
        print()
        time.sleep(1)

    x, y = current_pos[0]
    if laby[x][y] == 'O':
        print("✓ Arrivee atteinte")
    else:
        print(f"✗ Arrivee non atteinte. Position finale: {current_pos[0]}")
