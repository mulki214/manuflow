#!/usr/bin/env bash
set -Eeuo pipefail

environment="${1:-}"
revision="${2:-}"
archive="${3:-}"

case "$environment" in
  staging|production) ;;
  *) echo "Environment must be staging or production" >&2; exit 2 ;;
esac
if [[ ! "$revision" =~ ^[0-9a-f]{7,40}$ ]]; then
  echo "Revision must be a git SHA" >&2
  exit 2
fi
if [[ ! -f "$archive" ]]; then
  echo "Source archive not found" >&2
  exit 2
fi

base_dir=/opt/manuflow
release_dir="$base_dir/releases/$environment/$revision"
env_file="$base_dir/.env.$environment"
compose_file="$release_dir/docker-compose.vm.yml"
project="manuflow-$environment"

if [[ ! -f "$env_file" ]]; then
  echo "Missing $env_file. Run the environment bootstrap first." >&2
  exit 1
fi

mkdir -p "$release_dir" "$base_dir/backups" "$base_dir/deploy/production"
tar -xzf "$archive" -C "$release_dir"
test -f "$compose_file"

docker network inspect manuflow_proxy >/dev/null 2>&1 || docker network create manuflow_proxy >/dev/null

# The original production stack owns the existing database volume. On its first
# move to staging, back it up, then stop it before attaching that volume to the
# staging database container.
database_container="$(docker compose --project-name "$project" --env-file "$env_file" --file "$compose_file" ps -q db 2>/dev/null || true)"
if [[ -n "$database_container" ]] && docker inspect "$database_container" --format '{{.State.Running}}' | grep -qx true; then
  backup_file="$base_dir/backups/erp_manufaktur-${environment}-before-${revision:0:12}-$(date +%Y%m%d-%H%M%S).sql.gz"
  docker exec "$database_container" pg_dump -U erp -d erp_manufaktur | gzip > "$backup_file"
  test -s "$backup_file"
elif [[ "$environment" == staging ]] && docker inspect manuflow-db-1 >/dev/null 2>&1; then
  if ! docker ps --format '{{.Names}}' | grep -qx "$project-db-1"; then
    docker stop manuflow-api-1 manuflow-web-1 >/dev/null
    backup_file="$base_dir/backups/erp_manufaktur-before-staging-cutover-$(date +%Y%m%d-%H%M%S).sql.gz"
    backup_tmp="$backup_file.tmp"
    if ! docker exec manuflow-db-1 pg_dump -U erp -d erp_manufaktur | gzip > "$backup_tmp" \
      || [[ ! -s "$backup_tmp" ]] \
      || ! gzip -t "$backup_tmp"; then
      rm -f "$backup_tmp"
      docker start manuflow-api-1 manuflow-web-1 >/dev/null
      echo "Database backup failed; legacy web and API were restarted." >&2
      exit 1
    fi
    mv "$backup_tmp" "$backup_file"
    docker stop manuflow-db-1 >/dev/null
  fi
fi

docker compose \
  --project-name "$project" \
  --env-file "$env_file" \
  --file "$compose_file" \
  up -d --build --remove-orphans

api_container="$(docker compose --project-name "$project" --env-file "$env_file" --file "$compose_file" ps -q api)"
web_container="$(docker compose --project-name "$project" --env-file "$env_file" --file "$compose_file" ps -q web)"
if [[ -z "$api_container" || -z "$web_container" ]]; then
  echo "API or web container was not created" >&2
  exit 1
fi

healthy=false
for attempt in $(seq 1 60); do
  if docker exec "$api_container" python -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5)' >/dev/null 2>&1 \
    && docker exec "$web_container" sh -c 'wget -qO- http://127.0.0.1/ >/dev/null' >/dev/null 2>&1; then
    healthy=true
    break
  fi
  sleep 5
done
if [[ "$healthy" != true ]]; then
  docker compose --project-name "$project" --env-file "$env_file" --file "$compose_file" ps
  docker compose --project-name "$project" --env-file "$env_file" --file "$compose_file" logs --tail 100 api web
  echo "Environment failed its API or web health check" >&2
  exit 1
fi

# Keep the existing Caddy container and certificate storage. Attach it to the
# shared proxy network once, then reload routes after the target is healthy.
if ! docker inspect manuflow-caddy-1 >/dev/null 2>&1; then
  echo "The existing Caddy proxy container was not found" >&2
  exit 1
fi
if ! docker inspect manuflow-caddy-1 --format '{{json .NetworkSettings.Networks}}' | grep -q 'manuflow_proxy'; then
  docker network connect manuflow_proxy manuflow-caddy-1
fi
python3 -c 'from pathlib import Path; import sys; Path(sys.argv[2]).write_bytes(Path(sys.argv[1]).read_bytes())' \
  "$release_dir/deploy/production/Caddyfile" "$base_dir/deploy/production/Caddyfile"
docker exec manuflow-caddy-1 caddy validate --config /etc/caddy/Caddyfile
docker exec manuflow-caddy-1 caddy reload --config /etc/caddy/Caddyfile

echo "Deployed $environment revision $revision"
