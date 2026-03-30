import time

def display_laby(laby, current_pos):
    symbols = {0: '0', 1: '1', 2: '2', 3: '3'}
    for i in range(len(laby)):
        row = ""
        for j in range(len(laby[i])):
            if (i, j) == current_pos:
                row += "4 "
            else:
                row += symbols.get(laby[i][j], '2') + " "
        print(row)

def tester(code, laby):
    if not laby:
        print("✗ Labyrinthe vide")
        return

    start = None
    for i in range(len(laby)):
        for j in range(len(laby[i])):
            if laby[i][j] in (2, 4):
                start = (i, j)
                break
        if start is not None:
            break

    if start is None:
        print("✗ Depart introuvable (case 2 ou 4)")
        return

    current_pos = [start]
    history = [start]

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

        if laby[nx][ny] == 1:
            raise ValueError(f"Mur rencontre: {(nx, ny)}")

        current_pos[0] = (nx, ny)
        history.append((nx, ny))
        return current_pos[0]

    try:
        exec(code, {'laby': laby, 'move': move})
    except Exception as exc:
        print(f"✗ Erreur pendant l'execution: {exc}")

    for pos in history:
        display_laby(laby, pos)
        print()
        time.sleep(1)

    x, y = current_pos[0]
    if laby[x][y] == 3:
        print("✓ Arrivee atteinte")
    else:
        print(f"✗ Arrivee non atteinte. Position finale: {current_pos[0]}")
