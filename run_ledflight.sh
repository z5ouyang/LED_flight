#!/usr/bin/env bash
cd "$(dirname $0)"
pkill -f led_flight.py #2>/dev/null || true
source ledflight/bin/activate
nohup python -u led_flight.py &> log &
echo "pid: $!" >> log
deactivate
