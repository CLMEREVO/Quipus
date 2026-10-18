#!/usr/bin/env bash
# Start the FastAPI backend.
#
# Recommended: do NOT use this file. Set the Start Command in the platform
# dashboard instead:
#
#     uvicorn main:app --host 0.0.0.0 --port $PORT
#
# If your platform only supports a shell script (or you want to run it
# locally), use:
#
#     bash start.sh              # local, default port 8000
#     PORT=9000 bash start.sh
#
# Two mandatory flags:
#   --host 0.0.0.0   otherwise the platform's health check cannot reach us
#   --port $PORT     the platform assigns the port via env var

set -euo pipefail

exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
