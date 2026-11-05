"""Tiny helpers to turn DataFrames into LaTeX tabulars (no jinja2 dependency) so report numbers are never typed by hand."""
import math

import pandas as pd

_ESC = {"_": r"\_", "%": r"\%", "&": r"\&", "#": r"\#", "$": r"\$"}


def esc(s) -> str:
    return "".join(_ESC.get(ch, ch) for ch in str(s))


def fmt_num(x, kind: str = "g") -> str:
    """kind: 'g' 4 significant digits, 'pct' percentage with 2 digits, 'sci' scientific, 'int'."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "--"
    if kind == "int":
        return str(int(x))
    if kind == "pct":
        return f"{100 * float(x):.2f}\\%"
    if kind == "sci":
        m, e = f"{float(x):.2e}".split("e")
        return f"${m}\\times10^{{{int(e)}}}$"
    return f"{float(x):.4g}"


def tabular(df: pd.DataFrame, kinds: dict | None = None, caption: str | None = None, label: str | None = None,
            colspec: str | None = None, small: bool = True) -> str:
    """LaTeX table (table environment if caption/label given, else bare tabular). `kinds` maps column -> fmt_num kind."""
    kinds = kinds or {}
    cols = list(df.columns)
    spec = colspec or "l" + "r" * (len(cols) - 1)
    lines = [rf"\begin{{tabular}}{{{spec}}}", r"\toprule", " & ".join(esc(c) for c in cols) + r" \\", r"\midrule"]
    for _, row in df.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            if isinstance(v, str) or c not in kinds and not isinstance(v, (int, float)):
                cells.append(esc(v))
            else:
                cells.append(fmt_num(v, kinds.get(c, "g")))
        lines.append(" & ".join(cells) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    body = "\n".join(lines)
    if small:
        body = r"{\small" + "\n" + body + "\n}"
    if caption or label:
        body = "\\begin{table}[H]\n\\centering\n" + body + f"\n\\caption{{{caption or ''}}}\n" + (f"\\label{{{label}}}\n" if label else "") + "\\end{table}\n"
    return body + "\n"
