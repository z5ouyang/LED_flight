#!/usr/bin/env bash
cd "$(dirname $0)"
source ledflight/bin/activate
nohup python -u led_flight.py &> log &
echo "pid: $!" >> log
deactivate
