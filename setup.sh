#!/usr/bin/bash
apt install -y python3  python3.11-venv
python3 -m venv ledflight
source ledflight/bin/activate
pip install pyyaml requests pyserial
deactivate
