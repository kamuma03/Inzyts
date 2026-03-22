#!/bin/sh
set -e

# Ensure writable directories exist and are owned by the app user.
# Bind-mounted host directories may arrive as root-owned; fix that
# on every boot so the non-root "inzyts" process can write to them.
for dir in /app/logs /app/logs/jobs /app/output /app/data/uploads; do
    mkdir -p "$dir"
    chown -R inzyts:inzyts "$dir"
done

# Drop privileges and exec the real command.
# gosu resets HOME to the passwd entry (/home/inzyts) which doesn't exist.
# Wrap via sh -c so we can force HOME=/app after gosu drops privileges.
exec gosu inzyts env HOME=/app "$@"
