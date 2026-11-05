"""Run ngspice in batch mode and parse printed currents.

Sign convention (docs/DECISIONS.md D-006): terminal currents are positive INTO the device.
ngspice's I(Vsrc) is positive into the source's + node (+ node = device node, - node = ground), i.e. OUT of the
device, so  i_into_device = -I(Vsrc).  To be verified by the smoke test once ngspice is available.
"""
import os
import re
import subprocess
import tempfile
from pathlib import Path

_NUM = r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"
_PRINT_RE = re.compile(rf"^\s*i\((v\w+)\)\s*=\s*({_NUM})\s*$", re.IGNORECASE | re.MULTILINE)


def ngspice_exe(cfg: dict) -> str:
    return os.environ.get("NGSPICE_EXE") or cfg["spice"]["exe"]


def parse_source_currents(stdout: str) -> dict[str, float]:
    """{'vd': -1.2e-11, ...} raw SPICE source currents from `print i(Vd) ...` output (lower-cased names)."""
    return {m.group(1).lower(): float(m.group(2)) for m in _PRINT_RE.finditer(stdout)}


def terminal_currents(src: dict[str, float]) -> dict[str, float]:
    """Raw source currents -> currents flowing INTO the device terminals (id, ig, is, ib)."""
    return {"id": -src["vd"], "ig": -src["vg"], "is": -src["vs"], "ib": -src["vb"]}


def run_netlist(netlist: str, cfg: dict, timeout: float = 60.0) -> str:
    """Run one netlist in ngspice batch mode, return stdout+stderr. Raises RuntimeError on failure/timeout."""
    with tempfile.TemporaryDirectory(prefix="dvdml_") as d:
        f = Path(d) / "run.cir"
        f.write_text(netlist, encoding="utf-8")
        try:
            p = subprocess.run([ngspice_exe(cfg), "-b", str(f)], capture_output=True, text=True, timeout=timeout, cwd=d)
        except subprocess.TimeoutExpired as e:
            raise RuntimeError("ngspice timeout") from e
    if p.returncode != 0:
        raise RuntimeError(f"ngspice exit {p.returncode}: {p.stderr[-500:]}")
    return p.stdout + p.stderr
