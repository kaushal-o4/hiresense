"""Builds docs/HireSense_Team_Work_Distribution.pdf from content.py.

Run from the repository root with the backend venv (needs playwright + pypdf):
    backend\\venv\\Scripts\\python docs\\team_report\\build.py
Two passes: render, find the page of every section heading, then render again with page numbers in the contents.
The cover is rendered separately (no header/footer) and merged in front; body pages are numbered from 1.
"""
import base64
import html
import io
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright
from pypdf import PdfReader, PdfWriter

sys.path.insert(0, str(Path(__file__).parent))
import content as C  # noqa: E402

HERE = Path(__file__).parent
OUT_PDF = HERE.parent / "HireSense_Team_Work_Distribution.pdf"
SHOTS = (HERE.parent / "screenshots").resolve()
e = html.escape

CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root { --navy:#0b1f3a; --blue:#1d4ed8; --blue2:#2563eb; --sky:#e8effc; --ink:#111827; --muted:#4b5563; --line:#d6deea; }
* { box-sizing: border-box; }
html, body { margin:0; padding:0; }
body { font-family: 'Inter', 'Segoe UI', Arial, sans-serif; color: var(--ink); font-size: 10.1pt; line-height: 1.45; }
h1 { font-size: 20pt; color: var(--navy); margin: 0 0 4mm; padding-bottom: 2.5mm; border-bottom: 2.5px solid var(--blue); }
h2 { font-size: 13.5pt; color: var(--blue); margin: 6mm 0 2.5mm; }
h3 { font-size: 11pt; color: var(--navy); margin: 3.5mm 0 1.2mm; }
p { margin: 0 0 2.6mm; text-align: justify; }
ul, ol { margin: 0 0 2.5mm; padding-left: 6mm; } li { margin: 0 0 .7mm; }
.section { break-before: page; }
h2, h3, h4 { break-after: avoid; }
.keep { break-inside: avoid; }
table { width: 100%; border-collapse: collapse; margin: 1.5mm 0 4mm; font-size: 9.4pt; }
th { background: var(--navy); color: #fff; text-align: left; padding: 2mm 2.5mm; font-weight: 600; }
td { border-bottom: 1px solid var(--line); padding: 1.8mm 2.5mm; vertical-align: top; }
tr:nth-child(even) td { background: #f5f8fd; }
tr { break-inside: avoid; }
.tight td { padding: 1.05mm 2.2mm; } .tight th { padding: 1.5mm 2.2mm; }
code, .mono { font-family: Consolas, 'Cascadia Mono', monospace; font-size: 8.6pt; color: #1e3a8a; }
.lead { font-size: 11pt; color: #1f2937; }
.callout { background: var(--sky); border-left: 4px solid var(--blue); padding: 3mm 4mm; margin: 2mm 0 4mm; border-radius: 0 4px 4px 0; }
.member-head { background: linear-gradient(90deg, var(--navy), #163768); color:#fff; border-radius: 6px; padding: 5mm 6mm; margin-bottom: 4mm; }
.member-head .num { font-size: 9pt; letter-spacing: .15em; text-transform: uppercase; color: #a9c1ee; }
.member-head .name { font-size: 22pt; font-weight: 800; margin: 1mm 0; }
.member-head .role { font-size: 11pt; color: #dbe6fb; }
.pct { float: right; text-align: right; } .pct b { font-size: 22pt; display:block; } .pct span { font-size: 8.5pt; color:#a9c1ee; }
.chips { margin: 1mm 0 3mm; } .chip { display:inline-block; background: var(--sky); color: #1e3a8a; border:1px solid #c7d6f5; border-radius: 20px; padding: .5mm 3mm; margin: 0 1.5mm 1.5mm 0; font-size: 8.8pt; }
.grid2 { display:grid; grid-template-columns: 1fr 1fr; gap: 4mm; }
.card { border:1px solid var(--line); border-radius:6px; padding: 3mm 4mm; break-inside: avoid; }
.card h4 { margin: 0 0 1.5mm; color: var(--blue); font-size: 10pt; }
.toc { width:100%; border-collapse: collapse; font-size: 11pt; }
.toc td { border:none; padding: 2.2mm 0; background: none !important; }
.toc td.n { width: 10mm; color: var(--blue); font-weight: 700; }
.toc td.p { text-align: right; width: 14mm; font-weight: 600; }
.toc td.t { border-bottom: 1px dotted #9aa8bf !important; }
.toc tr.sub td { font-size: 10pt; padding: 1.2mm 0; color: var(--muted); } .toc tr.sub td.t { padding-left: 6mm; }
.shot { width: 100%; border:1px solid var(--line); border-radius: 4px; }
.shots { display:grid; grid-template-columns: 1fr 1fr; gap: 3mm; margin: 2mm 0; } .shots figure { margin:0; break-inside: avoid; }
figcaption { font-size: 8.5pt; color: var(--muted); text-align:center; margin-top: 1mm; }
.bar { height: 5mm; background:#e5ebf5; border-radius: 3px; overflow:hidden; } .bar > div { height:100%; background: var(--blue2); }
"""

COVER_CSS = r"""
@page { size: A4; margin: 0; }
body { margin:0; }
.cover { width: 210mm; height: 297mm; background: var(--navy); color: #fff; position: relative; overflow: hidden; padding: 28mm 22mm; }
.cover .band { position:absolute; right:-40mm; top:-40mm; width: 150mm; height: 150mm; border-radius: 50%; background: #13305a; }
.cover .band2 { position:absolute; right: 20mm; bottom: -60mm; width: 120mm; height: 120mm; border-radius: 50%; background: #102a4f; }
.cover .inner { position: relative; }
.cover .tag { font-size: 10pt; letter-spacing: .25em; text-transform: uppercase; color:#8fb0ea; }
.cover .logo { display:inline-flex; align-items:center; justify-content:center; width: 18mm; height: 18mm; border-radius: 4mm; background: var(--blue2); font-weight:800; font-size: 22pt; margin-bottom: 8mm; }
.cover h1 { color:#fff; border:none; font-size: 40pt; margin: 4mm 0 2mm; padding: 0; letter-spacing: -.02em; }
.cover .sub { font-size: 15pt; color:#cfe0ff; max-width: 150mm; line-height: 1.35; }
.cover .doc { margin-top: 12mm; font-size: 17pt; font-weight: 700; color: #fff; border-left: 4px solid #60a5fa; padding-left: 4mm; }
.cover table { width: 150mm; margin-top: 16mm; font-size: 11pt; }
.cover td { border: none; padding: 2.2mm 0; color: #e5edff; background: none !important; }
.cover td.k { color:#8fb0ea; width: 45mm; }
.cover .team { margin-top: 10mm; } .cover .team span { display:inline-block; border:1px solid #3d63a3; border-radius: 20px; padding: 1.5mm 5mm; margin: 0 2mm 2mm 0; font-size: 11pt; }
.cover .foot { position:absolute; bottom: 18mm; left: 22mm; right: 22mm; font-size: 9pt; color:#8fb0ea; border-top: 1px solid #2c4c80; padding-top: 3mm; }
"""

SECTIONS = [  # (id, number, title, subtitles)
    ("desc", "1", "Project Description", []),
    ("how", "2", "How HireSense Works — Simple Architecture and Workflow", []),
    ("dist", "3", "Team Work Distribution", [f"3.{i+1}  {m['name']} — {m['role']} ({m['pct']}%)" for i, m in enumerate(C.MEMBERS)]),
    ("timeline", "4", "Project Timeline", []),
    ("collab", "5", "Team Collaboration", []),
    ("arch", "6", "Project Architecture (Technical Detail)", []),
    ("learn", "7", "Individual Learning Outcomes", []),
    ("concl", "8", "Conclusion", []),
]


def ul(items):
    return "<ul>" + "".join(f"<li>{fmt(i)}</li>" for i in items) + "</ul>"


def fmt(text):
    """Escape, then show file paths in a monospace style."""
    t = e(text)
    return re.sub(r"(?<![\w/])((?:\.?[\w\-]+/)+(?:[\w\-]+\.\w+)?(?![\w])|\b[\w\-]+\.(?:py|jsx?|json|yml|yaml|md|css)\b)",
                  r'<span class="mono">\1</span>', t)


def cover():
    team = "".join(f"<span>{e(n)}</span>" for n in C.TEAM)
    return f"""<div class="cover"><div class="band"></div><div class="band2"></div><div class="inner">
<div class="logo">H</div>
<div class="tag">Final Year Project Report</div>
<h1>{C.PROJECT}</h1>
<div class="sub">{e(C.SUBTITLE)}</div>
<div class="doc">Team Work Distribution and Project Contribution Report</div>
<table>
<tr><td class="k">College</td><td>[College Name]</td></tr>
<tr><td class="k">Department</td><td>[Department of Computer Engineering]</td></tr>
<tr><td class="k">Project Guide</td><td>[Guide Name]</td></tr>
<tr><td class="k">Academic Year</td><td>[2026-27]</td></tr>
<tr><td class="k">Date</td><td>{C.DATE}</td></tr>
</table>
<div class="team"><div class="tag" style="margin-bottom:3mm">Team members</div>{team}</div>
</div><div class="foot">Repository: github.com/kaushal-o4/hiresense &nbsp;·&nbsp; React · FastAPI · MongoDB · Gemini / Ollama</div></div>"""


def toc(pages):
    rows = []
    for sid, num, title, subs in SECTIONS:
        rows.append(f'<tr><td class="n">{num}</td><td class="t">{e(title)}</td><td class="p">{pages.get(sid, "")}</td></tr>')
        for i, s in enumerate(subs):
            rows.append(f'<tr class="sub"><td></td><td class="t">{e(s)}</td><td class="p">{pages.get(f"m{i}", "")}</td></tr>')
    return f'<h1>Table of Contents</h1><table class="toc">{"".join(rows)}</table>'


def arch_svg():
    box = lambda x, y, w, h, t, s="", fill="#e8effc", stroke="#1d4ed8": (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        f'<text x="{x+w/2}" y="{y+h/2-(6 if s else -4)}" text-anchor="middle" font-size="13" font-weight="700" fill="#0b1f3a">{t}</text>'
        + (f'<text x="{x+w/2}" y="{y+h/2+12}" text-anchor="middle" font-size="10.5" fill="#374151">{s}</text>' if s else ""))
    arrow = lambda x1, y1, x2, y2, label="": (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#1d4ed8" stroke-width="1.6" marker-end="url(#a)"/>'
        + (f'<text x="{(x1+x2)/2}" y="{(y1+y2)/2-5}" text-anchor="middle" font-size="10" fill="#1e3a8a">{label}</text>' if label else ""))
    parts = [
        '<svg viewBox="0 0 700 330" width="100%" xmlns="http://www.w3.org/2000/svg"><defs><marker id="a" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#1d4ed8"/></marker></defs>',
        '<rect x="10" y="10" width="200" height="310" rx="10" fill="#f5f8fd" stroke="#c7d6f5" stroke-dasharray="4 3"/>',
        '<text x="110" y="30" text-anchor="middle" font-size="11" fill="#4b5563" font-weight="600">BROWSER</text>',
        box(25, 45, 170, 70, "React + Vite", "4 portals · Tailwind"),
        box(25, 135, 170, 70, "three.js avatar", "lip sync · 4 interviewers"),
        box(25, 225, 170, 70, "MediaPipe", "on-device monitoring"),
        box(265, 110, 170, 100, "FastAPI", "routers + services", fill="#0b1f3a", stroke="#0b1f3a"),
        box(490, 20, 190, 55, "Google Gemini", "3.5 Flash / Flash-Lite"),
        box(490, 90, 190, 55, "Ollama qwen3:4b", "local fallback"),
        box(490, 160, 190, 55, "Whisper + Kokoro", "speech in / out (local)"),
        box(490, 230, 190, 55, "MiniLM + scikit-learn", "matching · classifier"),
        box(285, 250, 130, 60, "MongoDB", "all data"),
        arrow(195, 80, 265, 140, "REST + SSE"), arrow(195, 260, 265, 190, "events"),
        arrow(435, 140, 490, 50), arrow(435, 150, 490, 117), arrow(435, 165, 490, 187), arrow(435, 180, 490, 255),
        arrow(350, 210, 350, 250),
        "</svg>",
    ]
    svg = "".join(parts)
    # FastAPI box text should be white
    return svg.replace('fill="#0b1f3a">FastAPI', 'fill="#ffffff">FastAPI').replace(
        'fill="#374151">routers + services', 'fill="#cfe0ff">routers + services')


def simple_arch_svg():
    """Three-layer architecture: browser -> backend -> data and AI. Large text, readable when printed."""
    W = 720

    def layer(y, h, title, color):
        return (f'<rect x="10" y="{y}" width="{W-20}" height="{h}" rx="12" fill="{color}" stroke="#9db4e0" stroke-width="1.2"/>'
                f'<text x="28" y="{y+24}" font-size="14" font-weight="800" fill="#0b1f3a">{title}</text>')

    def box(x, y, w, h, t, s="", dark=False):
        fill, stroke, tc, sc = ("#0b1f3a", "#0b1f3a", "#ffffff", "#cfe0ff") if dark else ("#ffffff", "#1d4ed8", "#0b1f3a", "#374151")
        out = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>'
        if s:
            out += (f'<text x="{x+w/2}" y="{y+h/2-3}" text-anchor="middle" font-size="13" font-weight="700" fill="{tc}">{t}</text>'
                    f'<text x="{x+w/2}" y="{y+h/2+14}" text-anchor="middle" font-size="10.5" fill="{sc}">{s}</text>')
        else:
            out += f'<text x="{x+w/2}" y="{y+h/2+5}" text-anchor="middle" font-size="13" font-weight="700" fill="{tc}">{t}</text>'
        return out

    def arrow(x, y1, y2, label):
        return (f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="#1d4ed8" stroke-width="2.2" marker-end="url(#ah)"/>'
                f'<line x1="{x+14}" y1="{y2}" x2="{x+14}" y2="{y1}" stroke="#1d4ed8" stroke-width="2.2" marker-end="url(#ah)"/>'
                f'<text x="{x+26}" y="{(y1+y2)/2+4}" font-size="11.5" font-weight="600" fill="#1e3a8a">{label}</text>')

    p = ['<svg viewBox="0 0 720 560" width="100%" xmlns="http://www.w3.org/2000/svg"><defs><marker id="ah" markerWidth="9" '
         'markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 z" fill="#1d4ed8"/></marker></defs>']
    p.append(layer(10, 130, "1. USER'S BROWSER  (what people see)", "#eef3fc"))
    for i, (t, s) in enumerate([("Student", "portal"), ("Recruiter", "portal"), ("Mentor", "portal"), ("Admin", "portal")]):
        p.append(box(28 + i * 118, 46, 106, 52, t, s))
    p.append(box(510, 46, 190, 52, "Camera + Mic", "voice interview"))
    p.append('<text x="28" y="124" font-size="11" fill="#4b5563">React website · 3D interviewer (three.js) · face check on the device (MediaPipe)</text>')
    p.append(arrow(330, 142, 188, "HTTPS requests / JSON replies"))
    p.append(layer(190, 150, "2. BACKEND SERVER  (the rules of the system) — FastAPI, Python", "#e4ecfa"))
    for i, (t, s) in enumerate([("Login and", "security"), ("Interview", "engine"), ("Resume and", "job matching"),
                                ("English", "coach"), ("Live", "notifications")]):
        p.append(box(28 + i * 136, 228, 124, 62, t, s, dark=True))
    p.append('<text x="28" y="320" font-size="11" fill="#4b5563">Checks who is logged in · decides what each role may see · calls the AI · saves results</text>')
    p.append(arrow(150, 342, 388, "saves and reads data"))
    p.append(arrow(470, 342, 388, "prompts / scores"))
    p.append(layer(390, 160, "3. DATA AND AI", "#eef3fc"))
    p.append(box(28, 428, 200, 100, "MongoDB database", "users, interviews, jobs, scores"))
    p.append(box(250, 428, 215, 46, "Gemini (online AI)", "main model"))
    p.append(box(250, 482, 215, 46, "Ollama (on the laptop)", "backup AI model"))
    p.append(box(485, 428, 215, 46, "Whisper", "speech → text"))
    p.append(box(485, 482, 215, 46, "Kokoro", "text → interviewer voice"))
    p.append("</svg>")
    return "".join(p)


def flow_svg(steps, cols):
    """Numbered boxes in a snake layout with arrows: left-to-right, then right-to-left on the next row."""
    bw, bh, gx, gy = 178, 62, 40, 44
    rows = (len(steps) + cols - 1) // cols
    W = cols * bw + (cols - 1) * gx + 20
    H = rows * bh + (rows - 1) * gy + 20
    pos = []
    for i in range(len(steps)):
        r, c = divmod(i, cols)
        if r % 2:
            c = cols - 1 - c
        pos.append((10 + c * (bw + gx), 10 + r * (bh + gy)))
    p = [f'<svg viewBox="0 0 {W} {H}" width="100%" xmlns="http://www.w3.org/2000/svg"><defs><marker id="fh" markerWidth="9" '
         'markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 z" fill="#1d4ed8"/></marker></defs>']
    for i in range(len(steps) - 1):
        (x1, y1), (x2, y2) = pos[i], pos[i + 1]
        if y1 == y2:
            if x2 > x1:
                p.append(f'<line x1="{x1+bw}" y1="{y1+bh/2}" x2="{x2-4}" y2="{y2+bh/2}" stroke="#1d4ed8" stroke-width="2" marker-end="url(#fh)"/>')
            else:
                p.append(f'<line x1="{x1}" y1="{y1+bh/2}" x2="{x2+bw+4}" y2="{y2+bh/2}" stroke="#1d4ed8" stroke-width="2" marker-end="url(#fh)"/>')
        else:
            p.append(f'<line x1="{x1+bw/2}" y1="{y1+bh}" x2="{x2+bw/2}" y2="{y2-4}" stroke="#1d4ed8" stroke-width="2" marker-end="url(#fh)"/>')
    for i, ((t, s), (x, y)) in enumerate(zip(steps, pos)):
        p.append(f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="9" fill="#ffffff" stroke="#1d4ed8" stroke-width="1.6"/>'
                 f'<circle cx="{x+15}" cy="{y+15}" r="10" fill="#1d4ed8"/>'
                 f'<text x="{x+15}" y="{y+19}" text-anchor="middle" font-size="11" font-weight="800" fill="#fff">{i+1}</text>'
                 f'<text x="{x+bw/2+10}" y="{y+(28 if s else 37)}" text-anchor="middle" font-size="12.5" font-weight="700" fill="#0b1f3a">{e(t)}</text>'
                 + (f'<text x="{x+bw/2}" y="{y+47}" text-anchor="middle" font-size="10.5" fill="#4b5563">{e(s)}</text>' if s else ""))
    p.append("</svg>")
    return "".join(p)


def body(pages):
    out = [f'<div>{toc(pages)}</div>']
    # 1. description
    d = C.DESCRIPTION
    out.append('<div class="section" id="desc"><h1>1. Project Description</h1>')
    out.append(f'<div class="callout"><b>{C.PROJECT}</b> — {e(C.SUBTITLE)}. A full-stack placement-preparation platform '
               'with four portals, an AI interviewer that speaks through a 3D avatar, and explainable scoring.</div>')
    for k in ("Introduction", "Objective", "Problem Statement", "Proposed Solution"):
        out.append(f"<h2>{k}</h2>")
        out.append(ul(d[k]) if k == "Objective" else "".join(f"<p>{e(p)}</p>" for p in d[k]))
    out.append('<h2>Technologies Used</h2><table><tr><th style="width:26%">Layer</th><th>Technology</th></tr>'
               + "".join(f"<tr><td><b>{e(a)}</b></td><td>{e(b)}</td></tr>" for a, b in C.TECH_TABLE) + "</table>")
    out.append("<h2>Expected Outcomes</h2>" + ul(d["Expected Outcomes"]))
    out.append("<h2>Scope of the Project</h2>" + "".join(f"<p>{e(p)}</p>" for p in d["Scope of the Project"]))
    shots = [("student-dashboard.png", "Student dashboard"), ("voice-interview.png", "Live voice interview"),
             ("interview-report.png", "Interview report"), ("recruiter-compare.png", "Recruiter: compare candidates")]
    out.append('<div class="keep"><h2>Screenshots</h2><div class="shots">' + "".join(
        f'<figure><img class="shot" src="data:image/png;base64,{base64.b64encode((SHOTS / f).read_bytes()).decode()}"><figcaption>{c}</figcaption></figure>' for f, c in shots)
        + "</div></div></div>")

    # 2. simple architecture and workflow
    out.append('<div class="section" id="how"><h1>2. How HireSense Works — Simple Architecture and Workflow</h1>'
               '<div class="callout"><b>In one sentence:</b> the student uses a website, the website asks the backend server, '
               'and the server saves data in MongoDB and asks the AI models for questions, scores and feedback.</div>'
               '<h2>2.1 Simple architecture (three layers)</h2>'
               f'<div class="card keep" style="padding:2mm 3mm"><div style="width:84%;margin:0 auto">{simple_arch_svg()}</div></div>'
               '<h3>What the diagram shows</h3><ol style="font-size:9.6pt">' + "".join(f"<li>{e(t)}</li>" for t in C.SIMPLE_ARCH_TEXT) + '</ol></div>')
    out.append('<div class="section"><h2 style="margin-top:0">2.2 Main workflow: the student journey</h2>'
               f'<div class="card keep" style="padding:3mm 4mm">{flow_svg(C.STUDENT_FLOW, 4)}</div>'
               '<h3>Step by step</h3><ol>' + "".join(f"<li>{e(t)}</li>" for t in C.STUDENT_FLOW_TEXT) + '</ol></div>')
    out.append('<div class="section"><h2 style="margin-top:0">2.3 Recruiter and admin workflows</h2><h3>Recruiter</h3>'
               f'<div class="card keep" style="padding:3mm 4mm">{flow_svg(C.RECRUITER_FLOW, 3)}</div><h3>Admin</h3>'
               f'<div class="card keep" style="padding:3mm 4mm">{flow_svg(C.ADMIN_FLOW, 3)}</div>'
               '<h3>Step by step</h3><ol>' + "".join(f"<li>{e(t)}</li>" for t in C.OTHER_FLOW_TEXT) + '</ol></div>')

    # 3. distribution
    pct_line = " · ".join(f'{m["name"]} {m["pct"]}%' for m in C.MEMBERS)
    out.append('<div class="section" id="dist"><h1>3. Team Work Distribution</h1>')
    out.append('<p class="lead">The project was divided into five parts by module, so that each member owns a complete '
               'area end to end and can explain it independently. Yash and Kaushal owned the largest areas (AI engine, '
               'testing and documentation; voice interview, English module and three portals); Samrath, Aryan and '
               f'Shardha owned the backend, the frontend foundation and the student pages. Shares: {pct_line}.</p>')
    out.append('<table><tr><th style="width:14%">Member</th><th>Role</th><th style="width:20%">Contribution</th><th style="width:8%">%</th></tr>'
               + "".join(f'<tr><td><b>{m["name"]}</b></td><td>{e(m["role"])}</td><td><div class="bar"><div style="width:{m["pct"]}%"></div></div></td><td><b>{m["pct"]}%</b></td></tr>'
                         for m in C.MEMBERS)
               + '<tr><td colspan="3" style="text-align:right"><b>Total</b></td><td><b>100%</b></td></tr></table>')
    out.append('<h2>Module responsibility matrix</h2><table><tr><th>Module</th><th>Owner</th><th>Supporting</th></tr>' + "".join(
        f"<tr><td>{e(a)}</td><td><b>{b}</b></td><td>{c}</td></tr>" for a, b, c in [
            ("System architecture, configuration, integration", "Yash", "All"),
            ("AI engine: Gemini/Ollama, interview engine, scoring, resume, matching", "Yash", "Samrath"),
            ("Testing, CI and documentation", "Yash", "All"),
            ("Deployment (Docker, Render, Vercel)", "Yash", "Samrath"),
            ("Live voice interview, speech, 3D avatars", "Kaushal", "Yash"),
            ("Interview monitoring and security module", "Kaushal", "Samrath"),
            ("English learning, vocabulary, daily plan, rewards", "Kaushal", "Yash"),
            ("Mentor, recruiter and admin portals", "Kaushal", "Samrath, Shardha"),
            ("Database (MongoDB data layer), models, seed", "Samrath", "Yash"),
            ("Authentication, security, access control, notifications", "Samrath", "Aryan"),
            ("Frontend setup, design system, layout, API client", "Aryan", "Shardha"),
            ("Student portal pages and frontend tests", "Shardha", "Aryan"),
        ]) + "</table></div>")

    for i, m in enumerate(C.MEMBERS):
        out.append(f'<div class="section" id="m{i}">')
        out.append(f'<div class="member-head"><div class="pct"><b>{m["pct"]}%</b><span>contribution</span></div>'
                   f'<div class="num">3.{i+1} · Team member {i+1} of 5</div><div class="name">{m["name"]}</div>'
                   f'<div class="role">{e(m["role"])}</div></div>')
        out.append(f'<p class="lead">{e(m["summary"])}</p>')
        out.append("<h3>Responsibilities</h3><ol>" + "".join(f"<li>{fmt(r)}</li>" for r in m["responsibilities"]) + "</ol>")
        out.append("<h3>Modules Assigned</h3>" + ul(m["modules"]))
        out.append("<h3>Deliverables</h3>" + ul(m["deliverables"]))
        out.append('<h3>Technologies Used</h3><div class="chips">' + "".join(f'<span class="chip">{e(t)}</span>' for t in m["tech"]) + "</div>")
        out.append("<h3>Workflow</h3><ol>" + "".join(f"<li>{fmt(w)}</li>" for w in m["workflow"]) + "</ol>")
        out.append('<h3>Challenges Faced and Solutions Implemented</h3><table><tr><th style="width:4%">#</th><th style="width:46%">Challenge faced</th><th>Solution implemented</th></tr>'
                   + "".join(f"<tr><td>{j+1}</td><td>{fmt(c)}</td><td>{fmt(s)}</td></tr>" for j, (c, s) in enumerate(m["challenges"])) + "</table>")
        out.append(f'<div class="callout keep"><b>Contribution percentage: {m["pct"]}%</b> of the total project work '
                   f'({pct_line} = 100%).</div>')
        out.append("</div>")

    # 3. timeline
    out.append('<div class="section" id="timeline"><h1>4. Project Timeline</h1>'
               '<p>The project ran from 9 October to 5 November 2026. Phases overlapped because members built their modules in parallel; the lead owned each phase and the supporting members reviewed and helped.</p>'
               '<table class="tight" style="font-size:8.8pt"><tr><th style="width:5%">#</th><th>Phase</th><th style="width:22%">Period</th><th style="width:13%">Lead</th><th style="width:18%">Support</th></tr>'
               + "".join(f"<tr><td>{j+1}</td><td>{e(p)}</td><td>{e(d)}</td><td><b>{l}</b></td><td>{e(s)}</td></tr>"
                         for j, (p, d, l, s) in enumerate(C.TIMELINE)) + "</table>")
    phases = ["Requirements", "Design", "Development", "AI integration", "Testing", "Documentation", "Deployment"]
    involve = {"Yash": "●●●●●●●", "Kaushal": "●●●●●●○", "Samrath": "○●●●●○●", "Aryan": "○●●○○●○", "Shardha": "●○●○●●○"}
    out.append('<h2>Who worked on which phase</h2><table class="tight" style="font-size:8.6pt"><tr><th>Member</th>' + "".join(f'<th style="text-align:center">{p}</th>' for p in phases) + "</tr>"
               + "".join(f'<tr><td><b>{n}</b></td>' + "".join(f'<td style="text-align:center;color:#1d4ed8">{"●" if c == "●" else "–"}</td>' for c in involve[n]) + "</tr>" for n in C.TEAM)
               + '</table><p style="font-size:9pt;color:#4b5563">● = actively involved in the phase.</p></div>')

    # 4. collaboration
    out.append('<div class="section" id="collab"><h1>5. Team Collaboration</h1><p>All five members worked on one shared code base, so clear agreements on communication, ownership and integration were essential.</p>'
               + '<div class="grid2">' + "".join(f'<div class="card"><h4>{e(a)}</h4><p style="margin:0;text-align:left">{e(b)}</p></div>' for a, b in C.COLLABORATION) + "</div>"
               + '<h2>Integration points between members</h2><table class="tight" style="font-size:8.8pt"><tr><th>Interface</th><th>Between</th><th>Agreement</th></tr>'
               + "".join(f"<tr><td>{e(a)}</td><td>{e(b)}</td><td>{e(c)}</td></tr>" for a, b, c in [
                   ("REST API contract (/api/...)", "Samrath ↔ Aryan, Shardha, Kaushal", "Pydantic schemas and the generated Swagger page at /docs"),
                   ("AI gateway functions", "Yash ↔ Kaushal", "Every AI call goes through services/ai_base.py with a JSON schema"),
                   ("Interview session data", "Yash ↔ Kaushal ↔ Shardha", "Same session and answer records for typed and voice interviews and the report page"),
                   ("Access rules", "Samrath ↔ Kaushal", "services/access.py decides who may see which student in the mentor, recruiter and admin portals"),
                   ("Design system", "Aryan ↔ all frontend work", "Colours as CSS variables, shared components in components/ui.jsx"),
                   ("Tests before merge", "Yash ↔ all", "Full backend and frontend suites must pass on GitHub Actions"),
               ]) + "</table></div>")

    # 5. architecture
    out.append('<div class="section" id="arch"><h1>6. Project Architecture (Technical Detail)</h1><div class="callout"><b>Plain summary:</b> this is the same three-layer system as in Section 2 (website, backend server, database and AI), shown with the real technologies. Read Section 2 first; this page is for technical questions in the viva.</div>'
               f'<div class="card" style="padding:4mm">{arch_svg()}</div>'
               + "".join(f"<h3>{e(a)}</h3><p>{fmt(b)}</p>" for a, b in C.ARCHITECTURE)
               + '<h2>Request flow: one typed interview answer</h2><ol>'
               '<li>The student submits an answer in the interview page (Shardha) or the voice room (Kaushal), through the shared API client (Aryan).</li>'
               '<li>The backend checks the login cookie and the student\'s access (Samrath).</li>'
               '<li>The answer is saved in MongoDB and scored by the AI engine through the gateway (Yash).</li>'
               '<li>The score decides the difficulty of the next question; detailed feedback runs in the background.</li>'
               '<li>The report, rewards and progress records are updated, and the mentor and recruiter views read the same data (Kaushal).</li></ol></div>')

    # 6. learning outcomes
    out.append('<div class="section" id="learn"><h1>7. Individual Learning Outcomes</h1>')
    for m in C.MEMBERS:
        out.append(f'<div class="card" style="margin-bottom:4mm"><h4>{m["name"]} — {e(m["role"])} ({m["pct"]}%)</h4><table style="margin:1mm 0 0">'
                   + "".join(f'<tr><td style="width:30%"><b>{e(k)}</b></td><td>{e(v)}</td></tr>' for k, v in m["learning"].items())
                   + "</table></div>")
    out.append("</div>")

    # 7. conclusion
    out.append('<div class="section" id="concl"><h1>8. Conclusion</h1>' + "".join(f"<p>{e(p)}</p>" for p in C.CONCLUSION)
               + '<h2>Summary of contributions</h2><table><tr><th>Member</th><th>Main contribution</th><th>%</th></tr>'
               + "".join(f'<tr><td><b>{m["name"]}</b></td><td>{e(m["role"])}</td><td>{m["pct"]}%</td></tr>' for m in C.MEMBERS)
               + '</table><h2>Declaration</h2><p>We declare that the work described in this report was carried out by the team members named above, and that the division of work reflects each member\'s responsibilities in the project.</p>'
               '<table style="margin-top:8mm"><tr><th>Member</th><th>Signature</th><th>Date</th></tr>'
               + "".join(f'<tr><td style="height:7mm"><b>{n}</b></td><td></td><td></td></tr>' for n in C.TEAM)
               + '<tr><td style="height:7mm"><b>Project Guide</b> [Guide Name]</td><td></td><td></td></tr></table></div>')
    return "".join(out)


def page(inner, css):
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}{css}</style></head><body>{inner}</body></html>'


HEADER = ('<div style="width:100%;font-size:8px;font-family:Segoe UI,Arial;color:#4b5563;padding:0 16mm;display:flex;'
          'justify-content:space-between;border-bottom:1px solid #d6deea;padding-bottom:2px;margin:0 0 0 0">'
          '<span><b style="color:#1d4ed8">HireSense</b> — Team Work Distribution</span><span>Final Year Project Report</span></div>')
FOOTER = ('<div style="width:100%;font-size:8px;font-family:Segoe UI,Arial;color:#4b5563;padding:0 16mm;display:flex;'
          'justify-content:space-between"><span>[College Name] · [Department]</span>'
          '<span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span></div>')


def render(pw_page, doc, header=True):
    pw_page.set_content(doc, wait_until="networkidle")
    pw_page.wait_for_timeout(500)
    opts = dict(format="A4", print_background=True)
    if header:
        opts.update(display_header_footer=True, header_template=HEADER, footer_template=FOOTER,
                    margin={"top": "20mm", "bottom": "18mm", "left": "16mm", "right": "16mm"})
    else:
        opts.update(margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
    return pw_page.pdf(**opts)


def find_pages(pdf_bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    texts = [p.extract_text() or "" for p in reader.pages]
    found = {}
    keys = [(sid, f"{num}. {title}") for sid, num, title, _ in SECTIONS]
    keys += [(f"m{i}", f"3.{i+1} · Team member {i+1} of 5") for i in range(len(C.MEMBERS))]
    for sid, needle in keys:
        n = re.sub(r"\s+", "", needle).lower()
        for idx, t in enumerate(texts):
            if idx == 0:
                continue  # page 1 is the table of contents
            if n in re.sub(r"\s+", "", t).lower():
                found[sid] = idx + 1
                break
    return found, len(reader.pages)


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        first = render(pg, page(body({}), "@page { size: A4; }"))
        pages, n = find_pages(first)
        missing = [s for s, *_ in SECTIONS if s not in pages]
        print("pass 1:", n, "pages; section pages", pages, "missing", missing)
        final = render(pg, page(body(pages), "@page { size: A4; }"))
        pages2, n2 = find_pages(final)
        if pages2 != pages:
            print("page numbers moved, third pass", pages2)
            final = render(pg, page(body(pages2), "@page { size: A4; }"))
        cov = render(pg, page(cover(), COVER_CSS), header=False)
        b.close()
    w = PdfWriter()
    for src in (cov, final):
        for pdf_page in PdfReader(io.BytesIO(src)).pages:
            w.add_page(pdf_page)
    w.add_metadata({"/Title": "HireSense — Team Work Distribution", "/Author": ", ".join(C.TEAM),
                    "/Subject": C.SUBTITLE})
    with open(OUT_PDF, "wb") as f:
        w.write(f)
    print("wrote", OUT_PDF, "pages:", len(w.pages))


if __name__ == "__main__":
    main()
