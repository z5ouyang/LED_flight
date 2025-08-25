#!/usr/bin/bash
source ledflight/bin/activate
nohup python -u led_flight.py &> log &
echo "pid: $!" >> log
deactivate
