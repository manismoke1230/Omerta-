#!/usr/bin/env python3
"""Generate the simplified P&ID (../04-pid.svg). Run from this directory."""
W, H = 1280, 760
o = []
A = o.append
A(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="Helvetica,Arial,sans-serif" font-size="12">')
A(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
A('<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="context-stroke"/></marker></defs>')
A('<text x="30" y="34" font-size="18" font-weight="bold">CDU-10 simplified P&amp;ID - Rev B (preliminary design, not for construction)</text>')
TCS, FWS, INK = "#c2410c", "#1d4ed8", "#111827"
YT, YB = 190, 520          # top and bottom process lines
def line(x1, y1, x2, y2, c, arrow=False, dash=False):
    A(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{c}" stroke-width="3"'
      + (' marker-end="url(#a)"' if arrow else '') + (' stroke-dasharray="6 5"' if dash else '') + '/>')
def box(x, y, tag, desc, c, w=84, h=40):
    A(f'<rect x="{x-w/2}" y="{y-h/2}" width="{w}" height="{h}" rx="5" fill="#fff" stroke="{c}" stroke-width="2"/>')
    A(f'<text x="{x}" y="{y-2}" text-anchor="middle" font-weight="bold" fill="{INK}">{tag}</text>')
    A(f'<text x="{x}" y="{y+13}" text-anchor="middle" font-size="10" fill="{INK}">{desc}</text>')
def inst(x, y, tag, up=True):
    cy = y - 46 if up else y + 46
    A(f'<line x1="{x}" y1="{y}" x2="{x}" y2="{cy + (17 if up else -17)}" stroke="{INK}" stroke-width="1"/>')
    A(f'<circle cx="{x}" cy="{cy}" r="17" fill="#fff" stroke="{INK}" stroke-width="1.5"/>')
    a, b = tag.split("-")
    A(f'<text x="{x}" y="{cy-1}" text-anchor="middle" font-size="10" font-weight="bold">{a}</text>')
    A(f'<text x="{x}" y="{cy+10}" text-anchor="middle" font-size="10">{b}</text>')
def label(x, y, t, c=INK, anchor="middle", size=12, bold=False):
    A(f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" fill="{c}"' + (' font-weight="bold"' if bold else '') + f'>{t}</text>')

# enclosure boundary
A(f'<rect x="150" y="80" width="980" height="600" rx="10" fill="none" stroke="#6b7280" stroke-width="1.5" stroke-dasharray="10 6"/>')
label(160, 100, "CDU-10 enclosure / drip tray boundary", "#6b7280", "start", 11)

# heat exchanger
A(f'<rect x="600" y="{YT-30}" width="80" height="{YB-YT+60}" fill="#f3f4f6" stroke="{INK}" stroke-width="2"/>')
for i in range(1, 8):
    A(f'<line x1="{600+i*10}" y1="{YT-30}" x2="{600+i*10}" y2="{YB+30}" stroke="#9ca3af"/>')
label(640, YT-40, "E-101", bold=True); label(640, YB+46, "brazed plate HX, 30 plates", size=10)
label(640, YB+59, "counterflow", size=10)

# ---------------- FWS (left) ----------------
line(40, YB, 600, YB, FWS, True)
line(600, YT, 40, YT, FWS, True)
label(40, YB+22, "FWS SUPPLY", FWS, "start", bold=True); label(40, YB+36, "water, 18-32 C", FWS, "start", 10)
label(40, YT-12, "FWS RETURN", FWS, "start", bold=True)
box(205, YB, "V-201", "isolation", FWS, 66); box(290, YB, "STR-201", "Y-strainer", FWS, 72)
box(380, YB, "XV-201", "shut-off FC", FWS, 76)
inst(460, YB, "TT-201"); inst(510, YB, "PT-201"); 
box(555, YB+70, "V-203", "drain", FWS, 60, 34); line(555, YB, 555, YB+53, FWS)
inst(560, YT, "TT-202"); box(480, YT, "FT-201", "mag flow", FWS, 72)
box(385, YT, "TCV-201", "control 2-way", FWS, 86)
inst(310, YT, "PT-202"); box(205, YT, "V-202", "isolation", FWS, 66)
box(270, YT+75, "PSV-201", "thermal relief", FWS, 86, 34); line(270, YT, 270, YT+58, FWS)

# ---------------- TCS (right) ----------------
line(1240, YT, 680, YT, TCS, True)
line(680, YB, 1240, YB, TCS, True)
label(1240, YT-30, "TCS RETURN (from IT)", TCS, "end", bold=True)
label(1240, YB+40, "TCS SUPPLY (to IT)", TCS, "end", bold=True); label(1240, YB+54, "PG25, 30 L/min, 32 C", TCS, "end", 10)
box(1085, YT, "V-101", "isolation", TCS, 66)
inst(1020, YT, "TT-102"); inst(970, YT, "PT-101")
box(905, YT+80, "TK-101", "expansion 8 L", TCS, 90, 36); line(905, YT, 905, YT+62, TCS)
A(f'<circle cx="820" cy="{YT}" r="24" fill="#fff" stroke="{TCS}" stroke-width="2"/>')
A(f'<path d="M832 {YT-20} L796 {YT} L832 {YT+20}" fill="none" stroke="{TCS}" stroke-width="2"/>')
label(820, YT-32, "P-101", bold=True); label(820, YT+40, "VSD pump", size=10)
inst(760, YT, "PT-102")
box(725, YT+85, "PSV-101", "4.0 bar g", TCS, 76, 36); line(725, YT, 725, YT+67, TCS)
label(725, YT+118, "to drip tray", size=10)
box(700, YT-80, "AV-101", "air vent", TCS, 66, 34); line(700, YT, 700, YT-63, TCS)
box(760, YB, "F-101", "filter 50 um", TCS, 84)
inst(760, YB, "PDT-101", up=False)
inst(840, YB, "TT-101"); box(905, YB, "FT-101", "mag flow", TCS, 72); inst(975, YB, "PT-103")
box(1085, YB, "V-102", "isolation", TCS, 66)
# bypass
line(1025, YB, 1025, YT, TCS, False, True); box(1025, (YT+YB)/2+30, "V-105", "min-flow bypass", TCS, 96, 36)
# fill / drain / sample
box(840, YB+80, "V-103/104", "fill / drain", TCS, 90, 34); line(840, YB, 840, YB+63, TCS)
box(960, YB+80, "SP-101", "sample port", TCS, 84, 34); line(960, YB, 960, YB+63, TCS)

# non-process instruments
box(260, 640, "LDS-301", "tray leak rope", INK, 100, 34); box(380, 640, "LDS-302", "hose-end leak", INK, 100, 34)
box(500, 640, "AT-301", "room T / RH", INK, 90, 34)
box(430, 118, "PLC + HMI", "control panel (dry zone)", INK, 150, 40)
label(40, 720, "Blue: facility water (FWS).  Orange: technology coolant (TCS, PG25).  FC = fail closed.  Dashed = minimum-flow bypass.", size=11, anchor="start")
label(40, 738, "Circles are transmitters: TT temperature, PT pressure, PDT differential pressure.  See 04-pid-and-equipment.md for the full list.", size=11, anchor="start")
A('</svg>')
open("../04-pid.svg", "w").write("\n".join(o))
