#!/bin/sh
# Runs inside the postgres container (make demo-snapshot, make demo-restore): "snapshot" copies
# the api and mockgov databases to *_snap templates; "restore" rebuilds both from them. The
# Makefile stops the services that hold connections first.
set -eu
q() { psql -v ON_ERROR_STOP=1 -qAt -U "$POSTGRES_USER" -d postgres -c "$1"; }
api="${API_DB_NAME:-countersign}"
gov="${MOCKGOV_DB_NAME:-mockgov}"
q "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('$api', '$gov', '${api}_snap', '${gov}_snap') AND pid <> pg_backend_pid();" > /dev/null
case "${1:-}" in
  snapshot)
    for db in "$api" "$gov"; do
      q "DROP DATABASE IF EXISTS ${db}_snap;"
      q "CREATE DATABASE ${db}_snap TEMPLATE $db;"
    done ;;
  restore)
    for db in "$api" "$gov"; do
      q "SELECT 1 FROM pg_database WHERE datname = '${db}_snap';" | grep -q 1 || { echo "no snapshot of $db; run make demo-snapshot first" >&2; exit 1; }
      q "DROP DATABASE IF EXISTS $db;"
      q "CREATE DATABASE $db TEMPLATE ${db}_snap;"
    done ;;
  *) echo "usage: demo-db.sh snapshot|restore" >&2; exit 2 ;;
esac
echo "$1: $api and $gov"
