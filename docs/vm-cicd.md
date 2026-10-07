# VM staging and production deployment

The VM runs separate Docker Compose projects for staging and production. Each
environment has its own API, web container, database container, database
volume, JWT secret, and admin bootstrap credentials. Caddy remains the shared
TLS proxy.

| Environment | Branch | Web | API | Database volume |
| --- | --- | --- | --- | --- |
| Staging | `staging` | `erp.103.93.134.27.nip.io` | `api.103.93.134.27.nip.io` | Existing `manuflow_production_postgres_data` |
| Production | `main` | `ep.103.93.134.27.nip.io` | `ap.103.93.134.27.nip.io` | New `manuflow_prod_postgres_data` |

## One-time VM setup

1. Copy this repository revision to the VM.
2. Run `python3 /opt/manuflow/deploy/vm/bootstrap-environments.py` once. It
   preserves current production credentials in `.env.staging`, assigns the
   existing database volume to staging, creates fresh production database/JWT
   secrets, and sets the production bootstrap admin to `admin@example.com` /
   `Admin123!`. It does not print credentials and refuses to run a second time.
3. Keep `/opt/manuflow/.env.staging` and `/opt/manuflow/.env.production` private
   (`0600`). These files are excluded from release archives and Git.
4. Add the public SSH key matching GitHub's `DEPLOY_SSH_KEY` secret to
   `nstprod`'s `authorized_keys`. Add repository secret `DEPLOY_SSH_KEY` with
   its private key. The VM host and user are fixed in the workflow, and its
   public host key is pinned in `.github/vm_known_hosts`.
5. Deploy a commit on `staging` first, then deploy `main`. The first staging
   cutover backs up the current database, stops the legacy app/database
   containers, and mounts their existing data volume from the staging stack.
6. Verify both sites and APIs. The `main` deployment creates its own empty
   database and runs Alembic migrations plus the idempotent admin seed.

## Automatic deployments

`.github/workflows/deploy-vm.yml` runs backend and Flutter checks, then deploys
every pushed commit on `staging` or `main`. It packages the checked-out commit, copies it to a revision-specific
release directory, builds the matching environment, waits for local API/web
health checks, reloads Caddy, and checks the public web/API routes. Staging and
production deployments run independently and serially per branch.

Before cutover, create a fresh database backup and test restoration in a
separate database. Migration files run during API startup. A failed migration
stops the deployment before the API health check can pass; the previous release
archive and database backup remain on the VM for recovery.
