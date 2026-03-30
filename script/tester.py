import sys
import time


def display_laby(laby, current_pos):
    symbols = {" ": ' ', "#": '#', 'S': 'S', 'O': 'O'}
    for i in range(len(laby)):
        row = ""
        for j in range(len(laby[i])):
            if (i, j) == current_pos:
                row += "P"
            else:
                row += symbols.get(laby[i][j], ' ')
        print(row)


def _find_start(laby):
    for i in range(len(laby)):
        for j in range(len(laby[i])):
            if laby[i][j] in ('S', 'P'):
                return (i, j)
    return None


def tester(code, laby, return_history=False, exec_globals=None):
    if not laby:
        message = "Labyrinthe vide"
        if return_history:
            return {
                'error': message,
                'history': [],
                'trace': [],
                'current': None,
                'status': 'failed',
                'message': message,
            }
        print(f"✗ {message}")
        return

    start = _find_start(laby)

    if start is None:
        message = "Depart introuvable (case 2 ou 4)"
        if return_history:
            return {
                'error': message,
                'history': [],
                'trace': [],
                'current': None,
                'status': 'failed',
                'message': message,
            }
        print(f"✗ {message}")
        return

    current_pos = [start]
    history = [start]
    trace = []
    code_lines = code.splitlines()

    def tracer(frame, event, arg):
        if event == 'line' and frame.f_code.co_filename == '<string>':
            lineno = frame.f_lineno
            line = code_lines[lineno - 1] if 1 <= lineno <= len(code_lines) else ''
            trace.append({
                'lineno': lineno,
                'line': line,
                'position': list(current_pos[0]),
            })
        return tracer

    def move(direction):
        moves = {
            'left': (0, -1),
            'right': (0, 1),
            'up': (-1, 0),
            'down': (1, 0),
        }

        if direction not in moves:
            raise ValueError("Direction invalide. Utilise: left, right, up, down")

        dx, dy = moves[direction]
        x, y = current_pos[0]
        nx, ny = x + dx, y + dy

        if not (0 <= nx < len(laby) and 0 <= ny < len(laby[0])):
            raise ValueError(f"Sortie des limites: {(nx, ny)}")

        if laby[nx][ny] == '#':
            raise ValueError(f"Mur rencontre: {(nx, ny)}")

        current_pos[0] = (nx, ny)
        history.append((nx, ny))
        return current_pos[0]

    error = None
    try:
        sys.settrace(tracer)
        globals_scope = {'laby': laby, 'move': move}
        if isinstance(exec_globals, dict):
            globals_scope.update(exec_globals)
        exec(code, globals_scope)
    except Exception as exc:
        error = f"Erreur pendant l'execution: {exc}"
    finally:
        sys.settrace(None)

    if return_history:
        x, y = current_pos[0]
        if error:
            status = 'failed'
            message = error
        else:
            status = 'success' if laby[x][y] == 'O' else 'failed'
            message = 'Arrivee atteinte' if status == 'success' else f"Arrivee non atteinte. Position finale: {current_pos[0]}"
        result = {
            'error': error,
            'history': history,
            'trace': trace,
            'current': current_pos[0],
            'status': status,
            'message': message,
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
