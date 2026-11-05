r"""Render the LaTeX report to a PDF WITHOUT a LaTeX engine (dist/report.pdf).

This is a converter for the small LaTeX subset used by report/ (sections, lists, tabulars, figures, simple inline/display math, a few text
commands) -> HTML -> PDF through PyMuPDF's Story renderer. It is a faithful rendering of the same content, tables and figures, but NOT a pdfLaTeX
typeset: fonts, line breaking and math layout differ (math is shown as formatted text). For the true LaTeX PDF compile report/report.tex
(e.g. dist/report_overleaf.zip on Overleaf).
Run scripts/12_build_report_tables.py first. Usage: python scripts/14_render_report_pdf.py
"""
import datetime
import html
import re
import sys
from pathlib import Path

import pymupdf

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "report"
SEARCH = [ROOT / "results" / d for d in ("data_check", "models", "gates", "circuit")]
OUT = ROOT / "dist" / "report.pdf"
RAW = ROOT / "dist" / "_report_raw.pdf"
TEXT_W = 495.0   # A4 width 595 pt minus 2 x 50 pt margins

SYM = {r"\min": "min", r"\max": "max", r"\in": "∈", r"\gamma": "γ", r"\beta": "β", r"\delta": "δ", r"\Delta": "Δ", r"\sigma": "σ", r"\rho": "ρ",
       r"\epsilon": "ε", r"\lambda": "λ", r"\tau": "τ", r"\phi": "φ", r"\theta": "θ", r"\eta": "η", r"\kappa": "κ", r"\sinh": "sinh", r"\tanh": "tanh",
       r"\exp": "exp", r"\neq": "≠", r"\equiv": "≡", r"\propto": "∝", r"\rightarrow": "→", r"\Rightarrow": "⇒", r"\forall": "∀",
       r"\times": "×", r"\pm": "±", r"\approx": "≈", r"\le": "≤", r"\leq": "≤", r"\ge": "≥", r"\geq": "≥", r"\gg": "≫", r"\ll": "≪", r"\cdot": "·",
       r"\circ": "°", r"\mu": "μ", r"\Omega": "Ω", r"\alpha": "α", r"\sim": "∼", r"\ldots": "…", r"\dots": "…", r"\to": "→", r"\infty": "∞",
       r"\log": "log", r"\ln": "ln", r"\sum": "Σ", r"\quad": "  ", r"\,": " ", r"\;": " ", r"\:": " ", r"\!": "", r"\ ": " "}


# ----------------------------------------------------------------------------- helpers
def brace_arg(s: str, i: int):
    """s[i] must be '{'; return (content, index after the matching '}')."""
    assert s[i] == "{", s[i:i + 20]
    depth, j = 0, i
    while j < len(s):
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    raise ValueError("unbalanced braces")


def strip_comments(t: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*", "", ln) for ln in t.splitlines())


def expand_inputs(t: str) -> str:
    def rep(m):
        name = m.group(1)
        f = REPORT / (name if name.endswith(".tex") else name + ".tex")
        return expand_inputs(strip_comments(f.read_text(encoding="utf-8")))
    return re.sub(r"\\input\{([^}]+)\}", rep, t)


# ----------------------------------------------------------------------------- math
def math_to_html(m: str) -> str:
    m = m.strip().replace("\\%", "%").replace("\\$", "$").replace("\\_", "_").replace("\\#", "#").replace("\\{", "\x07").replace("\\}", "\x08")
    m = re.sub(r"\\(?:text|mathrm|operatorname|mathbf|textbf)\s*\{", lambda mo: "\x01{", m)   # keep content, drop the command
    for k in sorted(SYM, key=len, reverse=True):
        m = m.replace(k, SYM[k])
    m = re.sub(r"\\(?:tfrac|frac)\s*\{([^{}]*)\}\s*\{([^{}]*)\}", lambda mo: f"({mo.group(1)})/({mo.group(2)})" if not re.fullmatch(r"[\w.]+", mo.group(1) + mo.group(2)) else f"{mo.group(1)}/{mo.group(2)}", m)
    m = m.replace("\x01", "")
    m = re.sub(r"\\tfrac(\d)(\d)", r"\1/\2", m)
    while "\\overline" in m:                                  # nested braces allowed
        i = m.index("\\overline")
        j = m.index("{", i)
        arg, end = brace_arg(m, j)
        m = m[:i] + "<span style='text-decoration:overline'>" + arg + "</span>" + m[end:]

    def script(s):
        out, i = [], 0
        while i < len(s):
            c = s[i]
            if c in "_^":
                i += 1
                if i < len(s) and s[i] == "{":
                    arg, i = brace_arg(s, i)
                elif i < len(s) and s[i] == "\\":
                    mo = re.match(r"\\[A-Za-z]+|\\.", s[i:])
                    arg, i = mo.group(0), i + len(mo.group(0))
                else:
                    arg, i = s[i:i + 1], i + 1
                tag = "sub" if c == "_" else "sup"
                out.append(f"<{tag}>{script(arg)}</{tag}>")
            else:
                out.append(c)
                i += 1
        return "".join(out)
    m = script(m)
    m = m.replace("{", "").replace("}", "")
    return m.replace("\x07", "{").replace("\x08", "}")


# ----------------------------------------------------------------------------- inline text
def inline(s: str, protect: dict) -> str:
    maths = []

    def keep_math(mo):
        maths.append(math_to_html(mo.group(1)))
        return f"\x02{len(maths) - 1}\x03"
    s = re.sub(r"(?<!\\)\$((?:[^$\\]|\\.)*)\$", keep_math, s)
    s = html.escape(s, quote=False)
    s = s.replace("\\\\", "<br>")
    for a, b in ((r"\%", "%"), (r"\&amp;", "&amp;"), (r"\_", "_"), (r"\#", "#"), (r"\$", "$"), (r"\{", "{"), (r"\}", "}"), (r"\,", " "), (r"\ ", " "), (r"\-", "")):
        s = s.replace(a, b)
    for _ in range(4):   # nested commands
        s = re.sub(r"\\emph\{([^{}]*)\}", r"<i>\1</i>", s)
        s = re.sub(r"\\textbf\{([^{}]*)\}", r"<b>\1</b>", s)
        s = re.sub(r"\\texttt\{([^{}]*)\}", r"<code>\1</code>", s)
        s = re.sub(r"\\textcolor\{[^{}]*\}\{([^{}]*)\}", r"<span style='color:#b00000'>\1</span>", s)
    s = re.sub(r"\\label\{[^}]*\}", "", s)
    s = re.sub(r"\\(?:ref|eqref)\{([^}]+)\}", lambda mo: f"@@REF:{mo.group(1)}@@", s)
    s = re.sub(r"\\(?:small|centering|noindent|bigskip|medskip|smallskip)\b", "", s)
    s = s.replace("\\dots", "…").replace("\\ldots", "…").replace("-&gt;", "→")
    s = s.replace("---", "—").replace("--", "–").replace("``", "“").replace("''", "”")
    s = s.replace("~", "&nbsp;")
    s = s.replace("{", "").replace("}", "")
    s = re.sub(r"\x02(\d+)\x03", lambda mo: maths[int(mo.group(1))], s)
    for k, v in protect.items():
        s = s.replace(k, v)
    left = re.findall(r"\\[A-Za-z]+", s)
    if left:
        print("unhandled LaTeX commands:", sorted(set(left))[:8], "in:", s[:80].replace("\n", " "))
    return s


# ----------------------------------------------------------------------------- environments
class Doc:
    def __init__(self):
        self.labels, self.blocks, self.toc = {}, {}, []
        self.sec = [0, 0]
        self.appendix = False
        self.fig = 0
        self.tab = 0
        self.cur_label_target = ""

    def next_token(self, html_block: str) -> str:
        k = f"\x04{len(self.blocks)}\x05"
        self.blocks[k] = html_block
        return k

    def heading(self, level: int, title: str, numbered: bool = True) -> str:
        if not numbered:
            return f"<h{level + 1}>{inline(title, {})}</h{level + 1}>"
        if level == 1:
            self.sec[0] += 1
            self.sec[1] = 0
            num = chr(64 + self.sec[0]) if self.appendix else str(self.sec[0])
        else:
            self.sec[1] += 1
            base = chr(64 + self.sec[0]) if self.appendix else str(self.sec[0])
            num = f"{base}.{self.sec[1]}"
        self.cur_label_target = num
        txt = inline(title, {})
        self.toc.append((level, num, re.sub(r"<[^>]+>", "", txt)))
        pre = ("Appendix " if (level == 1 and self.appendix) else "")
        return f"<h{level + 1}>{pre}{num}&nbsp;&nbsp;{txt}</h{level + 1}>"


def parse_tabular(body: str, spec: str, doc: Doc) -> str:
    aligns = re.findall(r"[lrc]", re.sub(r"\{[^}]*\}", "", spec))
    body = re.sub(r"\\(?:toprule|midrule|bottomrule|hline)", "\x06", body)
    rows = [r for r in re.split(r"(?<!\\)\\\\", body)]
    out, header_done = ["<table>"], False
    pending_header = True
    for raw in rows:
        parts = raw.split("\x06")
        has_rule_before = len(parts) > 1
        content = parts[-1].strip() if len(parts) > 1 else raw.strip()
        if len(parts) > 1 and any(p.strip() for p in parts[:-1]) and not content:
            content = "".join(p for p in parts if p.strip()).strip()
        raw_rows = [p.strip() for p in parts if p.strip()]
        for content in raw_rows:
            cells = re.split(r"(?<!\\)&", content)
            tag = "th" if pending_header else "td"
            tds = []
            for i, c in enumerate(cells):
                al = {"l": "left", "r": "right", "c": "center"}.get(aligns[i] if i < len(aligns) else "l", "left")
                tds.append(f"<{tag} style='text-align:{al}'>{inline(c.strip(), {})}</{tag}>")
            out.append("<tr>" + "".join(tds) + "</tr>")
            pending_header = False
        if len(parts) > 1 and pending_header is False and header_done is False:
            header_done = True
    out.append("</table>")
    return "".join(out)


def convert(tex: str, doc: Doc) -> str:
    # --- environments (innermost handled via explicit order) ---
    def find_env(s, name):
        m = re.search(r"\\begin\{" + name + r"\}(\[[^\]]*\])?", s)
        if not m:
            return None
        e = re.search(r"\\end\{" + name + r"\}", s[m.end():])
        return m.start(), m.end(), m.end() + e.start(), m.end() + e.end()

    while True:   # verbatim
        r = find_env(tex, "verbatim")
        if not r:
            break
        a, b, c, d = r
        tex = tex[:a] + doc.next_token("<pre>" + html.escape(tex[b:c].strip("\n")) + "</pre>") + tex[d:]
    while True:   # figures
        r = find_env(tex, "figure")
        if not r:
            break
        a, b, c, d = r
        body = tex[b:c]
        doc.fig += 1
        imgs = []
        for m in re.finditer(r"\\includegraphics(?:\[width=([0-9.]*)\\textwidth\])?\{([^}]+)\}", body):
            frac = float(m.group(1)) if m.group(1) else 1.0
            imgs.append((m.group(2), frac))
        cap = ""
        mc = re.search(r"\\caption\{", body)
        if mc:
            cap, _ = brace_arg(body, mc.end() - 1)
        for ml in re.finditer(r"\\label\{([^}]+)\}", body):
            doc.labels[ml.group(1)] = str(doc.fig)
        if len(imgs) > 1:      # several images in one figure: two per row, as a borderless table
            cells = [f"<td><img src='{n}' width='{TEXT_W * f * 0.97:.0f}'></td>" for n, f in imgs]
            grid = "<table class='grid'>" + "".join("<tr>" + "".join(cells[i:i + 2]) + "</tr>" for i in range(0, len(cells), 2)) + "</table>"
        else:
            grid = f"<img src='{imgs[0][0]}' width='{TEXT_W * imgs[0][1] * 0.985:.0f}'>"
        blk = f"<div class='fig'>{grid}<p class='cap'><b>Figure {doc.fig}.</b> {inline(cap, {})}</p></div>"
        tex = tex[:a] + doc.next_token(blk) + tex[d:]
    while True:   # tables
        r = find_env(tex, "table")
        if not r:
            break
        a, b, c, d = r
        body = tex[b:c]
        doc.tab += 1
        mt = re.search(r"\\begin\{tabular\}\{([^}]*)\}(.*?)\\end\{tabular\}", body, re.S)
        cap = ""
        mc = re.search(r"\\caption\{", body)
        if mc:
            cap, _ = brace_arg(body, mc.end() - 1)
        for ml in re.finditer(r"\\label\{([^}]+)\}", body):
            doc.labels[ml.group(1)] = str(doc.tab)
        blk = f"<div class='tab'>{parse_tabular(mt.group(2), mt.group(1), doc)}<p class='cap'><b>Table {doc.tab}.</b> {inline(cap, {})}</p></div>"
        tex = tex[:a] + doc.next_token(blk) + tex[d:]
    while True:   # bare tabulars (not in a table environment)
        m = re.search(r"\\begin\{tabular\}\{([^}]*)\}(.*?)\\end\{tabular\}", tex, re.S)
        if not m:
            break
        tex = tex[:m.start()] + doc.next_token("<div class='tab'>" + parse_tabular(m.group(2), m.group(1), doc) + "</div>") + tex[m.end():]
    for env, tag in (("itemize", "ul"), ("enumerate", "ol")):
        while True:
            r = find_env(tex, env)
            if not r:
                break
            a, b, c, d = r
            items = [i.strip() for i in re.split(r"\\item\b", tex[b:c])[1:]]
            blk = f"<{tag}>" + "".join(f"<li>{inline(i, {})}</li>" for i in items) + f"</{tag}>"
            tex = tex[:a] + doc.next_token(blk) + tex[d:]
    while True:   # display math
        m = re.search(r"\\\[(.*?)\\\]", tex, re.S)
        if not m:
            break
        tex = tex[:m.start()] + doc.next_token("<p class='eq'>" + math_to_html(re.sub(r"\s+", " ", m.group(1))).replace("\\\\", "<br>") + "</p>") + tex[m.end():]
    tex = re.sub(r"\\begin\{center\}|\\end\{center\}", "", tex)

    # --- sectioning + paragraphs ---
    tex = re.sub(r"\\(?:maketitle|tableofcontents|newpage|clearpage)\b", "", tex)
    out = []
    pos = 0
    pat = re.compile(r"\\(section\*?|subsection|paragraph)\s*\{|\\appendix\b")
    chunks = []
    for m in pat.finditer(tex):
        chunks.append(("text", tex[pos:m.start()]))
        if m.group(0).startswith("\\appendix"):
            chunks.append(("appendix", ""))
            pos = m.end()
            continue
        title, end = brace_arg(tex, m.end() - 1)
        chunks.append((m.group(1), title))
        pos = end
    chunks.append(("text", tex[pos:]))
    for kind, val in chunks:
        if kind == "appendix":
            doc.appendix = True
            doc.sec = [0, 0]
        elif kind == "section":
            out.append(doc.heading(1, val))
        elif kind == "section*":
            out.append(doc.heading(1, val, numbered=False))
        elif kind == "subsection":
            out.append(doc.heading(2, val))
        elif kind == "paragraph":
            ttl = inline(val, {})
            out.append(f"<p class='para'><b>{ttl}{'' if ttl.rstrip().endswith('.') else '.'}</b> ")
        else:
            for lab in re.finditer(r"\\label\{([^}]+)\}", val):
                doc.labels[lab.group(1)] = ("Appendix " if False else "") + doc.cur_label_target
            for para in re.split(r"\n\s*\n", val):
                p = para.strip()
                if not p:
                    continue
                parts = re.split(r"(\x04\d+\x05)", p)
                buf = []
                for part in parts:
                    if re.fullmatch(r"\x04\d+\x05", part):
                        if buf and "".join(buf).strip():
                            out.append("<p>" + inline(" ".join(buf), {}) + "</p>")
                        buf = []
                        out.append(doc.blocks[part])
                    else:
                        buf.append(part)
                if buf and "".join(buf).strip():
                    out.append("<p>" + inline(" ".join(buf), {}) + "</p>")
    return "\n".join(out)


CSS = """
body { font-family: serif; font-size: 10pt; line-height: 1.28; }
h1 { font-size: 20pt; text-align: center; margin: 0 0 4pt 0; }
h2 { font-size: 14pt; margin: 14pt 0 4pt 0; }
h3 { font-size: 11.5pt; margin: 10pt 0 3pt 0; }
p { margin: 0 0 5pt 0; text-align: justify; }
p.sub { text-align: center; font-size: 12pt; margin: 0 0 4pt 0; }
p.eq { text-align: center; margin: 4pt 0 6pt 0; font-size: 11pt; }
p.cap { font-size: 9pt; text-align: justify; margin: 3pt 6pt 8pt 6pt; }
div.fig { text-align: center; margin: 6pt 0 4pt 0; }
div.tab { margin: 6pt 0 4pt 0; font-size: 8pt; }
table { border-collapse: collapse; margin-left: auto; margin-right: auto; }
table.grid td { border: none; padding: 0; text-align: center; }
th { border-top: 1pt solid #000; border-bottom: 0.6pt solid #000; padding: 1.5pt 4pt; font-weight: bold; }
td { padding: 1.2pt 4pt; border-bottom: 0.3pt solid #cccccc; }
pre { font-family: monospace; font-size: 6.2pt; line-height: 1.15; margin: 4pt 0 6pt 0; }
code { font-family: monospace; font-size: 9pt; }
ul, ol { margin: 0 0 5pt 0; }
li { margin: 0 0 1.5pt 0; text-align: justify; }
"""


def main():
    raw = strip_comments((REPORT / "report.tex").read_text(encoding="utf-8"))
    title_m = re.search(r"\\title\{(.*?)\}\s*\\author", raw, re.S)
    author = re.search(r"\\author\{(.*?)\}", raw, re.S).group(1)
    body = raw[raw.index("\\begin{document}") + len("\\begin{document}"):raw.index("\\end{document}")]
    body = expand_inputs(body)
    doc = Doc()
    main_html = convert(body, doc)

    def resolve(h):
        def rep(m):
            if m.group(1) not in doc.labels:
                print("UNRESOLVED REF", m.group(1))
                return "??"
            return doc.labels[m.group(1)]
        return re.sub(r"@@REF:([^@]+)@@", rep, h)
    main_html = resolve(main_html)

    title = inline(title_m.group(1).replace("\\large", ""), {})
    head = f"<h1>{title}</h1><p class='sub'>{inline(author, {})}</p><p class='sub'>{datetime.date.today():%d %B %Y}</p><br>"

    def toc_html(pages):
        rows = []
        for (lvl, num, txt), pg in zip(doc.toc, pages):
            pad = "" if lvl == 1 else "&nbsp;&nbsp;&nbsp;&nbsp;"
            lab = ("A" <= num[0] <= "C" and not num[0].isdigit())
            rows.append(f"<p style='margin:0;text-align:left'>{pad}{'<b>' if lvl == 1 else ''}{'Appendix ' if (lvl == 1 and lab) else ''}{num}&nbsp;&nbsp;{txt}{'</b>' if lvl == 1 else ''}"
                        f"&nbsp;&nbsp;<span style='color:#555'>… {pg}</span></p>")
        return "<h2>Contents</h2>" + "".join(rows) + "<br>"

    # images are looked up by file name in one archive directory: copy references into a temp folder
    tmp = ROOT / "dist" / "_figs"
    tmp.mkdir(parents=True, exist_ok=True)
    for name in set(re.findall(r"<img src='([^']+)'", main_html)):
        src = next((d / name for d in SEARCH if (d / name).exists()), None)
        if src is None:
            sys.exit(f"missing image {name}")
        (tmp / name).write_bytes(src.read_bytes())

    pages = ["?"] * len(doc.toc)
    for attempt in range(2):
        full = f"<html><body>{head}{toc_html(pages)}{main_html}</body></html>"
        story = pymupdf.Story(html=full, user_css=CSS, archive=pymupdf.Archive(str(tmp)))
        OUT.parent.mkdir(exist_ok=True)
        raw_path = ROOT / "dist" / f"_raw{attempt}.pdf"
        writer = pymupdf.DocumentWriter(str(raw_path))
        mediabox = pymupdf.paper_rect("a4")
        where = mediabox + (50, 52, -50, -64)
        found, pno = [], 0
        more = 1
        while more:
            dev = writer.begin_page(mediabox)
            more, _ = story.place(where)

            def make_rec(pg):
                def rec(pos):
                    if pos.heading and pos.open_close & 1 and pos.heading in (2, 3) and pos.text.strip() not in ("Contents",) and not pos.text.strip().startswith("Report status"):
                        found.append((pos.heading - 1, pos.text.strip(), pg))
                return rec
            story.element_positions(make_rec(pno + 1))
            story.draw(dev)
            writer.end_page()
            pno += 1
        writer.close()
        pages_new = [p for (_, _, p) in found]
        if len(pages_new) != len(doc.toc):
            print("heading count mismatch", len(pages_new), len(doc.toc))
            break
        if [str(p) for p in pages_new] == pages:
            break
        pages = [str(p) for p in pages_new]
    # page numbers + PDF bookmarks
    pdf = pymupdf.open(str(raw_path))
    for i, page in enumerate(pdf, 1):
        page.insert_text((TEXT_W / 2 + 50 - 4, 842 - 34), str(i), fontsize=9, fontname="helv")
    outline = []
    for (lvl, txt, pg) in found:
        outline.append([lvl, txt, pg])
    if outline:
        try:
            pdf.set_toc(outline)
        except Exception as e:  # bookmarks are optional
            print("bookmarks skipped:", e)
    pdf.save(str(OUT), garbage=3, deflate=True)
    pdf.close()
    for f in (ROOT / "dist").glob("_raw*.pdf"):
        try:
            f.unlink()
        except OSError:
            pass
    print(f"{OUT}: {pno} pages, {len(doc.toc)} headings, {doc.fig} figures, {doc.tab} tables, {len(doc.labels)} labels")


if __name__ == "__main__":
    main()
