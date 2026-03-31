# CodeArena - Auth Backend

## Lancer le serveur

```powershell
python -m Backend.app
```

Le serveur demarre par defaut sur `http://127.0.0.1:8000`.

## URL front

Ouvrir:

`http://127.0.0.1:8000/Assets/html/login.html`

## Endpoints disponibles

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `POST /api/account/update`
- `GET /api/dashboard/me`
- `GET /api/health`

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
