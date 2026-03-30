# CodeArena - Auth Backend

## Lancer le serveur

```powershell
python -m Backend.app
```

Alternative equivalente:

```powershell
python .\Backend\app.py
```

Si `python` n'est pas disponible, essayez:

```powershell
py -3 -m Backend.app
```

Le serveur demarre par defaut sur `http://127.0.0.1:5000`.

## URL front

Ouvrir:

`http://127.0.0.1:5000/Assets/html/login.html`

`http://127.0.0.1:5000/Assets/html/account.html`

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

```
{
  "first_name": "Raphael",
  "last_name": "Martin",
  "username": "CodeNinja42",
  "email": "you@example.com",
  "password": "super-secret-password"
}
```

### Login

```
{
  "email": "you@example.com",
  "password": "super-secret-password"
}
```

### Update account

```
{
  "first_name": "Raphael",
  "last_name": "Martin",
  "username": "CodeNinja42",
  "email": "you@example.com",
  "current_password": "old-password-if-changing",
  "new_password": "new-password-or-empty"
}
```
