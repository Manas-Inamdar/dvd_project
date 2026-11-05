"""Package the LaTeX report for Overleaf: dist/report_overleaf/ and dist/report_overleaf.zip (self-contained, images included).

Checks first (a substitute for a compile when no LaTeX engine is available): every \\input file exists, every \\includegraphics image exists,
every \\ref/\\eqref has a \\label, no table is a 'pending' stub, no \\todo is left.
The bundle has report.tex at its root, sections/, tables/ and figures/ (all referenced images copied flat) and a graphicspath that points to figures/.
Upload the zip to Overleaf (New Project -> Upload Project) and compile report.tex with pdfLaTeX.
Run scripts/12_build_report_tables.py first so the tables are up to date.
"""
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "report"
DIST = ROOT / "dist" / "report_overleaf"
SEARCH = [ROOT / "results" / d for d in ("data_check", "models", "gates", "circuit")]


def tex_files():
    return sorted(REPORT.rglob("*.tex"))


def main():
    problems = []
    text = {p: re.sub(r"(?<!\\)%.*", "", p.read_text(encoding="utf-8")) for p in tex_files()}
    allt = "\n".join(text.values())

    for p, t in text.items():                                           # \input files
        for m in re.finditer(r"\\input\{([^}]+)\}", t):
            f = REPORT / (m.group(1) if m.group(1).endswith(".tex") else m.group(1) + ".tex")
            if not f.exists():
                problems.append(f"missing input {m.group(1)} (in {p.name})")
    images = sorted(set(re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", allt)))
    found = {}
    for name in images:                                                 # images
        hit = next((d / name for d in SEARCH if (d / name).exists()), None)
        if hit is None:
            problems.append(f"missing image {name}")
        else:
            found[name] = hit
    labels = set(re.findall(r"\\label\{([^}]+)\}", allt))               # cross references
    for ref in sorted(set(re.findall(r"\\(?:ref|eqref|pageref)\{([^}]+)\}", allt))):
        if ref not in labels:
            problems.append(f"undefined reference {ref}")
    if "pending:" in allt:
        problems.append("a table is still a 'pending' stub (run scripts/12_build_report_tables.py after the pipeline)")
    for p, t in text.items():
        if "\\todo{" in t and "newcommand" not in t:
            problems.append(f"\\todo left in {p.name}")
    if problems:
        print("PROBLEMS:")
        for x in problems:
            print("  -", x)
        sys.exit(1)

    if DIST.parent.exists():
        shutil.rmtree(DIST.parent)
    (DIST / "figures").mkdir(parents=True)
    shutil.copytree(REPORT / "sections", DIST / "sections")
    shutil.copytree(REPORT / "tables", DIST / "tables")
    main = (REPORT / "report.tex").read_text(encoding="utf-8")
    main = re.sub(r"\\graphicspath\{.*\}", r"\\graphicspath{{figures/}}", main)
    (DIST / "report.tex").write_text(main, encoding="utf-8")
    for name, src in found.items():
        shutil.copy(src, DIST / "figures" / name)
    zpath = DIST.parent / "report_overleaf.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(DIST.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(DIST))
    print(f"checks passed: {len(text)} tex files, {len(found)} images, {len(labels)} labels, all references resolved")
    print(f"bundle: {DIST}  ({sum(1 for _ in DIST.rglob('*') if _.is_file())} files)")
    print(f"zip:    {zpath}  ({zpath.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
