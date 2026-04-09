---
name: two-device architecture
description: LED_flight runs on two separate devices — DietPi Pi (large display, SSH) and CircuitPython MatrixPortal S3 (small display, serial-only). Most development targets the Pi.
type: project
---

LED_flight has two completely separate runtime targets:

- **DietPi Raspberry Pi** (`led_flight.py`): Large 192×32 RGB LED matrix, connected via Modbus serial (FTDI USB). SSH accessible at `ssh dietpi`. Deployed at `/opt/LED_flight/`. Runs as user `tim`. This is the primary development target.

- **CircuitPython MatrixPortal S3** (`code.py`): Much smaller LED matrix, no SSH — code loaded via serial/USB connection. Has its own MQTT, WiFi, watchdog. Auto-updates from GitHub main via `git_sync()`.

**Why:** Feature work and bug fixes should target the Pi files only (`led_flight.py`, `flight_api.py`, `modbus_led.py`, etc.). Changes to `code.py` should only be bug fixes, and be aware that pushing to main triggers OTA update on the MatrixPortal next time it syncs.

**How to apply:** When the user asks for new features, default to Pi-only. Don't modify `code.py` or `plane_icon.py` unless explicitly asked.
