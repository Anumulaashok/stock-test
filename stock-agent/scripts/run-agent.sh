#!/usr/bin/env bash
set -uo pipefail

BRANCH="feature/stock-intelligence-redesign"
LOGDIR=".agent/logs"; mkdir -p "$LOGDIR"

seconds_until_0450() {
  local now target
  now=$(date +%s)
  if date -d "today 04:50" +%s >/dev/null 2>&1; then
    target=$(date -d "today 04:50" +%s)            # GNU
  else
    target=$(date -j -f "%Y-%m-%d %H:%M" "$(date +%F) 04:50" +%s)  # BSD/macOS
  fi
  (( target <= now )) && target=$(( target + 86400 ))
  echo $(( target - now ))
}

while true; do
  TS=$(date +%F-%H%M); LOG="$LOGDIR/run-$TS.log"
  echo "[$(date)] starting run" | tee -a "$LOG"

  claude -p "Read docs/MASTER_BRIEF.md and docs/AUTONOMY.md in full. \
Read PROGRESS.md and DECISIONS.md to resume. Continue from the current slice. \
Work autonomously per the autonomy contract. Commit and push after every green \
slice. Do not ask questions." >>"$LOG" 2>&1
  STATUS=$?

  if grep -qiE '429|rate.?limit|quota exceeded|overloaded' "$LOG"; then
    WAIT=$(seconds_until_0450)
    echo "[$(date)] rate limited; sleeping ${WAIT}s until 04:50" | tee -a "$LOG"
    sleep "$WAIT"
    continue
  fi

  if grep -q 'ALL WAVES COMPLETE' "$LOG"; then
    echo "[$(date)] done" | tee -a "$LOG"; break
  fi

  if (( STATUS != 0 )); then
    echo "[$(date)] exit $STATUS; retrying in 15m" | tee -a "$LOG"
    sleep 900; continue
  fi

  sleep 60
done
