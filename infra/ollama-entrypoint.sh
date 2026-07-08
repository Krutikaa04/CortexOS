#!/bin/sh
# Start Ollama, then pull required models in the background so startup
# is not deadlocked on a multi-GB download. The API reports "degraded"
# until all required models are present.
set -e

ollama serve &
SERVER_PID=$!

# Wait for the server to accept requests
i=0
until ollama list >/dev/null 2>&1; do
  i=$((i + 1))
  [ "$i" -gt 60 ] && echo "ollama server did not start" && exit 1
  sleep 1
done

(
  IFS=','
  for model in $CORTEX_REQUIRED_MODELS; do
    model=$(echo "$model" | tr -d ' ')
    [ -z "$model" ] && continue
    if ollama list | awk '{print $1}' | grep -q "^${model}"; then
      echo "model already present: $model"
    else
      echo "pulling model: $model"
      ollama pull "$model" || echo "WARN: failed to pull $model (will retry on restart)"
    fi
  done
) &

wait $SERVER_PID
