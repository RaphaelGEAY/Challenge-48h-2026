# CodeArena - Auth Backend

## Lancer le serveur

```powershell
python -m Backend.app
```

Le serveur demarre par defaut sur `http://127.0.0.1:8000`.

Le moteur de jeu lit maintenant les niveaux depuis `database.db` (table `game_levels`).
Au premier demarrage, les niveaux sont initialises depuis `Game/maze.json` vers la base.

## URL front

Ouvrir:

`http://127.0.0.1:8000/Assets/html/login.html`

`http://127.0.0.1:8000/Assets/html/play.html`

## Endpoints disponibles

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `POST /api/account/update`
- `GET /api/dashboard/me`
- `GET /api/game/levels`
- `GET /api/game/maze?level=maze1`
- `GET /api/game/code?level=maze1`
- `POST /api/game/code/save`
- `POST /api/game/run`
- `POST /api/game/submit`
- `GET /api/health`

## Structure

- `Game/`: logique du jeu (lecture des niveaux, execution du tester, stockage des niveaux)
- `Backend/`: API HTTP, auth, dashboard, persistance SQLite

## Format JSON

### Register

```json
{
  "first_name": "Raphael",
  "last_name": "Martin",
  "username": "CodeNinja42",
  "email": "you@example.com",
  "password": "super-secret-password"
}
```

### Run game code

```json
{
  "level": "maze1",
  "content": "for _ in range(3):\n    move('right')",
  "time_seconds": 42
}
```
