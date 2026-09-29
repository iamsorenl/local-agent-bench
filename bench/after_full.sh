#!/bin/zsh
# Queued 2026-09-28: runs after the baseline benchmark finishes.
cd "${0:A:h}/.."
while pgrep -f when_idle.sh >/dev/null; do sleep 60; done
echo "$(date '+%F %T') baseline done; reproducing qwen harrow error"
uv run python -c "
import asyncio
from bench.run import run_one
from bench.tasks import TASKS
r = asyncio.run(run_one('qwen3-coder:30b', next(t for t in TASKS if t['id'] == 'harrow')))
print('HARROW_REPRO', r['error'], r['calls'])
" 2>&1 | grep --line-buffered -v "Processing request"
echo "$(date '+%F %T') starting hints variant"
uv run python -m bench --variant hints 2>&1 | grep --line-buffered -v "Processing request"
echo "$(date '+%F %T') done"
