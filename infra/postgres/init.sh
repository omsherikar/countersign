#!/bin/bash
# Creates the three databases on first boot of the postgres volume.
set -e
for db in "${API_DB_NAME:-countersign}" "${API_TEST_DB_NAME:-countersign_test}" "${MOCKGOV_DB_NAME:-mockgov}"; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -tc \
    "SELECT 1 FROM pg_database WHERE datname = '$db'" | grep -q 1 || \
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -c "CREATE DATABASE \"$db\""
done
