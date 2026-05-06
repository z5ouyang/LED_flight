import microcontroller

BOOT_PY = """import storage
storage.remount("/", readonly=True)
"""

with open("boot.py", "w") as f:
    f.write(BOOT_PY)

microcontroller.reset()
