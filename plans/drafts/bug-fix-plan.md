# LED Flight Bug Fix Plan

## Context

LED_flight is a flight-tracking project that displays nearby aircraft on LED signs. Two targets exist:
- **CircuitPython MatrixPortal S3** (`code.py`) — small LED matrix, self-contained
- **Raspberry Pi / DietPi** (`led_flight.py`) — drives a Modbus LED sign via serial

The Pi version is deployed at `/opt/LED_flight/` on a DietPi ARM64 device (Debian 12, Python 3.11). It's the actively running target and where all production bugs manifest.

**Production issues observed:**
- 33 crashes in 8 days (all `TypeError: 'NoneType' is not subscriptable` at `led_flight.py:239`)
- Steady memory leak (~200 bytes/loop, climbs from 70KB to 200KB+)
- 2 orphan processes (old watchdog never cleaned up)
- 5 ASCII encoding errors on non-ASCII airline/city names
- 1 watchdog timeout at startup from modbus errors

**Note:** The remote deployed code differs from the local git repo — `run_ledflight.sh` on the device has `pkill` logic the local copy lacks. Changes should be tested against the remote state.

---

## Fixes

### Fix 1: Null dereferences in `led_flight.py` (33 production crashes)

**Files:** `led_flight.py`

**1a — Line 239:** `fshort` can be `None` when `get_flight_short()` fails.
```
# Current (line 239):
if fshort['altitude']<ut.LANDING_ALTITUDE:

# Fix: guard with None check (matches code.py:356 pattern):
if fshort is not None and fshort['altitude']<ut.LANDING_ALTITUDE:
```

**1b — Line 186:** `flight` used before null check on line 187.
```
# Current (line 185-187):
flight = ut.get_flight_short(requests,flight_index,DEBUG_VERBOSE=DEBUG_VERBOSE)
ml.show_text(... flight['flight_number'] ...)  # crashes if None
if flight is not None and flight['altitude']<ut.LANDING_ALTITUDE:

# Fix: add null guard before line 186:
flight = ut.get_flight_short(requests,flight_index,DEBUG_VERBOSE=DEBUG_VERBOSE)
if flight is None:
    ml.show_text(0,16,192,16,"0FF",'Out of Monitor Boundary',font=3)
else:
    ml.show_text(0,0,192,16,"F0F","%s %s-%s %s"%(flight['flight_number'],flight['ori'],flight['dest'],flight['aircraft_type']),font=4)
    if flight['altitude']<ut.LANDING_ALTITUDE:
        ml.show_text(0,16,192,16,"0FF","Landed\t"+str(flight["speed"])+' kts',font=3)
    else:
        ml.show_text(0,16,192,16,"0FF",'Out of Monitor Boundary',font=3)
```

### Fix 2: Memory leak in `led_flight.py:check_brightness()`

**Files:** `led_flight.py`

The `requests.get()` call at line 91 is made every loop iteration but the response is never closed. This is the primary memory leak (~200 bytes/loop).

```
# Current (lines 91-101):
response = requests.get("https://api.sunrise-sunset.org/json", params={...})
sunrise_time = datetime.fromisoformat(response.json()["results"]["sunrise"]).astimezone(TZ)

# Fix: close response, and use try/finally:
response = requests.get("https://api.sunrise-sunset.org/json", params={...})
try:
    sunrise_time = datetime.fromisoformat(response.json()["results"]["sunrise"]).astimezone(TZ)
    LED_SUN_RISE = {dt.date().isoformat():sunrise_time}
finally:
    response.close()
```

Also fix geo_loc indexing (line 95): `"lng": geo_loc[2]` should use center longitude `(geo_loc[2]+geo_loc[3])/2`, and latitude should be `(geo_loc[0]+geo_loc[1])/2`.

### Fix 3: Process management — orphan processes and unused `main_try()`

**Files:** `led_flight.py`, `run_ledflight.sh`

**3a — `main_try()` never called:** Line 294 uses `target=main` but `main_try` (line 281) wraps main() with exception handling. Fix: change line 294 to `target=main_try`.

**3b — Watchdog doesn't detect child crash:** When the child process crashes (33 times!), the watchdog just waits for timeout instead of restarting immediately. Add `child_process.is_alive()` check in the watchdog loop.

**3c — `run_ledflight.sh`:** Sync local to match remote (add `pkill` logic). Improve to also kill zombie children:
```bash
#!/usr/bin/env bash
cd "$(dirname $0)"
pkill -f led_flight.py 2>/dev/null || true
sleep 1
pkill -9 -f led_flight.py 2>/dev/null || true
source ledflight/bin/activate
nohup python -u led_flight.py &> log &
echo "pid: $!" >> log
deactivate
```

### Fix 4: ASCII encoding errors in `modbus_led.py`

**Files:** `modbus_led.py`

Lines 144 and 229 use `txt.encode('ascii')` which crashes on characters like e-acute, n-tilde in airline/city names. Also need to fix `CNT` to count bytes not characters.

```
# Line 144 and 229 — change:
CNT = int(len(txt)).to_bytes(2,byteorder='little')
... txt.encode('ascii')

# To:
txt_bytes = txt.encode('latin-1', errors='replace')
CNT = int(len(txt_bytes)).to_bytes(2,byteorder='little')
... txt_bytes
```

### Fix 5: Null guard in `utility.py:get_time_zone_offset()`

**Files:** `utility.py`

Line 227: `tInfo['status']` crashes if `get_request_response()` returns `None`.

```
# Add before line 227:
if tInfo is None:
    return None, None
```

### Fix 6: `set_time_zone` catches wrong exception (`led_flight.py:79`)

**Files:** `led_flight.py`

`ZoneInfo()` raises `KeyError`, not `subprocess.CalledProcessError`. Also fix the dead error message ("Ping failed" in a timezone function).

```
# Change line 79:
except subprocess.CalledProcessError as e:
    if DEBUG_VERBOSE:
        print(f"Ping failed: {e.output.decode()}")

# To:
except (KeyError, Exception) as e:
    if DEBUG_VERBOSE:
        print(f"Time zone error: {e}")
```

### Fix 7: KD-tree distance unit mismatch (`kdnode.py:62`)

**Files:** `kdnode.py`

Line 62 compares `distance_haversine()` (miles) against `best[-1]` (degrees-squared from `distance_sq()`). The pruning heuristic uses inconsistent units.

Fix: use `distance_sq` for the pruning comparison too, keeping the same unit throughout:
```
# Line 62 — change:
if distance_haversine(target,node.point,axis) < best[-1]:

# To:
if (target[axis] - node.point[axis])**2 < best[-1]:
```

This compares single-axis squared-degree distance against the best squared-degree distance — consistent units, and cheap to compute.

### Fix 8: Serial port resource leak (`modbus_led.py:send_modbus()`)

**Files:** `modbus_led.py`

Lines 20-27: serial port not closed on exception.

```
# Change to context manager:
def send_modbus(tx_data):
    with serial.Serial(port=PORT,baudrate=BAUDRATE,parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,bytesize=serial.EIGHTBITS,timeout=1) as ser:
        ser.reset_input_buffer()
        ser.write(tx_data)
        time.sleep(0.1)
        rx_data = ser.read_all()
    return rx_data
```

### Fix 9: Minor fixes

**9a — `modbus_led.py:261`:** Remove `@staticmethod` from module-level `calculate_modbus_crc()` (or delete if unused).

**9b — `code.py:58-60`:** Change `res.txt` to `res.text` (2 occurrences in git_sync).

**9c — `code.py:240`:** Remove unused `icon_data` variable (get_plane_horizontal called twice).

**9d — `led_flight.py:37,102`:** Change bare `except:` to `except Exception:`.

---

## Verification

1. **Before deploying:** Test locally that `led_flight.py` imports cleanly with `python -c "import led_flight"` (catches syntax errors, wrong exception types, @staticmethod issue).

2. **Deploy to device:**
   - SSH in, stop current processes: `pkill -9 -f led_flight.py`
   - Pull/copy updated files
   - Run `./run_ledflight.sh`
   - Monitor log: `tail -f /opt/LED_flight/log`

3. **Verify Fix 1 (null derefs):** Wait for a period with no flights in the zone, then watch for the follow-previous-plane logic to trigger. Should no longer crash. Check `grep -c TypeError log` stays at 0.

4. **Verify Fix 2 (memory leak):** Monitor "Current: N bytes" in log over 30+ minutes. Memory should stabilize instead of climbing monotonically.

5. **Verify Fix 3 (process mgmt):** After running for a while, `ps aux | grep led_flight` should show exactly 2 processes (parent watchdog + child worker), not accumulating.

6. **Verify Fix 4 (encoding):** Wait for a flight with non-ASCII characters or test manually by temporarily hardcoding a flight name with accented characters.

---

## Order of Implementation

1. Fix 1 (null derefs) — stops the 33-crashes-in-8-days problem
2. Fix 2 (memory leak) — stops the steady memory growth
3. Fix 3 (process mgmt) — stops orphan accumulation, uses main_try
4. Fix 4 (encoding) — stops ASCII errors on accented names
5. Fix 5 (timezone null guard) — prevents potential crash
6. Fix 6 (wrong exception type) — makes error handling work
7. Fix 7 (KD-tree units) — correctness of airport lookup
8. Fix 8 (serial port leak) — resource safety
9. Fix 9a-d (minor) — cleanup
