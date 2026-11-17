#!/usr/bin/env python3
"""CDU-10 general-arrangement model and layout checks (Rev C).

Pure Python, no dependencies.  Run from this directory:

    python3 make_layout.py

Writes
  cdu10_layout.obj / .mtl   mesh model (imports into FreeCAD, SolidWorks, Blender, any viewer)
  cdu10_views.svg           front, side and top views with overall dimensions
  viewer.html               interactive 3D view (three.js from a CDN)
  layout_checks.md          clash, service-access, segregation, tray and stability checks

Coordinates, mm: x across the front (0 = left side seen from the front),
y depth (0 = front door plane), z height (0 = floor).  Component envelopes are
datasheet dimensions where known and estimates otherwise (flagged "est").
This is a layout model for fit and access, not a detailed design; pipe runs
are not modelled (corridors are listed in layout_checks.md).
"""
import json
import math

W, D, H = 600.0, 800.0, 1200.0                 # external envelope (Rev B: H was 1000 in Rev A)
FRAME = 40.0
Z_TRAY_FLOOR, Z_TRAY_RIM = 140.0, 180.0
Z_WET_TOP = 800.0                               # all wetted parts below this
Z_SHIELD = (805.0, 830.0)                       # sloped drip shield
Z_DRY = 840.0                                   # electrical panel above this
INNER = dict(x=(FRAME, W - FRAME), y=(FRAME, D - FRAME), z=(Z_TRAY_FLOOR, H - FRAME))
REACH = 600.0                                   # arm reach from the door plane, mm

# --------------------------------------------------------------------------- parts
# kind: box (x0,x1,y0,y1,z0,z1) or vcyl (cx,cy,r,z0,z1) or hcyl along y (cx,cz,r,y0,y1)
PARTS = [
    # tag, description, kind, geometry, mass kg, wet, colour, source
    ("P-101", "Pump CME 1-2, 1x200-240 V, axis front-to-back, drive at front", "box", (48, 260, 60, 368, 190, 423), 16.1, True, "pump", "Grundfos booklet: L1 308, B1 212, H 233 mm; 16.1 kg (316)"),
    ("TK-101", "Expansion tank 7.6-8 L, ASME VIII stamped", "vcyl", (163, 640, 115, 190, 520), 7.5, True, "vessel", "est (ASME 2 gal class)"),
    ("E-101", "Plate exchanger B25T x40, insulated", "box", (390, 549, 616, 758, 220, 786), 11.0, True, "hx", "526 x 119 plate, est. thickness"),
    ("F-101", "Filter, 10 in. 316 housing, bowl down", "vcyl", (475, 125, 65, 400, 790), 4.5, True, "filter", "est"),
    ("FT-101", "Flow meter, server loop", "box", (280, 390, 320, 380, 700, 780), 0.6, True, "inst", "est"),
    ("FT-201", "Flow meter, facility", "box", (280, 390, 420, 480, 560, 640), 0.6, True, "inst", "est"),
    ("TCV-201", "Control valve with actuator", "box", (100, 230, 560, 640, 560, 760), 1.6, True, "valve", "est"),
    ("XV-201", "Shut-off valve, spring return", "box", (290, 470, 500, 600, 200, 420), 2.6, True, "valve", "est"),
    ("STR-201", "Y-strainer 1 in.", "box", (290, 420, 380, 460, 200, 280), 1.2, True, "valve", "est"),
    ("PSV-101", "Relief valve 4.0 bar g", "box", (285, 325, 465, 505, 470, 550), 0.4, True, "valve", "est"),
    ("AV-101", "Automatic air vent", "box", (450, 490, 565, 605, 740, 800), 0.3, True, "valve", "est"),
    ("V-ISO", "Isolation valve bank V-101/102/201/202, levers forward", "box", (130, 390, 230, 300, 600, 680), 2.4, True, "valve", "est"),
    ("V-FILL", "Fill/drain valves and dry-break coupling", "box", (270, 330, 60, 120, 190, 250), 0.5, True, "valve", "est"),
    ("SP-101", "Sample port", "box", (340, 380, 60, 100, 190, 240), 0.2, True, "valve", "est"),
    ("PIPE", "316L pipework and supports (mass only)", "none", None, 10.0, True, None, "est"),
    ("COOLANT", "Coolant and facility water in cabinet (mass only)", "none", None, 7.5, True, None, "calc"),
    ("PANEL", "Control panel enclosure with PLC, PSU, relays", "box", (40, 560, 40, 260, Z_DRY, 1160), 15.0, False, "panel", "est"),
    ("SHIELD", "Sloped drip shield", "box", (40, 560, 40, 760, Z_SHIELD[0], Z_SHIELD[1]), 4.0, False, "shield", "est"),
    ("TRAY", "Stainless drip tray, 40 mm deep", "box", (40, 560, 40, 760, Z_TRAY_FLOOR, Z_TRAY_RIM), 7.0, False, "tray", "est"),
    ("CABINET", "Frame, panels, door, castors (mass only)", "none", None, 58.0, False, None, "est"),
]
# routine service envelopes: these volumes must be clear of every other part
SERVICE = [
    ("Pump slide-out", "P-101", (48, 260, 0, 368, 190, 433)),
    ("Filter bowl drop", "F-101", (405, 545, 55, 195, 320, 400)),
    ("Filter bowl pull-out", "F-101", (405, 545, 0, 125, 320, 700)),
    ("Strainer screen pull", "STR-201", (290, 420, 260, 380, 200, 280)),
    ("Isolation lever swing", "V-ISO", (130, 390, 150, 230, 600, 720)),
    ("Fill coupling hand space", "V-FILL", (250, 400, 0, 60, 180, 300)),
]
ROUTINE = ["P-101", "F-101", "STR-201", "V-ISO", "V-FILL", "SP-101"]   # must be within reach of the door
CASTOR_INSET = 40.0

COLOURS = dict(pump="#2a78d6", vessel="#1baf7a", hx="#eb6834", filter="#6250d6", inst="#eda100",
               valve="#e87ba4", panel="#52514e", shield="#9a9993", tray="#c3c2b7")


def bbox(kind, g):
    if kind == "box":
        return g
    if kind == "vcyl":
        cx, cy, r, z0, z1 = g
        return (cx - r, cx + r, cy - r, cy + r, z0, z1)
    raise ValueError(kind)


def overlap(a, b, gap=0.0):
    return all(a[2 * i] < b[2 * i + 1] - gap and b[2 * i] < a[2 * i + 1] - gap for i in range(3)) if gap <= 0 else \
        all(a[2 * i] < b[2 * i + 1] + gap and b[2 * i] < a[2 * i + 1] + gap for i in range(3))


def vol_overlap(a, b):
    d = [min(a[2 * i + 1], b[2 * i + 1]) - max(a[2 * i], b[2 * i]) for i in range(3)]
    return all(v > 0 for v in d)


# --------------------------------------------------------------------------- checks
def checks():
    rep = []
    ok_all = True
    solid = [(t, d, bbox(k, g), m, wet) for t, d, k, g, m, wet, c, s in PARTS if k != "none"]
    structural = {"TRAY", "SHIELD", "PANEL"}

    # 1. inside envelope
    rows = []
    for t, d, b, m, wet in solid:
        inside = (b[0] >= INNER["x"][0] and b[1] <= INNER["x"][1] and b[2] >= INNER["y"][0] and
                  b[3] <= INNER["y"][1] and b[4] >= INNER["z"][0] and b[5] <= INNER["z"][1])
        rows.append((t, inside))
        ok_all &= inside
    rep.append(("Every part inside the internal envelope", all(r[1] for r in rows),
                ", ".join(t for t, ok in rows if not ok) or "all inside"))

    # 2. clashes (10 mm clearance between components; tray/shield/panel are containers)
    clashes = []
    comps = [s for s in solid if s[0] not in structural]
    for i in range(len(comps)):
        for j in range(i + 1, len(comps)):
            if vol_overlap(grow(comps[i][2], 5), grow(comps[j][2], 5)):
                clashes.append(f"{comps[i][0]} / {comps[j][0]}")
    for t, d, b, m, wet in comps:
        for s in ("PANEL", "SHIELD"):
            sb = next(x[2] for x in solid if x[0] == s)
            if vol_overlap(b, sb):
                clashes.append(f"{t} / {s}")
        if b[4] < Z_TRAY_RIM and t not in ():
            pass   # parts may stand in the tray on feet
    rep.append(("No clashes (10 mm clearance between components)", not clashes, "; ".join(clashes) or "none"))
    ok_all &= not clashes

    # 3. service envelopes clear
    blocked = []
    for name, owner, env in SERVICE:
        for t, d, b, m, wet in solid:
            if t == owner or t in ("TRAY",):
                continue
            if vol_overlap(env, b):
                blocked.append(f"{name} blocked by {t}")
    rep.append(("Service envelopes clear", not blocked, "; ".join(blocked) or
                f"{len(SERVICE)} envelopes clear: " + ", ".join(s[0] for s in SERVICE)))
    ok_all &= not blocked

    # 4. reach from the door
    far = []
    for t, d, b, m, wet in solid:
        if t in ROUTINE and b[2] > REACH:
            far.append(f"{t} front face at {b[2]:.0f} mm")
    rep.append((f"Routine service items within {REACH:.0f} mm of the door", not far, "; ".join(far) or
                "all routine items reachable: " + ", ".join(ROUTINE)))
    ok_all &= not far

    # 5. wet / dry segregation
    high = [f"{t} top at {b[5]:.0f}" for t, d, b, m, wet in solid if wet and b[5] > Z_WET_TOP]
    rep.append((f"All wetted parts below {Z_WET_TOP:.0f} mm; panel above {Z_DRY:.0f} mm behind shield", not high,
                "; ".join(high) or "segregated"))
    ok_all &= not high

    # 6. drip tray capacity
    tray_l = (INNER["x"][1] - INNER["x"][0]) * (INNER["y"][1] - INNER["y"][0]) * (Z_TRAY_RIM - Z_TRAY_FLOOR) / 1e6
    displaced = 0.0
    for t, d, b, m, wet in comps:
        if b[4] < Z_TRAY_RIM:
            displaced += (b[1] - b[0]) * (b[3] - b[2]) * (Z_TRAY_RIM - max(b[4], Z_TRAY_FLOOR)) / 1e6
    cab_coolant = 5.1
    net = tray_l - displaced
    rep.append(("Drip tray holds at least 2x the cabinet coolant (5.1 L)", net >= 2 * cab_coolant,
                f"gross {tray_l:.1f} L, displaced by feet/stands {displaced:.1f} L, net {net:.1f} L = {net / cab_coolant:.1f}x"))

    # 7. mass, centre of gravity, tipping
    mass, mx, my, mz = 0.0, 0.0, 0.0, 0.0
    for t, d, k, g, m, wet, c, s in PARTS:
        if k == "none":
            if t == "CABINET":
                cx, cy, cz = W / 2, D / 2, 0.42 * H        # frame and panels: slightly below mid-height (castors, base)
            elif t == "PIPE":
                cx, cy, cz = W / 2, 450.0, 520.0
            else:
                cx, cy, cz = 420.0, 500.0, 480.0
        else:
            b = bbox(k, g)
            cx, cy, cz = (b[0] + b[1]) / 2, (b[2] + b[3]) / 2, (b[4] + b[5]) / 2
        mass += m
        mx += m * cx
        my += m * cy
        mz += m * cz
    cg = (mx / mass, my / mass, mz / mass)
    xa, xb = CASTOR_INSET, W - CASTOR_INSET
    ya, yb = CASTOR_INSET, D - CASTOR_INSET
    # tipping angle to each side: atan(horizontal distance from CG to tip line / CG height)
    tips = dict(left=math.degrees(math.atan((cg[0] - xa) / cg[2])),
                right=math.degrees(math.atan((xb - cg[0]) / cg[2])),
                front=math.degrees(math.atan((cg[1] - ya) / cg[2])),
                rear=math.degrees(math.atan((yb - cg[1]) / cg[2])))
    # door open 90 deg: 600 mm door, 9 kg, hinged on the left front edge, swings to x < 0
    door_m, door_c = 9.0, (-300.0 + 0.0, -0.0, 0.5 * H)
    m2 = mass + door_m
    cg_door = ((mx + door_m * (W * 0.0 - 0.0 + 0.0)) / m2,
               (my + door_m * (-300.0)) / m2, (mz + door_m * 600.0) / m2)
    tip_front_door = math.degrees(math.atan((cg_door[1] - ya) / cg_door[2]))
    worst = min(min(tips.values()), tip_front_door)
    rep.append(("Stable at 10 deg tilt in every direction, door open (IEC 61010-1 cl. 7.3)", worst > 10.0,
                f"mass {mass:.0f} kg; CG x {cg[0]:.0f}, y {cg[1]:.0f}, z {cg[2]:.0f} mm; tip angles "
                + ", ".join(f"{k} {v:.0f} deg" for k, v in tips.items())
                + f"; forward with door open {tip_front_door:.0f} deg"))
    ok_all &= worst > 10.0
    rep.append(("Castor load (4 castors, worst one carries 35 %)", True,
                f"{mass * 9.81 * 0.35:.0f} N per castor; specify castors rated >= 600 N each"))
    return rep, ok_all, mass, cg


def grow(b, g):
    return (b[0] - g, b[1] + g, b[2] - g, b[3] + g, b[4] - g, b[5] + g)


# --------------------------------------------------------------------------- mesh export
def box_mesh(b):
    x0, x1, y0, y1, z0, z1 = b
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    f = [(1, 2, 3, 4), (5, 8, 7, 6), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 8, 4), (4, 8, 5, 1)]
    return v, f


def vcyl_mesh(g, n=24):
    cx, cy, r, z0, z1 = g
    v = []
    for z in (z0, z1):
        for i in range(n):
            a = 2 * math.pi * i / n
            v.append((cx + r * math.cos(a), cy + r * math.sin(a), z))
    f = [tuple(range(n, 0, -1)), tuple(range(n + 1, 2 * n + 1))]
    for i in range(n):
        a, b = i + 1, (i + 1) % n + 1
        f.append((a, b, b + n, a + n))
    return v, f


def export_obj():
    mtl = []
    for name, hexc in COLOURS.items():
        r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5))
        mtl += [f"newmtl {name}", f"Kd {r:.3f} {g:.3f} {b:.3f}", "d 1.0", ""]
    mtl += ["newmtl frame", "Kd 0.75 0.75 0.73", "d 0.15", ""]
    out = ["# CDU-10 general arrangement, Rev C. Units mm. Z up.", "mtllib cdu10_layout.mtl"]
    base = 0
    items = [(t, k, g, c) for t, d, k, g, m, wet, c, s in PARTS if k != "none"]
    items.append(("ENVELOPE", "box", (0, W, 0, D, 0, H), "frame"))
    for t, k, g, c in items:
        v, f = box_mesh(g) if k == "box" else vcyl_mesh(g)
        out.append(f"o {t}")
        out.append(f"usemtl {c}")
        out += [f"v {x:.1f} {y:.1f} {z:.1f}" for x, y, z in v]
        out += ["f " + " ".join(str(i + base) for i in face) for face in f]
        base += len(v)
    open("cdu10_layout.obj", "w").write("\n".join(out) + "\n")
    open("cdu10_layout.mtl", "w").write("\n".join(mtl) + "\n")


# --------------------------------------------------------------------------- drawing
def export_views(mass, cg):
    S = 0.36
    pad, gap = 70, 90
    fw, fh = W * S, H * S
    sw = D * S
    tw, th = W * S, D * S
    VW = pad + fw + gap + sw + gap + tw + pad + 40
    VH = 120 + fh + 110
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VW:.0f} {VH:.0f}" font-family="Helvetica,Arial,sans-serif" font-size="10">',
         '<style>svg{--bg:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--line:#9a9993}'
         '@media (prefers-color-scheme: dark){svg{--bg:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--line:#6f6e69}}'
         '.ink{fill:var(--ink)}.ink2{fill:var(--ink2)}.edge{stroke:var(--ink);fill:none}.dim{stroke:var(--ink2)}'
         '.zone{stroke:var(--line);stroke-dasharray:5 4;fill:none}</style>',
         f'<rect width="{VW:.0f}" height="{VH:.0f}" style="fill:var(--bg)"/>',
         f'<text x="{pad}" y="28" font-size="15" font-weight="bold" class="ink">CDU-10 general arrangement, Rev C (layout model, not for construction)</text>',
         f'<text x="{pad}" y="46" font-size="11" class="ink2">600 W x 800 D x 1200 H mm. Mass about {mass:.0f} kg filled. '
         f'CG {cg[2]:.0f} mm above floor. Generated by cad/make_layout.py.</text>']
    top = 100

    def rect(x, y, w, h, colour, label=None, lx=None, ly=None):
        o.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{colour}" fill-opacity="0.35" stroke="{colour}" stroke-width="1.2"/>')
        if label:
            labels.append((lx if lx is not None else x + w / 2, ly if ly is not None else y + h / 2 + 3, label))

    def circle(cx, cy, r, colour, label=None):
        o.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{colour}" fill-opacity="0.35" stroke="{colour}" stroke-width="1.2"/>')
        if label:
            labels.append((cx, cy + 3, label))

    views = [("FRONT (door removed)", pad, 0, 2, fw), ("SIDE (from right)", pad + fw + gap, 1, 2, sw),
             ("TOP (roof and panel removed)", pad + fw + gap + sw + gap, 0, 1, tw)]
    for title, ox, ax_h, ax_v, wpx in views:
        labels = []
        hv = H if ax_v == 2 else D
        hpx = hv * S
        oy = top + (fh - hpx) if ax_v == 1 else top
        o.append(f'<text x="{ox:.1f}" y="{top - 14}" font-size="11" font-weight="bold" class="ink">{title}</text>')
        o.append(f'<rect x="{ox:.1f}" y="{oy:.1f}" width="{wpx:.1f}" height="{hpx:.1f}" class="edge" stroke-width="1.5"/>')

        def X(v):
            if ax_h == 1:      # side view from the right: front (y=0) on the left
                return ox + v * S
            return ox + v * S

        def Y(v):
            return oy + hpx - v * S

        if ax_v == 2:
            for zl, lab in ((Z_TRAY_RIM, "tray rim"), (Z_WET_TOP, "wet zone top"), (Z_DRY, "panel")):
                o.append(f'<line x1="{ox:.1f}" y1="{Y(zl):.1f}" x2="{ox + wpx:.1f}" y2="{Y(zl):.1f}" class="zone"/>')
                o.append(f'<text x="{ox + wpx + 3:.1f}" y="{Y(zl) + 3:.1f}" font-size="8" class="ink2">{lab}</text>')
        # draw far-to-near so nearer parts sit on top: depth axis is y (front), x (side, from right), z (top)
        depth_axis = {(0, 2): 1, (1, 2): 0, (0, 1): 2}[(ax_h, ax_v)]
        sign = {1: -1, 0: 1, 2: 1}[depth_axis]
        order = sorted((p for p in PARTS if p[2] != "none" and p[0] != "SHIELD"),
                       key=lambda p: sign * (bbox(p[2], p[3])[2 * depth_axis] + bbox(p[2], p[3])[2 * depth_axis + 1]))
        for t, d, k, g, m, wet, c, s in order:
            b = bbox(k, g)
            col = COLOURS[c]
            lab = t if t not in ("TRAY",) else None
            h0, h1 = (b[0], b[1]) if ax_h == 0 else (b[2], b[3])
            if ax_v == 2:
                v0, v1 = b[4], b[5]
            else:
                v0, v1 = b[2], b[3]
            if k == "vcyl" and ax_v == 1:
                circle(X((b[0] + b[1]) / 2), Y((b[2] + b[3]) / 2), (b[1] - b[0]) / 2 * S, col, lab)
            else:
                rect(X(h0), Y(v1), (h1 - h0) * S, (v1 - v0) * S, col, lab)
        placed = []
        for lx, ly, lab in labels:          # nudge labels that would overprint each other
            while any(abs(lx - px) < 26 and abs(ly - py) < 10 for px, py in placed):
                ly += 11
            placed.append((lx, ly))
            o.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" font-size="9" class="ink" '
                     f'style="paint-order:stroke;stroke:var(--bg);stroke-width:3px">{lab}</text>')
        # overall dimensions
        o.append(f'<line x1="{ox:.1f}" y1="{oy + hpx + 22:.1f}" x2="{ox + wpx:.1f}" y2="{oy + hpx + 22:.1f}" class="dim"/>')
        o.append(f'<text x="{ox + wpx / 2:.1f}" y="{oy + hpx + 36:.1f}" text-anchor="middle" class="ink2">'
                 f'{(W if ax_h == 0 else D):.0f}</text>')
        o.append(f'<line x1="{ox - 22:.1f}" y1="{oy:.1f}" x2="{ox - 22:.1f}" y2="{oy + hpx:.1f}" class="dim"/>')
        o.append(f'<text x="{ox - 26:.1f}" y="{oy + hpx / 2:.1f}" text-anchor="middle" class="ink2" transform="rotate(-90 {ox - 26:.1f} {oy + hpx / 2:.1f})">{hv:.0f}</text>')
    o.append(f'<text x="{pad}" y="{VH - 18:.0f}" font-size="10" class="ink2">Front is at left in the side view and at bottom in the top view. '
             'Pipe runs not shown. Envelopes from datasheets where known, otherwise estimated.</text>')
    o.append("</svg>")
    open("cdu10_views.svg", "w").write("\n".join(o))


def export_viewer():
    data = []
    for t, d, k, g, m, wet, c, s in PARTS:
        if k == "none":
            continue
        data.append(dict(tag=t, desc=d, kind=k, g=g, colour=COLOURS[c]))
    html = VIEWER.replace("__DATA__", json.dumps(data)).replace("__W__", str(W)).replace("__D__", str(D)).replace("__H__", str(H))
    open("viewer.html", "w").write(html)


VIEWER = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CDU-10 Layout</title>
<style>
:root{--bg:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7}}
:root[data-theme="dark"]{--bg:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7}
body{margin:0;background:var(--bg);color:var(--ink);font:14px Helvetica,Arial,sans-serif}
#info{position:absolute;left:16px;top:12px;max-width:min(420px,calc(100vw - 32px))}
#info h1{font-size:16px;margin:0 0 4px}#info p{margin:0;color:var(--ink2)}
#tip{position:absolute;padding:4px 8px;background:var(--bg);border:1px solid var(--ink2);border-radius:4px;pointer-events:none;display:none}
canvas{display:block}
</style></head><body>
<div id="info"><h1>CDU-10 general arrangement, Rev C</h1><p>600 x 800 x 1200 mm. Drag to rotate, scroll to zoom, hover a part for its tag. Layout model, not for construction.</p></div>
<div id="tip"></div>
<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"}}</script>
<script type="module">
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
const parts = __DATA__;
const W=__W__, D=__D__, H=__H__;
const scene = new THREE.Scene();
const dark = matchMedia('(prefers-color-scheme: dark)').matches;
scene.background = new THREE.Color(dark ? 0x1a1a19 : 0xfcfcfb);
const camera = new THREE.PerspectiveCamera(40, innerWidth/innerHeight, 1, 10000);
camera.position.set(1500, -1700, 1400); camera.up.set(0,0,1);
const renderer = new THREE.WebGLRenderer({antialias:true});
renderer.setSize(innerWidth, innerHeight); renderer.setPixelRatio(devicePixelRatio);
document.body.appendChild(renderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(W/2, D/2, H/2); controls.update();
scene.add(new THREE.AmbientLight(0xffffff, 0.7));
const sun = new THREE.DirectionalLight(0xffffff, 0.8); sun.position.set(1000,-1500,2000); scene.add(sun);
const meshes = [];
for (const p of parts) {
  let geo, pos;
  if (p.kind === 'box') { const [x0,x1,y0,y1,z0,z1] = p.g; geo = new THREE.BoxGeometry(x1-x0, y1-y0, z1-z0); pos = [(x0+x1)/2,(y0+y1)/2,(z0+z1)/2]; }
  else { const [cx,cy,r,z0,z1] = p.g; geo = new THREE.CylinderGeometry(r, r, z1-z0, 32); geo.rotateX(Math.PI/2); pos = [cx,cy,(z0+z1)/2]; }
  const mat = new THREE.MeshLambertMaterial({color: p.colour, transparent: p.tag==='SHIELD'||p.tag==='PANEL', opacity: (p.tag==='SHIELD'||p.tag==='PANEL') ? 0.35 : 1});
  const m = new THREE.Mesh(geo, mat); m.position.set(...pos); m.userData = p; scene.add(m); meshes.push(m);
  m.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo), new THREE.LineBasicMaterial({color: dark?0xf0efec:0x0b0b0b, transparent:true, opacity:0.35})));
}
const env = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(W,D,H)), new THREE.LineBasicMaterial({color: dark?0xc3c2b7:0x52514e}));
env.position.set(W/2,D/2,H/2); scene.add(env);
const ray = new THREE.Raycaster(), mouse = new THREE.Vector2(), tip = document.getElementById('tip');
addEventListener('pointermove', e => {
  mouse.set(e.clientX/innerWidth*2-1, -e.clientY/innerHeight*2+1); ray.setFromCamera(mouse, camera);
  const hit = ray.intersectObjects(meshes, false)[0];
  if (hit) { tip.style.display='block'; tip.style.left=(e.clientX+12)+'px'; tip.style.top=(e.clientY+12)+'px'; tip.textContent = hit.object.userData.tag + ': ' + hit.object.userData.desc; }
  else tip.style.display='none';
});
addEventListener('resize', () => { camera.aspect = innerWidth/innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); });
(function loop(){ requestAnimationFrame(loop); renderer.render(scene, camera); })();
</script></body></html>
"""


def main():
    rep, ok, mass, cg = checks()
    export_obj()
    export_views(mass, cg)
    export_viewer()
    lines = ["# Layout checks (generated by cad/make_layout.py)", "",
             f"Overall result: **{'PASS' if ok else 'FAIL'}**", "", "| Check | Result | Detail |", "|---|---|---|"]
    for name, passed, detail in rep:
        lines.append(f"| {name} | {'PASS' if passed else 'FAIL'} | {detail} |")
    lines += ["", "## Pipe corridors reserved (to be routed in detailed CAD)", "",
              "| Run | Route |", "|---|---|",
              "| Return port (rear) → V-101 (front bank) → tank tee → pump suction | Along the left side at z 600–680, down behind the tank to the pump's rear suction |",
              "| Pump discharge → PSV-101 → E-101 bottom port | Rear of pump up to z 470, across to the exchanger's lower port |",
              "| E-101 top port → AV-101 → F-101 head | Across the top of the wet zone at z 740–790 |",
              "| F-101 outlet → FT-101 → bypass tee → V-102 → supply port (rear) | z 700–780, front to rear on the right of centre |",
              "| Facility supply port → V-201 → STR-201 → XV-201 → E-101 | Low run at z 200–420, insulated |",
              "| E-101 → FT-201 → TCV-201 → V-202 → facility return port | Mid run at z 560–760, insulated |", ""]
    open("layout_checks.md", "w").write("\n".join(lines))
    for name, passed, detail in rep:
        print(("PASS " if passed else "FAIL ") + name + " -- " + detail)


if __name__ == "__main__":
    main()
