"""Reference solve with a cross-check (D-031).

SPICE with the mandated tolerances (gmin=1e-18 abstol=1e-18 reltol=1e-6 vntol=1e-9) occasionally "converges" to a point that is not a valid
operating point (e.g. an output node stuck at 7e-5 V instead of 4e-8 V, leakage 200x too large, or even negative). Every run is therefore solved
twice: with exactly the mandated options (tier 0) and with a later options line that sets abstol to the numerical noise floor and tightens
reltol/vntol (tier 1). The mandated result is the reference when both agree within `rel_tol`; otherwise the tier-1 result is used and flagged.
"""
import math


def solve_with_crosscheck(make_netlist, run, parse, leak, cfg, rel_tol: float = 0.01):
    """make_netlist(tier) -> netlist text; run(netlist, cfg) -> stdout; parse(stdout) -> values; leak(values) -> leakage (A).

    Returns (values, source, rel_diff) with source in {"mandated", "tight", "tight_only", "mandated_only"}; (None, "failed", nan) if both fail."""
    res = {}
    for tier in (0, 1):
        try:
            v = parse(run(make_netlist(tier), cfg))
            res[tier] = (v, leak(v))
        except (RuntimeError, KeyError):
            res[tier] = None
    if res[0] and res[1]:
        l0, l1 = res[0][1], res[1][1]
        d = abs(l0 - l1) / max(abs(l1), 1e-30)
        return (res[0][0], "mandated", d) if d <= rel_tol and math.isfinite(d) else (res[1][0], "tight", d)
    if res[1]:
        return res[1][0], "tight_only", math.nan
    if res[0]:
        return res[0][0], "mandated_only", math.nan
    return None, "failed", math.nan
