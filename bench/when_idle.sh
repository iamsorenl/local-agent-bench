#!/bin/zsh
# Wait until Ollama has had no models loaded for two checks 5 minutes apart, then run the full benchmark.
cd "${0:A:h}/.."
idle=0
while (( idle < 2 )); do
  if [[ $(ollama ps | tail -n +2 | grep -c .) -eq 0 ]]; then (( idle++ )); else idle=0; fi
  echo "$(date '+%F %T') idle_checks=$idle"
  (( idle < 2 )) && sleep 300
done
echo "$(date '+%F %T') starting benchmark"
uv run python -m bench --fresh 2>&1 | grep -v "Processing request"
echo "$(date '+%F %T') done"
