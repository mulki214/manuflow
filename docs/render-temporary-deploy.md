# Temporary Render deployment

This deployment publishes the Flutter web frontend, FastAPI backend, and PostgreSQL database.
It is intended for testing: Render's free database expires after 30 days and
the free web service sleeps after inactivity.

## Create the services

1. Push this project to a private GitHub repository. Do not commit `.env`.
2. In Render, select **New > Blueprint**, connect the repository, and select
   `render.yaml`.
3. Enter a strong value for `FIRST_ADMIN_PASSWORD` when prompted. Render
   generates `JWT_SECRET` and creates the database automatically.
4. Wait for `manuflow-api` and `manuflow-web` to finish their first deploy, then verify:

   ```text
   https://manuflow-api.onrender.com/health
   ```

   The web application is available at:

   ```text
   https://manuflow-web.onrender.com
   ```

## Copy local data after the cloud database exists

From Render database **Connect**, copy the External Database URL. Replace its
scheme with `postgresql+asyncpg://` only for the API; keep its original
`postgresql://` form for `pg_dump`/`pg_restore`.

Create a local backup (do not commit it):

```bash
docker compose exec -T db pg_dump -U erp -d erp_manufaktur -Fc > manuflow-local.dump
```

Restore it using the external URL from Render:

```bash
pg_restore --clean --if-exists --no-owner --no-privileges \
  --dbname='postgresql://USER:PASSWORD@HOST:5432/erp_manufaktur' \
  manuflow-local.dump
```

Then redeploy `manuflow-api` once, so Alembic confirms the schema and the
admin seed safely detects the existing user.

## Android testing

Run the Flutter app with the published API URL:

```bash
flutter run --dart-define=API_URL=https://manuflow-api.onrender.com/api/v1
```

For a deployed web frontend, add its HTTPS origin to the `CORS_ORIGINS`
environment variable in Render, using JSON list syntax.
