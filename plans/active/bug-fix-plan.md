# LED Flight Bug Fix Plan

## Status

| Field | Value |
|-------|-------|
| Stage | active |
| Type | plan |
| Created | 2026-04-04 15:38 |
| Last Updated | 2026-04-04 17:20 |
| Author | Unknown |
| Approver | Tim |
| Plan Review | completed |
| Review Date | 2026-04-04 |
| PM Review | not-required |
| PM Review Date | - |
| Execution Approved | no |
| Execution Approved By | - |
| Execution Started | - |
| AI Developer Ready | yes |
| AI Developer Ready By | Tim |
| AI Developer Ready Date | 2026-04-04 |
| AI Developer Ready Iteration | 1 |
| Implementation Verified | no |
| Implementation Verified By | - |
| Implementation Verified Date | - |
| Remediation Plan | - |
| Last Run | - |
| Last Result | - |
| Run Count | 0 |

### Progress Log

| Timestamp | Stage | active |
|-----------|-------|-------|
| 2026-04-04 15:38 | draft | Plan created |

---



## Context

LED_flight is a flight-tracking project that displays nearby aircraft on LED signs. Two targets exist:
- **CircuitPython MatrixPortal S3** (`code.py`) — small LED matrix, self-contained
- **Raspberry Pi / DietPi** (`led_flight.py`) — drives a Modbus LED sign via serial

The Pi version is deployed at `/opt/LED_flight/` on a DietPi ARM64 device (Debian 12, Python 3.11). It's the actively running target and where all production bugs manifest.

**Production issues observed:**
- 33 crashes in 8 days (all `TypeError: 'NoneType' is not subscriptable` — deployed code lacked null guards)
- Memory leak from bare `requests.get()` in `flight_api.py` (~200 bytes/iteration from orphaned urllib3 connection pools) plus unclosed HTTP response in sunrise API call
- 2 orphan processes (old watchdog never cleaned up)
- 5 ASCII encoding errors on non-ASCII airline/city names
- 1 watchdog timeout at startup from modbus errors

**Local vs deployed state:** The local git repo (post-TIM-onboarding refactor, commit `8973c2c`) already contains null guards that fix the 33 crashes (Fix 1) and the timezone null guard (Fix 5). These fixes exist in local code but have NOT been deployed to the device. Deploying the current local code resolves those production crashes. The remaining fixes in this plan address bugs still present in the local code.

---

## Fixes

### Fix 1: Null dereferences — ALREADY FIXED in local code (deploy only)

**Files:** `led_flight.py`
**Status:** Already resolved by TIM onboarding refactor (commit `8973c2c`). All `get_flight_short()` call sites now have proper null guards:
- Line 265-268: `clear_flight()` — `if flight is None: ml.clear_screen(); return`
- Line 314-315: `_follow_previous_flight()` — `if fshort is not None and int(fshort["altitude"]) < ut.LANDING_ALTITUDE:`
- Line 350: `_resolve_flight()` — `if findex is not None and fshort is not None:`

**Action:** No code changes needed. Deploy current local code to resolve all 33 production crashes.

### Fix 2: Memory leak — orphaned connection pools and unclosed response

**Files:** `flight_api.py`, `led_flight.py`

**2a — Primary leak (~200 bytes/iteration):** `get_request_response()` in `flight_api.py:74` uses bare `requests.get()` which creates a new urllib3 connection pool and HTTPAdapter per call. `response.close()` (line 78) closes the response but NOT the connection pool. With ~2 HTTP calls per main loop iteration, pools accumulate at ~200 bytes/iteration.

Fix: create a module-level `requests.Session()` in `flight_api.py` and use it for all HTTP calls. Sessions reuse connection pools.

```python
# Add at module level in flight_api.py (after imports):
_session = requests.Session()
_session.headers.update(HTTP_HEADERS)

# Change get_request_response() (lines 67-84):
# Current:
def get_request_response(
    requests: types.ModuleType,
    url: str,
    DEBUG_VERBOSE: bool = False,
    timeout: int = 5,
) -> dict[str, Any] | None:
    try:
        response = requests.get(
            url=url, headers=HTTP_HEADERS, timeout=timeout
        )
        response_json = response.json()
        response.close()
        gc.collect()
    except Exception as e:
        logger.debug("Request failed", exc_info=e)
        return None
    result: dict[str, Any] = response_json
    return result

# Fix:
def get_request_response(
    requests: types.ModuleType,
    url: str,
    DEBUG_VERBOSE: bool = False,
    timeout: int = 5,
) -> dict[str, Any] | None:
    try:
        response = _session.get(url=url, timeout=timeout)
        response_json = response.json()
        response.close()
    except Exception as e:
        logger.debug("Request failed", exc_info=e)
        return None
    return response_json
```

Note: the `requests` parameter is retained for backward compatibility but the session is used internally. `HTTP_HEADERS` are set on the session once instead of per-request. `gc.collect()` removed from here — it's already called in the main loop (led_flight.py:375).

**2b — Secondary leak (once/day):** `_update_sunrise()` in `led_flight.py` (lines 130-135) never closes its response object. This also uses bare `requests.get()` (not flight_api's function).

The function `_update_sunrise()` (lines 121-138) already has a try/except wrapping the entire body. The response close must be nested inside:

```python
# Current (lines 121-138):
def _update_sunrise(dt: datetime, geo_loc: list[float]) -> None:
    global LED_SUN_RISE
    try:
        params: dict[str, str] = {
            "lat": str(geo_loc[0]),
            "lng": str(geo_loc[2]),
            "date": dt.date().isoformat(),
            "formatted": "0",
        }
        response = requests.get(
            "https://api.sunrise-sunset.org/json",
            params=params,
            timeout=10,
        )
        sunrise = datetime.fromisoformat(response.json()["results"]["sunrise"]).astimezone(TZ)
        LED_SUN_RISE = {dt.date().isoformat(): sunrise}
    except (requests.RequestException, KeyError, ValueError):
        LED_SUN_RISE = None

# Fix: add try/finally INSIDE the existing try/except to ensure response.close():
def _update_sunrise(dt: datetime, geo_loc: list[float]) -> None:
    global LED_SUN_RISE
    try:
        params: dict[str, str] = {
            "lat": str((geo_loc[0] + geo_loc[1]) / 2),
            "lng": str((geo_loc[2] + geo_loc[3]) / 2),
            "date": dt.date().isoformat(),
            "formatted": "0",
        }
        response = requests.get(
            "https://api.sunrise-sunset.org/json",
            params=params,
            timeout=10,
        )
        try:
            sunrise = datetime.fromisoformat(response.json()["results"]["sunrise"]).astimezone(TZ)
            LED_SUN_RISE = {dt.date().isoformat(): sunrise}
        finally:
            response.close()
    except (requests.RequestException, KeyError, ValueError):
        LED_SUN_RISE = None
```

Note: the geo_loc center fix (`geo_loc[0]` → `(geo_loc[0]+geo_loc[1])/2`) is already included in the full function rewrite above. `geo_loc` is `[lat_min, lat_max, lng_min, lng_max]`.

### Fix 3: Process management — unused `main_try()` and missing crash detection

**Files:** `led_flight.py`

**3a — `main_try()` never called:** Line 420 creates the child process with `target=main`, but `main_try` (line 403) wraps `main()` with exception handling and traceback logging. Fix: change line 420 to `target=main_try`.

```python
# Current (line 420):
child_process = multiprocessing.Process(target=main, ...)

# Fix:
child_process = multiprocessing.Process(target=main_try, ...)
```

**3b — Watchdog doesn't detect child crash:** The watchdog loop (lines 386-400) only checks `wdt_pipe.poll()` for heartbeat messages and monitors timeout via `time.time() - last_feed > timeout`. It never calls `child_process.is_alive()`. When the child crashes, the watchdog waits for the full timeout period before `restart_program()` (which calls `os.execv()` to replace the process). Add `is_alive()` check that triggers the same restart path:

```python
# Insert between the pipe check (lines 387-390) and the timeout check (line 391).
# After:
        if wdt_pipe.poll():
            msg = wdt_pipe.recv()
            if msg == "feed":
                last_feed = time.time()
# Add:
        if not child_process.is_alive():
            logger.warning(
                "%s Child process died — restarting immediately",
                datetime.now(TZ),
            )
            child_process.join()
            restart_program()
            sys.exit()
# Before:
        if time.time() - last_feed > timeout:
```

Note: the watchdog does NOT have a respawn loop — it uses `os.execv()` to restart the entire program. A simple `break` would exit the watchdog without restarting.

**3c — `run_ledflight.sh`:** ~~Sync local to match remote.~~ Local already has `pkill` logic (line 3). No changes needed.

### Fix 4: ASCII encoding errors in `modbus_led.py`

**Files:** `modbus_led.py`

Two locations use `txt.encode('ascii')` which crashes on characters like e-acute, n-tilde in airline/city names:
- `show_text()` function: line 189 (`CNT`), line 193 (`txt.encode('ascii')`)
- `create_txt_programe()` function: line 300 (`txt.encode('ascii')`)

**Display charset constraint:** The JL4Z LED display uses GB2312 encoding (see `resources/JL4Z/`). GB2312 treats bytes 0xA1-0xF7 as the first byte of a double-byte Chinese character. Sending latin-1 bytes (0x80-0xFF) would corrupt the entire message — the display would consume adjacent bytes as part of a GB2312 pair. **latin-1 is NOT safe for this display.** Only ASCII (0x00-0x7F) is safe as single-byte text.

**Fix approach:** Strip accents via Unicode decomposition (NFKD), then encode ASCII. This preserves readability: "Müller"→"Muller", "São Paulo"→"Sao Paulo". Add a helper at module level:

```python
# Add near top of modbus_led.py (after imports):
import unicodedata

def _safe_ascii(txt: str) -> bytes:
    """Strip accents and encode to ASCII for GB2312 display."""
    normalized = unicodedata.normalize("NFKD", txt)
    return normalized.encode("ascii", errors="replace")
```

Then update both encoding sites:

```python
# In show_text() — lines 189-194:
# Current:
    CNT = int(len(txt)).to_bytes(2, byteorder="little")
    get_response(
        GID,
        b"\x38\x02",
        X + Y + W + H + FORMAT + CNT + txt.encode("ascii"),
    )

# Fix:
    txt_bytes = _safe_ascii(txt)
    CNT = int(len(txt_bytes)).to_bytes(2, byteorder="little")
    get_response(
        GID,
        b"\x38\x02",
        X + Y + W + H + FORMAT + CNT + txt_bytes,
    )

# In create_txt_programe() — lines 295-300:
# Current:
    CNT = int(len(txt)).to_bytes(2, byteorder="little")
    ...
        get_response(GID, b"\x10\x03", WID + REV + STYLE + FORMAT + TIMING + CNT + txt.encode("ascii"))

# Fix:
    txt_bytes = _safe_ascii(txt)
    CNT = int(len(txt_bytes)).to_bytes(2, byteorder="little")
    ...
        get_response(GID, b"\x10\x03", WID + REV + STYLE + FORMAT + TIMING + CNT + txt_bytes)
```

### Fix 5: Null guard in `get_time_zone_offset()` — ALREADY FIXED in local code (deploy only)

**Files:** `flight_api.py` (re-exported via `utility.py`)
**Status:** Already resolved. Line 361 in `flight_api.py` reads: `if tInfo is not None and tInfo["status"] == "OK":` — the null guard exists.

**Action:** No code changes needed. Deploy current local code.

### Fix 6: Mismatched exception handlers in `led_flight.py`

**Files:** `led_flight.py`

Two locations catch `subprocess.CalledProcessError` where the try block cannot raise it:

**6a — `set_time_zone()` (line 107):** `ZoneInfo()` (line 106) raises `KeyError` for invalid timezone names, but the except clause catches `subprocess.CalledProcessError`. The error message also says "Ping failed" — copy-pasted from an unrelated function.

```python
# Current (line 107-108):
except subprocess.CalledProcessError as e:
    logger.debug("Ping failed: %s", e.output.decode())

# Fix:
except Exception as e:
    logger.debug("Time zone error: %s", e)
```

On failure, `TZ` retains its module-level default (`ZoneInfo("America/Los_Angeles")` at line 30) — safe fallback.

**6b — `init()` (line 303):** The try block (lines 288-302) contains modbus LED calls (`ml.get_GID()`, `ml.create_canvas()`, etc.) which raise `serial.SerialException` or `OSError`, plus `set_time_zone()` (which raises `KeyError`/`Exception`). `check_wifi()` handles its own subprocess exceptions internally. Nothing in this block can raise `subprocess.CalledProcessError`.

```python
# Current (line 303-304):
except subprocess.CalledProcessError as e:
    logger.debug("LED controller failed: %s", e.output.decode())
    return False

# Fix:
except Exception as e:
    logger.debug("Init failed: %s", e)
    return False
```

This is the "1 watchdog timeout at startup from modbus errors" observed in production — modbus serial errors during init go uncaught because the wrong exception type is caught, crashing the child. The watchdog then times out waiting for a heartbeat that never comes.

### Fix 7: KD-tree distance unit mismatch (`kdnode.py:93`)

**Files:** `kdnode.py`

Line 93 compares `distance_haversine(target, node.point, axis)` (miles) against `best[-1]` (sum of squared coordinate differences from `distance_sq()`, lines 63-68). The pruning heuristic compares values in completely different units.

`distance_sq()` returns `sum([(a[i] - b[i]) ** 2 for i in range(dimensions)])` — dimensionless squared differences. `distance_haversine()` returns miles. These are not comparable.

Note: `distance_haversine()` with an `axis` parameter computes a projected 1D distance (e.g., `69 * abs(lat1-lat2)` for axis 0), not full haversine. But the result is still in miles, while `best[-1]` is in squared-degree units — still incomparable.

Fix: use single-axis squared difference for pruning (standard KD-tree heuristic — if single-axis distance exceeds total best, the subtree cannot contain a closer point):
```python
# Line 93 — change:
if distance_haversine(target, node.point, axis) < best[-1]:

# To:
if (target[axis] - node.point[axis]) ** 2 < best[-1]:
```

Also fix line 94: missing `dimensions` parameter in recursive call (currently defaults to 2, which happens to be correct for lat/lng, but is a latent bug):
```python
# Line 94 — change:
best = nearest(opposite_branch, target, depth + 1, best)

# To:
best = nearest(opposite_branch, target, depth + 1, best, dimensions)
```

### Fix 8: Serial port resource leak (`modbus_led.py:send_modbus()`)

**Files:** `modbus_led.py`

`send_modbus()` (lines 22-36) opens a serial port and calls `ser.close()` at line 35, but if an exception occurs between open and close, the port is leaked. Convert to context manager:

```python
# Current (lines 22-36):
def send_modbus(tx_data: bytes) -> bytes:
    ser = serial.Serial(
        port=PORT,
        baudrate=BAUDRATE,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        bytesize=serial.EIGHTBITS,
        timeout=1,
    )
    ser.reset_input_buffer()
    ser.write(tx_data)
    time.sleep(0.1)
    rx_data = ser.read_all()
    ser.close()
    return rx_data if rx_data is not None else b""

# Fix — context manager ensures close on exception, preserve None guard:
def send_modbus(tx_data: bytes) -> bytes:
    with serial.Serial(
        port=PORT,
        baudrate=BAUDRATE,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        bytesize=serial.EIGHTBITS,
        timeout=1,
    ) as ser:
        ser.reset_input_buffer()
        ser.write(tx_data)
        time.sleep(0.1)
        rx_data = ser.read_all()
    return rx_data if rx_data is not None else b""
```

### Fix 9: Minor fixes

**9a — REMOVED:** No `@staticmethod` decorator exists on `calculate_modbus_crc()` in `modbus_led.py`. Bug does not exist.

**9b — `code.py:83,85`:** Change `res.txt` to `res.text` (2 occurrences in `git_sync` function). `res.txt` is not a valid attribute on the response object — should be `res.text`.

**9c — `code.py:298-299`:** `icon_data` is assigned from `pi.get_plane_horizontal()` but never used. Line 299 calls `pi.get_plane_horizontal()` again as the first arg to `get_BMP()`.
```python
# Current (lines 298-299):
icon_data = pi.get_plane_horizontal()
get_BMP(pi.get_plane_horizontal(), planeBmp)

# Fix:
icon_data = pi.get_plane_horizontal()
get_BMP(icon_data, planeBmp)
```

**9d — REMOVED:** No bare `except:` clauses exist in `led_flight.py`. All exception handlers use specific types.

---

## Verification

1. **Before deploying:** Test locally that `led_flight.py` imports cleanly with `python -c "import led_flight"` (catches syntax errors, wrong exception types).

2. **Deploy to device:**
   - SSH in, stop current processes: `pkill -9 -f led_flight.py`
   - Pull/copy updated files
   - Run `./run_ledflight.sh`
   - Monitor log: `tail -f /opt/LED_flight/log`

3. **Verify Fix 1 (null derefs — already in local code):** After deploying, check `grep -c TypeError log` stays at 0 over 24+ hours. The null guards from the TIM refactor should eliminate the 33-crash pattern.

4. **Verify Fix 2 (memory leak):** Monitor `tracemalloc` output in log over 30+ minutes. Memory should stabilize instead of climbing ~200 bytes/iteration. The session-based connection pooling eliminates the per-request pool creation that was the primary leak source.

5. **Verify Fix 3 (process mgmt):** After running for a while, `ps aux | grep led_flight` should show exactly 2 processes (parent watchdog + child worker). If the child crashes, watchdog should restart it within seconds (not wait for full timeout).

6. **Verify Fix 4 (encoding):** Wait for a flight with non-ASCII characters or test manually by temporarily hardcoding a flight name with accented characters.

7. **Verify Fix 6a (set_time_zone exception):** If the timezone lookup fails, the error should be caught and logged as "Time zone error:" instead of crashing with an uncaught `KeyError`.

8. **Verify Fix 6b (init exception):** Disconnect the Modbus LED sign's serial cable and start the program. It should log "Init failed:" and return False (triggering retry), NOT crash with an uncaught `serial.SerialException`. Reconnect the cable afterward.

9. **Verify Fix 7 (KD-tree):** After deploying, check that nearest-airport lookups return reasonable results. In the log, airport codes for nearby flights should match expected airports (e.g., flights near LAX should resolve to LAX, not a distant airport). The unit mismatch could have caused the KD-tree to prune valid subtrees, returning incorrect nearest neighbors.

10. **Verify Fix 8 (serial port):** Monitor for serial port errors in the log. If a Modbus communication error occurs, subsequent writes should still work (port properly released by context manager). Previously, a leaked port could block all subsequent serial communication until program restart.

11. **Verify Fix 9b (code.py):** On the MatrixPortal, trigger git_sync and confirm the file download completes without AttributeError on `res.txt`.

12. **Verify Fix 9c (code.py):** Confirm `pi.get_plane_horizontal()` is only called once during initialization (not twice). Visual verification: the plane icon renders correctly on the LED matrix.

---

## Order of Implementation

1. Fix 1 (null derefs) — **deploy only**, already fixed in local code
2. Fix 5 (timezone null guard) — **deploy only**, already fixed in local code
3. Fix 3 (process mgmt) — uses main_try, adds crash detection
4. Fix 6 (wrong exception type) — makes error handling work
5. Fix 2 (memory leak + geo_loc) — session pooling, response close, correct coordinates
6. Fix 4 (encoding) — stops ASCII errors on accented names
7. Fix 7 (KD-tree units) — correctness of airport lookup
8. Fix 8 (serial port leak) — resource safety
9. Fix 9b-c (minor) — code.py attribute fix and dead code removal

**Removed from plan:** Fix 9a (no @staticmethod exists), Fix 9d (no bare except exists)
