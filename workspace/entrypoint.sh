#!/bin/bash
set -e

SHUT_DOWN="${SHUT_DOWN:-0}"
WORKFLOW_ID="${WORKFLOW_ID:-}"

service ssh start
echo "SSH started"

export DISPLAY=${DISPLAY:-:1}
if [ -x "/dockerstartup/vnc_startup.sh" ]; then
  /dockerstartup/vnc_startup.sh &
  echo "VNC/noVNC stack started via vnc_startup.sh (DISPLAY=$DISPLAY)"
elif [ -x "/dockerstartup/startup.sh" ]; then
  /dockerstartup/startup.sh &
  echo "VNC/noVNC stack started via startup.sh (DISPLAY=$DISPLAY)"
else
  echo "[WARN] No VNC startup script found under /dockerstartup/*. VNC may not start."
fi

# Echo settings (printf avoids issues if values contain quotes)
printf '%s\n' "===== SETTINGS ====="
printf 'WORKDIR: %s\n' "$(pwd)"
printf 'WORKFLOW_ID: %s\n' "${WORKFLOW_ID}"
printf 'SHUT_DOWN: %s\n' "${SHUT_DOWN}"
printf 'DISPLAY: %s\n' "${DISPLAY}"
printf 'PLAYWRIGHT_BROWSERS_PATH: %s\n' "${PLAYWRIGHT_BROWSERS_PATH}"
printf '%s\n' "===================="
printf '%s\n' "===== ENVIRONMENT VARIABLES ====="
env | sort
printf '%s\n' "=================================="

bash bin/setup
echo "Setup completed"

rm -f /workspace/.env
env | sort > /workspace/.env
chmod 600 /workspace/.env || true
echo "Environment variables written to /workspace/.env"

printf 'Running workflow with ID: %s\n' "$WORKFLOW_ID"

if [ "$SHUT_DOWN" = "1" ]; then
    exec bash bin/run --workflow-id "$WORKFLOW_ID" --shut-down-after-run
else
    bash bin/run --workflow-id "$WORKFLOW_ID" || echo "Workflow failed or WORKFLOW_ID not set"
    tail -f /dev/null
fi


