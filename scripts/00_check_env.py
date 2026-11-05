"""Print tool versions (needed for the report: simulator and version). Exit 1 if ngspice is missing."""
import platform
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dvdml.config import load_config  # noqa: E402
from dvdml.spice import ngspice_exe  # noqa: E402

print("python", sys.version.split()[0], platform.platform())
for mod in ("numpy", "pandas", "scipy", "sklearn", "matplotlib", "yaml", "joblib", "lightgbm"):
    try:
        m = __import__(mod)
        print(f"{mod:12s}", getattr(m, "__version__", "?"))
    except ImportError:
        print(f"{mod:12s} MISSING")
exe = ngspice_exe(load_config())
try:
    out = subprocess.run([exe, "-v"], capture_output=True, text=True, timeout=30)
    print("ngspice     ", (out.stdout + out.stderr).strip().splitlines()[0:3])
except (FileNotFoundError, subprocess.TimeoutExpired) as e:
    print("ngspice      NOT FOUND:", exe, e)
    sys.exit(1)
