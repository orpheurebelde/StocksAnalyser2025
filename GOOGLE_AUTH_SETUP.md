# Google Login Setup

## Google Cloud

1. Open Google Cloud Console and select or create project.
2. Configure Google Auth Platform branding, support email, and audience.
3. Create OAuth client ID with application type **Web application**.
4. Add authorized JavaScript origins:
   - `http://localhost:5173`
   - production frontend origin, for example `https://your-app.vercel.app`
5. Copy client ID. Client secret is not required for Google Identity Services ID-token login.

## Backend

Copy `backend/.env.example` to `backend/.env` and set:

```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
ADMIN_EMAILS=almeida1976marco@gmail.com
DATABASE_URL=postgresql://...
FRONTEND_ORIGINS=http://localhost:5173,https://your-app.vercel.app
AUTH_COOKIE_SECURE=false
AUTH_COOKIE_SAMESITE=lax
```

Production uses Vercel's same-origin `/api` rewrite to avoid third-party-cookie blocking. Leave `VITE_API_URL` unset in Vercel and use:

```env
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=lax
```

If backend URL changes, update API destination in `frontend/vercel.json`. Direct cross-site API calls require `AUTH_COOKIE_SAMESITE=none`, but browser privacy controls may still block those cookies.

Install updated backend dependencies:

```powershell
pip install -r backend/requirements.txt
```

Auth tables initialize at API startup in `DATABASE_URL`/`POSTGRES_URL`. Without Postgres, local auth uses `backend/auth.sqlite` or `AUTH_DB_PATH`.

## Frontend

Copy `frontend/.env.example` to `frontend/.env`:

```env
VITE_API_URL=http://localhost:8000
VITE_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
```

Set `VITE_GOOGLE_CLIENT_ID` in production frontend environment. Leave `VITE_API_URL` unset when using Vercel rewrite. Redeploy after changing `VITE_*` variables.

## Database Tables

- `app_users`: Google identity and profile.
- `auth_sessions`: hashed opaque session tokens, expiry, revocation, IP, and user agent.
- `login_events`: successful logins, failed logins, and logout events.
- `user_activity`: authenticated API method, path, status, duration, session, IP, and user agent.

Request bodies, Google credentials, passwords, and Google access tokens are not logged.

`ADMIN_EMAILS` accepts comma-separated verified Google email addresses. `almeida1976marco@gmail.com` is default bootstrap admin. Admins can read recent audit data at `GET /api/auth/admin/audit`.

## Deployment Check

1. Start backend and confirm auth tables exist.
2. Open frontend `/login` and sign in.
3. Confirm `/api/auth/me` returns user with browser credentials enabled.
4. Confirm protected API requests return `401` without session cookie.
5. Confirm login and API rows appear in `login_events` and `user_activity`.
6. Test logout and verify old session has `revoked_at` populated.
