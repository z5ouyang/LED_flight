# LED Flight

## Overview
LED flight tracker with dual runtime: CircuitPython (Adafruit MatrixPortal S3) + standard Python (Linux host).

## File Categories
- **CircuitPython** (`code.py`, `plane_icon.py`): Runs on microcontroller. No mypy, no type annotations, use `print()` for output. Linted by pylint with `.pylintrc-circuitpython`.
- **Standard Python** (all other `.py` files): Runs on Linux. Full TIM enforcement: mypy --strict, ruff, bandit, logging (not print).
- **`lib/`**: Precompiled `.mpy` CircuitPython libraries — binary, never modify, never lint.

## What This Project Does NOT Have
- No k8s, no ops.sh, no database, no deploy pipeline, no Dockerfile
- No web framework, no API served, no auth
- No tim-lib (standalone hardware project)

## Deployment
Manual: copy CircuitPython files to device via USB, run standard Python on Linux host via `run_ledflight.sh`.

## External Dependencies
- Flightradar24 API (read-only flight data)
- TimezoneDB API (timezone lookups)
- sunrise-sunset.org API (daylight times)

## TIM Exceptions
The following TIM requirements do not apply to this project:
- **No tim-lib**: Standalone hardware project, no web framework
- **No Dockerfile**: Not containerized
- **No ops-config.yaml**: Not deployed to k8s
- **No Gate 3**: No deploy pipeline
- **mypy exemption for CircuitPython files**: No type stubs for hardware modules (`board`, `digitalio`, `neopixel`, etc.)

## Security Considerations
- `code.py` downloads Python source from a GitHub raw URL and writes to disk (CircuitPython OTA update pattern) — known supply chain risk if the GitHub account is compromised
- MQTT connection in `code.py` uses `is_ssl=False` — data transmitted unencrypted
- `private.json` contains credentials — gitignored via `*private*` glob
- API responses from Flightradar24/TimezoneDB are deserialized without schema validation
