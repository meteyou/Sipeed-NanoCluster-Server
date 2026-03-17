#!/usr/bin/env bash
set -e

# Start pigpio daemon if we're root and it's not already running
if [ "$(id -u)" = "0" ]; then
  if ! pgrep pigpiod >/dev/null 2>&1; then
    echo "Starting pigpiod..."
    /usr/bin/pigpiod
  fi
fi

case "$1" in
  server)
    shift
    exec python3 /app/server.py "$@"
    ;;
  agent)
    shift
    exec python3 /app/agent.py "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
