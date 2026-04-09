# OTA Updates

## Status

| Field | Value |
|-------|-------|
| Stage | completed |
| Type | plan |
| Created | 2026-04-05 12:10 |
| Last Updated | 2026-04-05 18:17 |
| Author | Unknown |
| Approver | Tim |
| Plan Review | completed |
| Review Date | 2026-04-05 |
| PM Review | required |
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
|-----------|-------|-------|
| 2026-04-05 12:10 | draft | Plan created |

---



## Context

The MatrixPortal S3 device has a `git_sync()` function in `code.py` (lines 42-68) that was designed to pull updated code from GitHub daily, but it was never enabled because CircuitPython's filesystem is read-only from code by default. The function also has bugs (`res.txt` instead of `res.text`). The goal is to make the device self-updating so you don't need USB to deploy code changes.

**Critical finding:** The repo's `main` branch has diverged from what the device can run. `utility.py` on `main` imports from `flight_api.py` (a standard Python module using `logging`, `requests`, `typing`) which doesn't exist on the device and wouldn't work under CircuitPython. If OTA pulls `utility.py` from `main`, it will brick the device. A dedicated `device` branch is required.

## Steps

Follow these steps in order.

### Step 1: Edit `/Volumes/CIRCUITPY/code.py` (via USB)

All code.py changes happen in this step. Three sub-changes:

**1a. Replace lines 36-38** (the `GIT_COMMIT` dict area):

Device lines 36-38 currently read:
```python
# Git sync not called due to write-only system
GIT_COMMIT={'code.py':'','utility.py':'','plane_icon.py':''}
GIT_DATE=''
```

Replace with:
```python
# OTA: pulls from 'device' branch daily
GIT_DATE=''
GIT_SYNC_FILE = 'git_sync.json'

def _load_git_shas():
    try:
        with open(GIT_SYNC_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}

def _save_git_shas(shas):
    with open(GIT_SYNC_FILE, 'w') as f:
        json.dump(shas, f)
```

**1b. Replace the entire `git_sync()` function** (device lines 42-68) with:

```python
def git_sync():
    global GIT_DATE
    now = time.localtime()
    str_date = f"{now.tm_year}-{now.tm_mon:02}-{now.tm_mday:02}"
    if GIT_DATE == str_date:
        return
    GIT_DATE = str_date
    shas = _load_git_shas()
    updated = False
    for f in ['code.py', 'utility.py', 'plane_icon.py']:
        res = None
        try:
            url = "https://api.github.com/repos/z5ouyang/LED_flight/commits?path=" + f + "&sha=device&per_page=1"
            res = REQUESTS.get(url=url)
            commits = res.json()
            res.close()
            res = None
            gc.collect()
            w.feed()
            if shas.get(f) != commits[0]['sha']:
                sha = commits[0]['sha']
                url = "https://raw.githubusercontent.com/z5ouyang/LED_flight/device/" + f
                res = REQUESTS.get(url=url)
                if res is not None and res.text is not None and len(res.text) > 10:
                    with open(f, 'w') as file:
                        file.write(res.text)
                    shas[f] = sha
                    _save_git_shas(shas)
                    updated = True
                res.close()
                res = None
                gc.collect()
                w.feed()
        except Exception as e:
            if DEBUG_VERBOSE:
                print("GITHUB error for", f)
                print(''.join(traceback.format_exception(None, e, e.__traceback__)))
            else:
                log("GITHUB error for", f)
                log(''.join(traceback.format_exception(None, e, e.__traceback__)))
        finally:
            if res is not None:
                try:
                    res.close()
                except Exception:
                    pass
    if updated:
        log("OTA update applied, reloading")
        supervisor.reload()
```

Key design decisions in this code:
- `try/finally` ensures sockets are closed even if `.json()` fails (device has ~5 sockets)
- `gc.collect()` after each response frees RAM (~200KB total)
- `w.feed()` resets the 60-second watchdog between API calls
- `&per_page=1` limits GitHub API response to 1 commit (default 30 is too much JSON for this RAM)
- SHAs persisted to `git_sync.json` after each file write — prevents infinite download-crash-reload loops

**1c. Add `git_sync()` call in `main()`** — insert after WiFi check (device line 331), before config loading (line 332):

```python
    if not check_wifi(mp):
        return
    git_sync()
    config = ut.get_config()
```

Note: System time hasn't been set via NTP yet at this point, so the date throttle may be wrong on cold boot. This is harmless — the date check is just a throttle, not a correctness requirement.

### Step 2: Create `device` orphan branch in the repo

This step copies the now-edited code.py from the device to a new Git branch. The branch must exist on GitHub before OTA can pull from it.

```bash
cd /Volumes/External/Git/LED_flight
git checkout --orphan device
git rm -rf .
cp /Volumes/CIRCUITPY/code.py .
cp /Volumes/CIRCUITPY/utility.py .
cp /Volumes/CIRCUITPY/plane_icon.py .
cp /Volumes/CIRCUITPY/kdnode.py .
git add code.py utility.py plane_icon.py kdnode.py
git commit -m "feat: initial device branch with CircuitPython-compatible code"
git push origin device
git checkout main
```

**Pre-commit hooks note:** The repo's `.pre-commit-config.yaml` won't exist on the orphan branch (removed by `git rm -rf .`). Pre-commit will error. The human may need to handle this commit directly (or temporarily uninstall hooks). This is a one-time operation.

The orphan branch keeps it clean — no repo history, no standard Python files, just the 4 device files.

### Step 3: Create `boot.py` on the device

Write to `/Volumes/CIRCUITPY/boot.py`. This is the last USB write needed.

Uses `board.SDA` (STEMMA QT connector) as escape hatch pin. Verified: no I2C peripherals attached, `busio` is imported but never used in device code, MatrixPortal S3 dropped the LIS3DH accelerometer that the original MatrixPortal had on I2C.

```python
import board
import digitalio
import storage

pin = digitalio.DigitalInOut(board.SDA)
pin.direction = digitalio.Direction.INPUT
pin.pull = digitalio.Pull.UP

if pin.value:  # No jumper = normal boot = code-writable
    storage.remount("/", readonly=False)

pin.deinit()
```

**Escape hatch:** Jumper SDA to GND during reset to keep USB writable for manual intervention.

**Failure mode:** If `boot.py` itself crashes (import error, pin error), CircuitPython falls back to default behavior (USB writable, code read-only). Device works normally but OTA won't function. This is a safe failure — the device is not bricked.

### Step 4: Deploy

1. Safe-eject the CIRCUITPY volume
2. Press Reset on the device
3. From now on: OTA handles updates, USB is read-only
4. To regain USB access: jumper SDA to GND, press Reset

### Infinite Loop Protection

**Problem:** If OTA downloads a broken `code.py`, the device crashes, reloads, and without SHA persistence would re-download the same broken file endlessly.

**Solution:** SHAs are persisted to `git_sync.json` immediately after each file write. On the next boot, `_load_git_shas()` loads the saved SHAs. If they match the remote, no re-download occurs. The device is stuck with broken code until either:
- A new commit is pushed to the `device` branch (OTA picks it up on next boot)
- Human uses the SDA escape hatch to fix via USB

## Files Modified

| File | Action |
|------|--------|
| `/Volumes/CIRCUITPY/boot.py` | Create new (8 lines) |
| `/Volumes/CIRCUITPY/code.py` | Rewrite git_sync with SHA persistence, fix bugs, add call in main(), remove old GIT_COMMIT dict |
| Repo: new `device` orphan branch | Create from current device files, push to GitHub |

## NOT Changed

- `kdnode.py` — rarely changes, not worth the extra API calls per day
- `utility.py` on `main` — stays as standard Python; device branch has its own version
- `boot.py` is device-only, not committed to repo (hardware-specific config)

## Known Risks

- **Power loss during file write:** FAT16 has no journaling. Power loss mid-write could corrupt the filesystem. No practical mitigation on this hardware — accepted risk. Recovery: UF2 bootloader (double-press Reset) to reflash CircuitPython.
- **GitHub API rate limit:** 60 req/hr unauthenticated. Normal operation uses 3-6 calls/day. The SHA persistence prevents runaway API calls from infinite loops.
- **Supply chain risk (existing, now active):** If the `z5ouyang` GitHub account is compromised, an attacker can push malicious code to the `device` branch and the device will execute it on next sync. No code signing or integrity verification. This risk was already documented in CLAUDE.md as a known property of the OTA pattern — this plan activates it. Mitigation: enable 2FA on the GitHub account, use branch protection rules on the `device` branch.
- **Device branch drift:** The `device` branch has no automated relationship to `main`. When bugs are fixed on `main` in files like `utility.py` or `flight_region.py`, those fixes don't automatically reach the device branch. Manual porting is required: check `main` for relevant changes, adapt them to CircuitPython-compatible form, commit to the `device` branch. This is an accepted maintenance trade-off — the two runtimes (standard Python on Pi vs CircuitPython on device) are fundamentally different enough that automated merging would be dangerous.

## Verification

1. After reset: confirm device boots normally (LED display works)
2. Serial console (`screen /dev/cu.usbmodem85C818AEA1C41 115200`) to watch logs
3. Verify `git_sync()` runs on first boot — should see GitHub API calls in serial output or MQTT log
4. Verify `git_sync.json` is created on the device with SHA values
5. Push a trivial change to `device` branch (e.g., add a comment to `plane_icon.py`), reset device, confirm OTA downloads it and reloads
6. Test escape hatch: jumper SDA to GND, reset, confirm USB is writable from Mac
7. Test broken code recovery: push a file with a syntax error to `device` branch, reset device, confirm it crashes but does NOT re-download on next boot (SHA persisted)
