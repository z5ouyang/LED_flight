#!/usr/bin/bash
source ledflight/bin/activate
python -u led_flight.py &> log
deactivate
