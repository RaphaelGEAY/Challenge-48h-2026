# CodeArena - Auth Backend

## Lancer le serveur

```powershell
python3 Connexion.py
```

Le serveur demarre par defaut sur `http://127.0.0.1:5000`.

## URL front

Ouvrir:

`http://127.0.0.1:5000/Assets/html/login.html`

## Endpoints disponibles

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `GET /api/health`

## Format JSON

### Register

```
{
  "username": "CodeNinja42",
  "email": "you@example.com",
  "password": "super-secret-password",
  "remember": true
}
```

### Login

```
{
  "email": "you@example.com",
  "password": "super-secret-password",
  "remember": true
}
```
