#!/bin/bash
# Wrapper launchd actually invokes (see scripts/com.straf.kaggriculture.archive-sync.plist).
#
# launchd starts with none of the interactive shell profile — no venv activation, no
# `source .env` — so this script is deliberately self-contained: fixed absolute REPO
# path, and `analysis/archive_sync.py` reads `.env` itself (`_env_from_dotenv`), so no
# sourcing is needed here either.
#
# Runs the two cheap, safe-to-run-unattended steps daily: `ours` (sync the two active
# submissions) and `board` (one leaderboard snapshot/day, already idempotent). `top`
# and `manifest` are heavier (manifest hashes the whole archive on a cold cache; top
# re-syncs `ours` too) — run those by hand, or add a second, less frequent
# StartCalendarInterval entry once the first snapshot's cost is known:
#   scripts/archive_sync_launchd.sh top 5 10
#   scripts/archive_sync_launchd.sh manifest
#
# Exit code is the *last failing* subcommand's, so launchd's own failure counters
# (and `log show --predicate 'process == "com.straf.kaggriculture.archive-sync"'`)
# reflect real trouble, not just "nothing new today".

set -uo pipefail

REPO="/Users/straf/Python/Kaggriculture"
PY="$REPO/.venv/bin/python3"
LOG_DIR="$REPO/data/archive/logs"
mkdir -p "$LOG_DIR"

cd "$REPO" || exit 1

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

if [ "$#" -gt 0 ]; then
    log "archive_sync $* starting"
    "$PY" analysis/archive_sync.py "$@"
    rc=$?
    log "archive_sync $* exited $rc"
    exit "$rc"
fi

status=0

log "archive_sync ours starting"
"$PY" analysis/archive_sync.py ours --limit 300
rc=$?
log "archive_sync ours exited $rc"
[ "$rc" -ne 0 ] && status=$rc

log "archive_sync board starting"
"$PY" analysis/archive_sync.py board
rc=$?
log "archive_sync board exited $rc"
[ "$rc" -ne 0 ] && status=$rc

log "archive_sync run complete, exit $status"
exit "$status"
