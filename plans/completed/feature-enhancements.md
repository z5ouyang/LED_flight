# Feature Enhancements Plan

## Status

| Field | Value |
|-------|-------|
| Stage | completed |
| Type | plan |
| Created | 2026-04-05 |
| Last Updated | 2026-04-05 11:48 |
| Author | Tim / Claude |
| Approver | Tim |
| Plan Review | completed |
| Review Date | 2026-04-05 |
| PM Review | not-required |
| PM Review Date | - |
| Execution Approved | no |
| Execution Approved By | - |
| Execution Started | - |
| AI Developer Ready | yes |
| AI Developer Ready By | Tim |
| AI Developer Ready Date | 2026-04-05 |
| AI Developer Ready Iteration | 1 |
| Implementation Verified | yes |
| Implementation Verified By | Tim |
| Implementation Verified Date | 2026-04-05 |
| Remediation Plan | - |
| Last Run | - |
| Last Result | - |
| Run Count | 0 |

### Progress Log

| Timestamp | Stage | completed |
|-----------|-------|------|
| 2026-04-05 | draft | Plan created |

---

## Scope

**Target device: DietPi (Raspberry Pi) only.** The CircuitPython MatrixPortal S3 is a separate, smaller device with no SSH access — code is loaded via serial/USB. All changes in this plan apply only to the Pi-hosted files (`led_flight.py`, `flight_api.py`, `modbus_led.py`, etc.). Do not modify `code.py` or `plane_icon.py`.

---

## Current Display Layout (DO NOT CHANGE)

The 192×32 pixel LED display has three canvases. Existing sizes, positions, and font choices must be preserved.

```
┌──────────────────────────────────────────────────────────────┐
│  SHORT_CANVAS (64×16 at 0,0)  │         (upper area)        │  Row 0-15
│  font=4, multiline            │  alt/speed or date/weekday  │
├──────────────────────────────────────────────────────────────┤
│  LONG_CANVAS (192×16 at 0,16) — scrolling text              │  Row 16-31
│  font=3, centered, scrolling airline/aircraft info           │
└──────────────────────────────────────────────────────────────┘
PLANE_CANVAS (192×32 at 0,0) — full screen overlay for plane animation
```

### Current display states

**Idle (no flight):**
```
[Apr 5  ]        [  Sat  ]     row 0-15:  date (0,0,64,16) + weekday (128,0,64,16)  yellow FF0 font=4
         [ 17:33 ]              row 16-31: time (64,16,64,16)  yellow FF0 font=4
```

**Flight active — initial info:**
```
[UA123 ][SAN-LAX][A320]        row 0-15: SHORT_CANVAS cycling labels  magenta F0F font=4
[  United Airlines  SAN Diego-Los Angeles  Airbus A320  ]  row 16-31: LONG_CANVAS scrolling  magenta F0F font=3
```

**Flight active — tracking:**
```
[plane_img] [  3200ft 250kts ]  row 0-15: plane icon + alt/speed  yellow FF0 font=3
[  (LONG_CANVAS continues)   ]  row 16-31: still scrolling
```

**Flight exiting boundary:**
```
[UA123 SAN-LAX A320          ]  row 0-15: full width summary  magenta F0F font=4
[Landed  120 kts             ]  row 16-31: status  cyan 0FF font=3
  — or —
[Out of Monitor Boundary     ]  row 16-31: if not landed  cyan 0FF font=3
```

---

## Feature 1: Daily Flight Counter

### What
Show a running count of unique flights seen today in the idle display. Resets at midnight.

### Display placement
Replace the currently empty space in the idle display. The date is at (0,0,64,16) and weekday at (128,0,64,16) — the gap between them (64,0,64,16) is unused. Put the count there.

```
Idle (with counter):
[Apr 5  ][ 14 flt ][  Sat  ]     row 0-15
         [ 17:33 ]              row 16-31
```

The display only renders ASCII (GB2312). Use "14 flt" as the display text — `✈` would render as `?`.

### Implementation

**Data tracking:**
- Add a module-level set `FLIGHTS_TODAY: set[str] = set()` to track unique flight IDs seen today
- Add a module-level `FLIGHTS_TODAY_DATE: str = ""` to track which day the counter is for
- In `_resolve_flight()` at line 349, inside the `if findex != findex_old:` block, add:
  ```python
  if findex is not None:
      FLIGHTS_TODAY.add(findex)
  ```
  This fires exactly once per new flight detection.
- In the main `while True` loop (line 367), at the top of each iteration, add:
  ```python
  today = datetime.now(TZ).date().isoformat()
  if today != FLIGHTS_TODAY_DATE:
      FLIGHTS_TODAY.clear()
      FLIGHTS_TODAY_DATE = today
  ```
  This handles midnight rollover.
- Both globals need `global FLIGHTS_TODAY, FLIGHTS_TODAY_DATE` declarations in the functions that modify them.

**Display:**
- In `display_date_time()`, add a third `ml.show_text()` call:
  ```python
  count = len(FLIGHTS_TODAY)
  ml.show_text(64, 0, 64, 16, "FF0", f"{count} flt", font=4)
  ```
- This fits in the gap between the date and weekday at position (64,0,64,16), same yellow color and font. "flt" suffix keeps the number readable even at 0 ("0 flt").

**Files:** `led_flight.py` only.

### Edge cases
- Midnight rollover: check date at loop start, reset counter
- Same flight re-entering zone: set deduplicates by flight index
- No flights all day: shows "0"
- Counter persists across watchdog restarts within the same day (since `os.execv` replaces the process, the counter resets — acceptable since the new process starts fresh)

---

## Feature 2: Local Airport Arrival/Departure Context

### What
Replace the generic "Out of Monitor Boundary" message with context-aware messages relative to the local airport:
- "Arriving SAN" — plane is heading toward the local airport
- "Departing SAN" — plane is leaving the local airport
- "From LAX" — plane is arriving from a non-local origin
- "To LAX" — plane is heading to a non-local destination

### Determining the local airport
Use the center of `geo_loc` from config to find the nearest airport via the existing KD-tree (`kd.nearest()`). This is the "local" airport. Compute once at init and store as a module-level variable.

### Logic
When a flight exits the boundary or is in the `clear_flight()` display:

1. Get `flight['ori']` and `flight['dest']` (origin and destination IATA codes)
2. Compare against local airport IATA code:
   - If `dest == local_airport`: display "Arriving {local_airport}" (cyan)
   - If `ori == local_airport`: display "Departing {local_airport} -> {dest}" (cyan)
   - If neither matches: display "{ori} -> {dest}" (cyan, current behavior essentially)

### Display placement
This replaces the text on row 16-31 in the flight-exiting state. Currently shows "Landed\t120 kts" or "Out of Monitor Boundary" at (0,16,192,16) in cyan font=3.

```
Flight exiting (arriving local):
[UA123 SAN-LAX A320          ]  row 0-15
[Arriving SAN  120 kts       ]  row 16-31  cyan 0FF font=3

Flight exiting (departing local):
[UA123 SAN-LAX A320          ]  row 0-15
[Departing SAN -> LAX         ]  row 16-31  cyan 0FF font=3
```

When landed (altitude < LANDING_ALTITUDE), keep showing speed: "Arriving SAN  120 kts" or "Landed  120 kts".

### Implementation

**Init:**
- In `init()`, after loading config, compute local airport:
  ```python
  center_lat = (config["geo_loc"][0] + config["geo_loc"][1]) / 2
  center_lng = (config["geo_loc"][2] + config["geo_loc"][3]) / 2
  local_airport_info = kd.nearest(kd.IATA_INFO, [center_lat, center_lng])
  LOCAL_AIRPORT = local_airport_info[2] if local_airport_info else ""
  ```
- KD-tree node points are `[lat, lng, iata_code, municipality_region]`. Index [2] is the IATA code. `nearest()` returns `node.point + [distance]`, so index [2] is correct.
- Store as module-level `LOCAL_AIRPORT: str = ""`
- Must declare `global LOCAL_AIRPORT` inside `init()`

**clear_flight() changes (lines 281-284):**
Replace the current altitude check logic:
```python
# Current:
if flight["altitude"] < ut.LANDING_ALTITUDE:
    ml.show_text(0, 16, 192, 16, "0FF", "Landed\t" + str(flight["speed"]) + " kts", font=3)
else:
    ml.show_text(0, 16, 192, 16, "0FF", "Out of Monitor Boundary", font=3)

# Replacement:
status_text = _flight_exit_message(flight)
ml.show_text(0, 16, 192, 16, "0FF", status_text, font=3)
```

**New helper function:**
```python
def _flight_exit_message(flight: dict[str, Any]) -> str:
    """Build context-aware exit message based on local airport."""
    ori = flight.get("ori", "NA")
    dest = flight.get("dest", "NA")
    landed = flight["altitude"] < ut.LANDING_ALTITUDE
    speed_str = str(flight["speed"]) + " kts"

    if LOCAL_AIRPORT and dest == LOCAL_AIRPORT:
        # Top row already shows "UA123 LAX-SAN A320" with origin visible
        if landed:
            return f"Arriving {LOCAL_AIRPORT}\t{speed_str}"
        if ori != "NA":
            return f"Arriving {LOCAL_AIRPORT} from {ori}"
        return f"Arriving {LOCAL_AIRPORT}"
    if LOCAL_AIRPORT and ori == LOCAL_AIRPORT:
        if dest != "NA":
            return f"Departing {LOCAL_AIRPORT} -> {dest}"
        return f"Departing {LOCAL_AIRPORT}"
    if landed:
        return f"Landed\t{speed_str}"
    if ori != "NA" and dest != "NA":
        return f"{ori} -> {dest}"
    return "Out of Monitor Boundary"
```

**Files:** `led_flight.py` only. Uses existing `kd.nearest()` and `kd.IATA_INFO`.

### Edge cases
- Local airport not found (empty IATA_INFO): fall back to current "Out of Monitor Boundary" text
- Flight origin/destination unknown ("NA"): fall back to current text
- Flight to/from the same local airport (touch-and-go): show "Arriving {local}"

---

## Feature 3: Altitude-Based Color Coding

### What
Color the flight info text based on altitude to give a visual sense of how high the plane is:
- **Green (0F0)**: below 3,000 ft — on approach/departure, close to ground
- **Yellow (FF0)**: 3,000–15,000 ft — climbing or descending through the zone
- **Red (F00)**: above 15,000 ft — cruising, passing over at altitude

### Where it applies
Only the **alt/speed display** in `display_alt_sp()` and the **flight info** in `show_flight()` / `clear_flight()`. The date/time display stays yellow. The scrolling LONG_CANVAS text stays magenta.

Specifically:
- `display_alt_sp()`: the altitude/speed text color changes based on current altitude (currently hardcoded "FF0")
- `clear_flight()`: the top-row flight summary color changes (currently hardcoded "F0F")
- `show_flight()`: the SHORT_CANVAS and LONG_CANVAS program colors could optionally change, but since these are created once and the altitude changes over time, it's simpler to only apply color to the real-time `display_alt_sp()` call. Leave `show_flight()` as magenta.

### Implementation

**Helper function:**
```python
def _altitude_color(altitude: int | str) -> str:
    """Color by altitude: green (low), yellow (mid), red (high)."""
    try:
        alt = int(altitude)
    except (ValueError, TypeError):
        return "FF0"  # default yellow for non-numeric
    if alt < 3000:
        return "0F0"  # green — low/approach
    if alt < 15000:
        return "FF0"  # yellow — mid
    return "F00"      # red — high/cruise
```

Note: accepts both `int` (from `get_flight_short()`) and `str` (from `get_flight_detail()`) since the two data sources use different types.

Color values "0F0", "FF0", "F00" are all valid for `_validate_color()` in `modbus_led.py` (only accepts 3-char hex strings with F and 0 characters).

**Changes:**
- `display_alt_sp()`: replace hardcoded `"FF0"` with `_altitude_color(fInfo['altitude'])` — `fInfo['altitude']` is a string from detailed flight data
- `clear_flight()`: replace hardcoded `"F0F"` in the top row with `_altitude_color(flight['altitude'])` — `flight['altitude']` is an int from short flight data

**Files:** `led_flight.py` only.

### Edge cases
- Altitude is 0 or negative (on ground): green is correct
- Altitude field is "NA" or non-numeric string (from detailed flight data): defaults to yellow
- Altitude is int from short flight data: `int()` is a no-op, works correctly
- Thresholds (3000, 15000) are reasonable for the SAN area where most traffic is approach/departure (LANDING_ALTITUDE_MAX is 4000 in utility.py). These could be made configurable later but hardcoded is fine for now.

---

## Order of Implementation

1. Feature 3 (altitude colors) — smallest change, no new state
2. Feature 1 (flight counter) — adds state tracking, modifies idle display
3. Feature 2 (arrival/departure) — most complex, requires KD-tree lookup at init

---

## Verification

1. **Feature 3**: Watch display with active flight. Color should change as plane descends through the zone (red -> yellow -> green as altitude drops).

2. **Feature 1**: Kill and restart the process. Idle display should show "0" in the gap. Wait for a flight to appear. After it leaves, idle display should show "1". Counter increments for each new unique flight.

3. **Feature 2**: When a flight exits the boundary, the bottom row should say "Arriving SAN" or "Departing SAN -> LAX" instead of "Out of Monitor Boundary". For landing flights, should say "Arriving SAN  120 kts".
