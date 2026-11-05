"""Shared plotting helpers."""
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from . import metrics  # noqa: E402


def plot_case(case, pred, true, out):
    fig, axes = plt.subplots(2, 2, figsize=(9, 8))
    for ax, c in zip(axes.ravel(), metrics.CURRENTS):
        t, p = true[c].to_numpy(), pred[c].to_numpy()
        fl = metrics.I_FLOOR
        tt, pp = np.maximum(np.abs(t), fl * 1e-2), np.maximum(np.abs(p), fl * 1e-2)
        same = np.sign(t) == np.sign(p)
        ax.loglog(tt[same], pp[same], ".", ms=2, alpha=.5, label="sign OK")
        ax.loglog(tt[~same], pp[~same], "r.", ms=3, alpha=.6, label="sign differs")
        lo, hi = min(tt.min(), pp.min()), max(tt.max(), pp.max())
        ax.loglog([lo, hi], [lo, hi], "k-", lw=.6)
        ax.axvline(fl, color="gray", ls=":", lw=1); ax.axhline(fl, color="gray", ls=":", lw=1)
        ax.set_title(f"{case}  |{c}|  (dotted = noise floor {fl:g} A)", fontsize=9)
        ax.set_xlabel("SPICE |I| (A)"); ax.set_ylabel("ML |I| (A)"); ax.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(out, dpi=110); plt.close(fig)
