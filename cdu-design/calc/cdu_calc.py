#!/usr/bin/env python3
"""CDU-10 preliminary sizing calculations (Rev B).

Pure-Python, no dependencies.  Run:  python3 cdu_calc.py > results.txt
Importable: cdu_sim.py uses the fluid, exchanger and pump models from here.

Every number marked ASSUMED is an engineering assumption that must be
replaced with vendor/site data at the hold points listed in
../07-hold-points.md.  Nothing here is a validated rating.
"""
import math

# ----------------------------------------------------------------------------
# Fluids (near 30-35 C)
# ----------------------------------------------------------------------------
# PG25: rho, cp from Dow DOWFROST LC25 typical properties (as cited in the
# feasibility report).  Viscosity: Dow-linked listing gives 2.72 mPa.s at 20 C
# and 1.15 mPa.s at 50 C; log-linear interpolation at the 34.5 C loop mean
# gives 1.79 mPa.s.  Conductivity: 0.485 W/m.K published at 50 C; 0.475 used
# at 35 C (Rev B).
def pg25_mu(t_c):
    return math.exp(math.log(2.72e-3) + (t_c - 20.0) * (math.log(1.15e-3) - math.log(2.72e-3)) / 30.0)
PG25 = dict(name="PG25", rho=1027.8, cp=3890.0, mu=pg25_mu(34.5), k=0.475)
# Water: NIST values near 30 C.
WATER = dict(name="water", rho=995.7, cp=4180.0, mu=0.80e-3, k=0.615)
for f in (PG25, WATER):
    f["Pr"] = f["mu"] * f["cp"] / f["k"]

LPM = 1.0 / 60000.0  # m3/s per L/min
G = 9.81

# ----------------------------------------------------------------------------
# Design point (decisions D-03..D-06)
# ----------------------------------------------------------------------------
Q_RATED = 10_000.0          # W
TCS_FLOW = 30.0             # L/min PG25
FWS_FLOW = 24.0             # L/min water
T_FWS_IN = 27.0             # C  rating condition
T_TCS_SUPPLY = 32.0         # C  rating condition (approach 5 K)
EXT_DP_AVAIL = 100e3        # Pa available to the IT loop at CDU connections

# ----------------------------------------------------------------------------
# Brazed plate heat exchanger geometry -- SWEP B25T class (long 119 mm plate)
# The short B10T plate (289 x 119, published) was scanned first and rejected:
# 40 plates gave only ~1 % clean UA margin (see ../03-calculations.md).
# B25T: 526 x 119 mm plate, ports 479 x 72 mm -- ASSUMED from catalogue memory,
# as are effective width, pressing depth and chevron angle.
# Rev B: SWEP B25T specification sheets give 1.1 m2 for 20 plates and 3.02 m2
# for 50 plates, i.e. ~0.062 m2 per thermal plate; the enlargement factor is set
# to 1.21 so the model matches that area.  Channel volume 0.114 dm3 (SWEP B25).
# Vendor rating run replaces all of this (HP-03).
# ----------------------------------------------------------------------------
HX = dict(L=0.479, w=0.107, b=2.0e-3, phi_enl=1.21, chev_deg=60.0,
          t_wall=0.3e-3, k_wall=15.0, d_port=0.024, ch_vol=0.114e-3)
HX["Dh"] = 2 * HX["b"] / HX["phi_enl"]
HX.update(cal_h=1.0, cal_f=1.0, k_port=1.4)        # set by calibrate_to_swep() below
HX_PLATES = 40      # Rev B: 40 plates keeps dP under 15 kPa per side with the SWEP-calibrated model
HX["A_plate"] = HX["L"] * HX["w"] * HX["phi_enl"]


def martin(Re, Pr, chev_deg):
    """Martin (1996) chevron-plate correlation. Returns (f_darcy, Nu)."""
    p = math.radians(chev_deg)
    if Re < 2000:
        f0 = 64.0 / Re
        f1 = 597.0 / Re + 3.85
    else:
        f0 = (1.8 * math.log10(Re) - 1.5) ** -2
        f1 = 39.0 / Re ** 0.289
    inv = (math.cos(p) / math.sqrt(0.18 * math.tan(p) + 0.36 * math.sin(p) + f0 / math.cos(p))
           + (1 - math.cos(p)) / math.sqrt(3.8 * f1))
    f = 1.0 / inv ** 2
    Nu = 0.122 * Pr ** (1 / 3) * (f * Re ** 2 * math.sin(2 * p)) ** 0.374
    return f, Nu


KUMAR_HT = [(20, 0.562, 0.326), (400, 0.306, 0.529), (1e9, 0.108, 0.703)]  # beta=60 deg from horizontal
KUMAR_HT_30 = [(10, 0.718, 0.349), (1e9, 0.348, 0.663)]                      # beta<=30 deg from horizontal


def kumar_nu(Re, Pr, table):
    """Kumar (1984) plate correlation, Nu = Ch Re^n Pr^(1/3).  Constants as
    tabulated in Kakac & Liu, 'Heat Exchangers: Selection, Rating and Thermal
    Design' -- transcribed from memory; used only as a cross-check.  Kumar's
    angle is measured from the horizontal, so beta=30 matches Martin's 60."""
    for re_max, ch, n in table:
        if Re <= re_max:
            return ch * Re ** n * Pr ** (1 / 3)


def side(fluid, flow_lpm, n_ch):
    """Per-side film coefficient and pressure drop."""
    V = flow_lpm * LPM
    u = V / n_ch / (HX["w"] * HX["b"])
    Re = fluid["rho"] * u * HX["Dh"] / fluid["mu"]
    f, Nu = martin(Re, fluid["Pr"], HX["chev_deg"])
    h = Nu * fluid["k"] / HX["Dh"] * HX["cal_h"]
    dp_ch = f * HX["L"] / HX["Dh"] * fluid["rho"] * u ** 2 / 2 * HX["cal_f"]
    u_port = V / (math.pi / 4 * HX["d_port"] ** 2)
    dp_port = HX["k_port"] * fluid["rho"] * u_port ** 2 / 2
    h_kumar = kumar_nu(Re, fluid["Pr"], KUMAR_HT_30) * fluid["k"] / HX["Dh"]
    return dict(u=u, Re=Re, h=h, h_kumar=h_kumar, dp=dp_ch + dp_port)


def hx_perf(n_plates, tcs_lpm, fws_lpm):
    """Clean UA and pressure drops for an n-plate single-pass counterflow unit."""
    n_ch_tot = n_plates - 1
    n_tcs = n_ch_tot // 2
    n_fws = n_ch_tot - n_tcs
    s1 = side(PG25, tcs_lpm, n_tcs)
    s2 = side(WATER, fws_lpm, n_fws)
    U = 1.0 / (1 / s1["h"] + 1 / s2["h"] + HX["t_wall"] / HX["k_wall"])
    A = (n_plates - 2) * HX["A_plate"]
    U_k = 1.0 / (1 / s1["h_kumar"] + 1 / s2["h_kumar"] + HX["t_wall"] / HX["k_wall"])
    return dict(U=U, A=A, UA=U * A, UA_kumar=U_k * A, tcs=s1, fws=s2, n_tcs=n_tcs, n_fws=n_fws)


# ----------------------------------------------------------------------------
# Calibration against a published SWEP SSP rating (Rev B).
# B25THx50/1P, counter-current, ethylene glycol 25 mass% / water, 14.0 kW:
# 0.7349 / 0.6090 kg/s, 24 / 25 channels, clean OHTC 3500 W/m2K,
# pressure drop 11.4 / 7.36 kPa total, of which ports 1.23 / 0.873 kPa,
# port diameter 24 mm, port velocity 1.58 / 1.36 m/s.
# Uncalibrated Martin gave U 2541 W/m2K (0.73x) and dP 5.3 / 3.4 kPa (0.46x).
# ----------------------------------------------------------------------------
SWEP_CASE = dict(
    f1=dict(name="EG25", rho=1026.0, cp=3810.0, mu=0.969e-3, k=0.5042, kgs=0.7349),
    f2=dict(name="water", rho=990.0, cp=4180.0, mu=0.589e-3, k=0.6383, kgs=0.6090),
    plates=50, U=3500.0, dp1=11.4e3, dp2=7.36e3, dp_port1=1.23e3, u_port1=1.58)


def _swep_eval():
    c = SWEP_CASE
    for f in (c["f1"], c["f2"]):
        f["Pr"] = f["mu"] * f["cp"] / f["k"]
    nch = c["plates"] - 1
    l1, l2 = c["f1"]["kgs"] / c["f1"]["rho"] * 60000, c["f2"]["kgs"] / c["f2"]["rho"] * 60000
    s1, s2 = side(c["f1"], l1, nch // 2), side(c["f2"], l2, nch - nch // 2)
    U = 1.0 / (1 / s1["h"] + 1 / s2["h"] + HX["t_wall"] / HX["k_wall"])
    return U, s1["dp"], s2["dp"]


def calibrate_to_swep():
    c = SWEP_CASE
    HX["k_port"] = 2 * c["dp_port1"] / (c["f1"]["rho"] * c["u_port1"] ** 2)
    lo, hi = 0.5, 3.0                       # heat transfer: one factor on both film coefficients
    for _ in range(50):
        HX["cal_h"] = (lo + hi) / 2
        lo, hi = (HX["cal_h"], hi) if _swep_eval()[0] < c["U"] else (lo, HX["cal_h"])
    lo, hi = 0.5, 6.0                       # friction: one factor, fitted to the sum of both sides
    for _ in range(50):
        HX["cal_f"] = (lo + hi) / 2
        _, d1, d2 = _swep_eval()
        lo, hi = (HX["cal_f"], hi) if d1 + d2 < c["dp1"] + c["dp2"] else (lo, HX["cal_f"])
    return _swep_eval()


SWEP_FIT = calibrate_to_swep()


def eff_counterflow(UA, C1, C2):
    Cmin, Cmax = min(C1, C2), max(C1, C2)
    cr, ntu = Cmin / Cmax, UA / Cmin
    if abs(1 - cr) < 1e-9:
        return ntu / (1 + ntu), Cmin
    e = (1 - math.exp(-ntu * (1 - cr))) / (1 - cr * math.exp(-ntu * (1 - cr)))
    return e, Cmin


def cap(f, lpm):
    return f["rho"] * f["cp"] * lpm * LPM  # W/K


def tcs_supply_temp(n_plates, q, tcs_lpm, fws_lpm, t_fws_in, ua_derate=1.0):
    """TCS supply temperature needed to reject q at given conditions."""
    p = hx_perf(n_plates, tcs_lpm, fws_lpm)
    C1, C2 = cap(PG25, tcs_lpm), cap(WATER, fws_lpm)
    e, Cmin = eff_counterflow(p["UA"] * ua_derate, C1, C2)
    t_hot_in = t_fws_in + q / (e * Cmin)
    return t_hot_in - q / C1, t_hot_in


def fws_flow_for_setpoint(n_plates, q, tcs_lpm, t_fws_in, t_supply_sp, ua_derate=1.0):
    """Facility flow the control valve must pass to hold the supply setpoint."""
    lo, hi = 0.5, 60.0
    if tcs_supply_temp(n_plates, q, tcs_lpm, hi, t_fws_in, ua_derate)[0] > t_supply_sp:
        return None
    for _ in range(60):
        mid = (lo + hi) / 2
        if tcs_supply_temp(n_plates, q, tcs_lpm, mid, t_fws_in, ua_derate)[0] > t_supply_sp:
            lo = mid
        else:
            hi = mid
    return hi


# ----------------------------------------------------------------------------
# Pump curves, H [m] = c0 n^2 + c1 n Q + c2 Q^2, Q in m3/h, n = speed fraction.
# CME 1-3: read from the Grundfos product datasheet curve for 98394758 (100 %).
# CME 1-2: read from the Grundfos CM/CME data booklet, CME 1 curve page, -2 stages.
# Values read by eye from the published charts: +/-0.5 m.  Rev B (published data).
# ----------------------------------------------------------------------------
PUMPS = {"CME 1-3": (39.6, -1.47, -2.33), "CME 1-2": (25.6, -1.55, -1.24)}
PUMP_CAPS = {"CME 1-3": 0.767, "CME 1-2": 0.95}   # caps giving <= 3.5 bar g dead-head warm
PUMP_SEL = "CME 1-2"
ETA_W2W = 0.27          # wire-to-water: P2 curve x motor/drive (CME 1-3 sheet: P1 470 W for 149 W hydraulic)


def pump_head(q, n, c):
    return c[0] * n * n + c[1] * n * q + c[2] * q * q


def pump_speed_for(q, h, c):
    a, b, cc = c[0], c[1] * q, c[2] * q * q - h
    return (-b + math.sqrt(b * b - 4 * a * cc)) / (2 * a)


def pump_flow_on_system(n, k_sys, c):
    """Flow where the pump curve at speed n meets H = k_sys Q^2."""
    a, b, cc = c[2] - k_sys, c[1] * n, c[0] * n * n
    return (-b - math.sqrt(b * b - 4 * a * cc)) / (2 * a)


def hr(t):
    print("\n" + "=" * 78 + "\n" + t + "\n" + "=" * 78)


def main():
    # ============================================================================
    hr("1. RATING-POINT HEAT BALANCE")
    C_t, C_f = cap(PG25, TCS_FLOW), cap(WATER, FWS_FLOW)
    dT_t, dT_f = Q_RATED / C_t, Q_RATED / C_f
    T_tcs_ret = T_TCS_SUPPLY + dT_t
    T_fws_out = T_FWS_IN + dT_f
    d1, d2 = T_tcs_ret - T_fws_out, T_TCS_SUPPLY - T_FWS_IN
    lmtd = (d1 - d2) / math.log(d1 / d2)
    UA_req = Q_RATED / lmtd
    print(f"TCS  PG25  {TCS_FLOW:.0f} L/min  C={C_t:.0f} W/K  dT={dT_t:.2f} K  {T_tcs_ret:.2f} -> {T_TCS_SUPPLY:.2f} C")
    print(f"FWS  water {FWS_FLOW:.0f} L/min  C={C_f:.0f} W/K  dT={dT_f:.2f} K  {T_FWS_IN:.2f} -> {T_fws_out:.2f} C")
    print(f"LMTD = {lmtd:.2f} K   required UA (clean, no margin) = {UA_req:.0f} W/K")
    print(f"Pr PG25 = {PG25['Pr']:.1f}   Pr water = {WATER['Pr']:.1f}")

    # ============================================================================
    hr("2a. EXCHANGER MODEL CALIBRATED TO A SWEP SSP RATING (B25THx50, EG25/water, 14 kW)")
    c = SWEP_CASE
    print(f"Factors: film coefficients x{HX['cal_h']:.2f}, channel friction x{HX['cal_f']:.2f}, port loss K = {HX['k_port']:.2f}")
    print(f"Fit: U {SWEP_FIT[0]:.0f} W/m2K (SWEP {c['U']:.0f});  dP {SWEP_FIT[1]/1e3:.1f} / {SWEP_FIT[2]/1e3:.2f} kPa "
          f"(SWEP {c['dp1']/1e3:.1f} / {c['dp2']/1e3:.2f})")
    print("Before calibration the model gave U 2541 W/m2K and dP 5.3 / 3.4 kPa for this case.")

    hr("2. PLATE-COUNT SCAN (SWEP B25T geometry, Martin correlation calibrated to SWEP)")
    print(f"Dh = {HX['Dh']*1e3:.2f} mm   area/plate = {HX['A_plate']*1e4:.0f} cm2   chevron = {HX['chev_deg']:.0f} deg")
    print(" N   A[m2]  Re_tcs Re_fws  U[W/m2K]  UA[W/K]  UA/UAreq  dP_tcs[kPa] dP_fws[kPa]")
    for n in (20, 24, 30, 40, 50):
        p = hx_perf(n, TCS_FLOW, FWS_FLOW)
        print(f"{n:3d}  {p['A']:.3f}  {p['tcs']['Re']:5.0f}  {p['fws']['Re']:5.0f}   {p['U']:6.0f}   {p['UA']:6.0f}    {p['UA']/UA_req:4.2f}"
              f"      {p['tcs']['dp']/1e3:5.1f}       {p['fws']['dp']/1e3:5.1f}")
    print("Sensitivity of the chosen size to the ASSUMED chevron angle:")
    N_SEL = HX_PLATES
    for ang in (45.0, 55.0, 60.0, 65.0):
        HX["chev_deg"] = ang
        p = hx_perf(N_SEL, TCS_FLOW, FWS_FLOW)
        print(f"  chevron {ang:.0f} deg: UA/UAreq = {p['UA']/UA_req:4.2f}   dP_tcs = {p['tcs']['dp']/1e3:4.1f} kPa   dP_fws = {p['fws']['dp']/1e3:4.1f} kPa")
    HX["chev_deg"] = 60.0
    sel = hx_perf(N_SEL, TCS_FLOW, FWS_FLOW)
    print(f"SELECTED: {N_SEL} plates.  Clean UA margin = {(sel['UA']/UA_req-1)*100:.0f} %")
    print(f"Cross-check, Kumar correlation (uncalibrated): UA = {sel['UA_kumar']:.0f} W/K, margin {(sel['UA_kumar']/UA_req-1)*100:.0f} %")
    print(f"  hold-up volume per side ~ {sel['n_tcs']*HX['ch_vol']*1e3:.2f} L")

    # ============================================================================
    hr("3. OFF-DESIGN THERMAL PERFORMANCE (selected exchanger, UA derated 20 % for fouling)")
    DER = 0.80
    ts, th = tcs_supply_temp(N_SEL, Q_RATED, TCS_FLOW, FWS_FLOW, T_FWS_IN, DER)
    print(f"Rating check, fouled: 10 kW, FWS 27 C / 24 L/min -> TCS supply {ts:.1f} C (approach {ts-T_FWS_IN:.1f} K)")
    print("\nLowest achievable TCS supply at full facility flow (24 L/min), fouled:")
    print(" load[kW]  FWS_in[C]  TCS_supply[C]  TCS_return[C]  approach[K]")
    for q in (5e3, 10e3, 12e3):
        for tf in (18.0, 27.0, 32.0):
            ts, th = tcs_supply_temp(N_SEL, q, TCS_FLOW, FWS_FLOW, tf, DER)
            print(f"   {q/1e3:4.0f}      {tf:4.0f}        {ts:5.1f}          {th:5.1f}         {ts-tf:4.1f}")
    print("\nFacility flow the control valve must pass to hold a 32 C supply setpoint, fouled:")
    print(" load[kW]  FWS_in[C]  FWS_flow[L/min]  FWS_out[C]")
    for q in (2e3, 5e3, 10e3):
        for tf in (18.0, 22.0, 27.0):
            fl = fws_flow_for_setpoint(N_SEL, q, TCS_FLOW, tf, 32.0, DER)
            if fl is None:
                print(f"   {q/1e3:4.0f}      {tf:4.0f}      not achievable at <=60 L/min")
            else:
                print(f"   {q/1e3:4.0f}      {tf:4.0f}          {fl:5.1f}          {tf + q/cap(WATER, fl):5.1f}")
    print("\nReduced TCS flow case (15 L/min, e.g. GB200-class trays at ~1.5 L/min/kW), 10 kW, FWS 27 C:")
    ts, th = tcs_supply_temp(N_SEL, Q_RATED, 15.0, FWS_FLOW, T_FWS_IN, DER)
    print(f"   TCS supply {ts:.1f} C, return {th:.1f} C")

    # ============================================================================
    hr("4. TCS HYDRAULIC BUDGET AT 30 L/min PG25")
    V = TCS_FLOW * LPM
    D_PIPE = 0.0266   # DN25 sch 10S-ish bore, m
    L_PIPE, F_D, K_SUM = 3.0, 0.03, 12.0   # ASSUMED internal run and fittings
    v = V / (math.pi / 4 * D_PIPE ** 2)
    dp_pipe = (F_D * L_PIPE / D_PIPE + K_SUM) * PG25["rho"] * v ** 2 / 2
    items = [
        ("Plate exchanger, TCS side (calc)", sel["tcs"]["dp"]),
        ("Filter 50 um, at dirty-change limit (ASSUMED)", 30e3),
        ("Flow meter (ASSUMED)", 10e3),
        (f"Internal piping/valves, v={v:.2f} m/s (calc, ASSUMED K)", dp_pipe),
    ]
    dp_int = sum(x[1] for x in items)
    for n, d in items:
        print(f"  {n:55s} {d/1e3:6.1f} kPa")
    print(f"  {'Internal total':55s} {dp_int/1e3:6.1f} kPa")
    print(f"  {'External allowance to IT loop (requirement)':55s} {EXT_DP_AVAIL/1e3:6.1f} kPa")
    dp_tot = dp_int + EXT_DP_AVAIL
    H_req = dp_tot / (PG25["rho"] * G)
    P_hyd = dp_tot * V
    print(f"  {'Pump duty':55s} {dp_tot/1e3:6.1f} kPa = {H_req:.1f} m at {V*3600:.2f} m3/h")
    print(f"  Hydraulic power = {P_hyd:.0f} W")

    # ============================================================================
    hr("5. PUMP SELECTION (published Grundfos curves)")
    Qh = V * 3600
    print(f"Duty: {Qh:.2f} m3/h at {H_req:.1f} m (dirty filter, {EXT_DP_AVAIL/1e3:.0f} kPa to the servers)")
    print(" pump      curve at 100 %                 speed for duty  cap   dead-head at cap  ext. kPa at cap (dirty)  flow at cap")
    P_WARM = 1.15  # bar g static when warm (section 7)
    for name, c in PUMPS.items():
        n_req = pump_speed_for(Qh, H_req, c)
        n_cap = PUMP_CAPS[name]
        p_dead = P_WARM + pump_head(0.0, n_cap, c) * PG25["rho"] * G / 1e5
        h_cap = pump_head(Qh, n_cap, c)
        ext = h_cap * PG25["rho"] * G - dp_int
        k_sys = H_req / Qh ** 2
        q_cap = pump_flow_on_system(n_cap, k_sys, c)
        print(f" {name}  H={c[0]:.1f}n2{c[1]:+.2f}nQ{c[2]:+.2f}Q2   {n_req*100:5.0f} %     {n_cap*100:3.0f} %   {p_dead:5.2f} bar g      "
              f"{ext/1e3:6.0f}                 {q_cap/0.06:5.1f} L/min")
    c = PUMPS[PUMP_SEL]
    print(f"SELECTED: {PUMP_SEL}, speed cap {PUMP_CAPS[PUMP_SEL]*100:.0f} % "
          f"(dead-head under 3.5 bar g warm, relief 4.0 bar g; at least 100 kPa to servers with a dirty filter)")
    print(f"Electrical input at duty ({ETA_W2W*100:.0f} % wire-to-water, from the published P1 curve): "
          f"{P_hyd/ETA_W2W:.0f} W -> heat added to coolant <= that")
    k_clean = (dp_int - 25e3 + 70e3) / (PG25["rho"] * G) / Qh ** 2
    print(f"Speed at 29 L/min with a clean filter and 70 kPa setpoint: "
          f"{pump_speed_for(29 * 0.06, k_clean * (29 * 0.06) ** 2, c)*100:.0f} %")

    # ============================================================================
    hr("6. FACILITY-SIDE PRESSURE REQUIREMENT AND CONTROL VALVE")
    gpm = FWS_FLOW / 3.785
    CV = 4.7
    dp_valve = (gpm / CV) ** 2 * 6894.76
    fitems = [
        ("Plate exchanger, FWS side (calc)", sel["fws"]["dp"]),
        ("Y-strainer, part-loaded (ASSUMED)", 8e3),
        ("Flow meter (ASSUMED)", 7e3),
        ("Piping, isolation and shut-off valves (ASSUMED)", 6e3),
        (f"Control valve Cv {CV} fully open (calc)", dp_valve),
    ]
    dp_f = sum(x[1] for x in fitems)
    for n, d in fitems:
        print(f"  {n:55s} {d/1e3:6.1f} kPa")
    print(f"  {'Required facility supply-return dP at 24 L/min':55s} {dp_f/1e3:6.1f} kPa")
    print(f"  Valve authority = {dp_valve/dp_f:.2f}")

    # ============================================================================
    hr("7. EXPANSION TANK")
    V_SYS = 25.0     # L, design allowance (CDU ~5 L + hoses + IT)
    BETA = 4.5e-4    # 1/K ASSUMED mean volumetric expansion PG25, 15-50 C
    dV = V_SYS * BETA * (50 - 15)
    P_PRE, P_FILL_A, P_MAX_A = 0.8 + 1.013, 1.0 + 1.013, 1.5 + 1.013   # bar abs at tank
    RESERVE = 1.0    # L of make-up reserve before low-pressure alarm
    V_TANK = 8.0
    v_fill = V_TANK * (1 - P_PRE / P_FILL_A)          # water in tank at cold fill
    v_at_max = V_TANK * (1 - P_PRE / P_MAX_A)
    print(f"System volume allowance {V_SYS:.0f} L, expansion 15->50 C = {dV:.2f} L")
    print(f"{V_TANK:.0f} L tank, precharge 0.8 bar g: holds {v_fill:.2f} L at 1.0 bar g fill, {v_at_max:.2f} L at 1.5 bar g")
    print(f"Usable acceptance between fill and 1.5 bar g = {v_at_max - v_fill:.2f} L  (need {dV:.2f} L)")
    p_hot = P_PRE * V_TANK / (V_TANK - v_fill - dV) - 1.013
    print(f"Predicted static pressure when fully warm = {p_hot:.2f} bar g")
    p_loss = P_PRE * V_TANK / (V_TANK - (v_fill - 0.5)) - 1.013
    print(f"Static pressure after losing 0.5 L of coolant (cold) = {p_loss:.2f} bar g -> low-pressure alarm 0.7, trip 0.5 bar g")

    # ============================================================================
    hr("8. LOSS-OF-COOLING TRANSIENT (lumped estimate)")
    M_CP = V_SYS * 1e-3 * PG25["rho"] * PG25["cp"] + 30.0 * 480.0   # coolant + ~30 kg wetted metal ASSUMED
    for q in (10e3, 5e3):
        rate = q / M_CP
        print(f"Load {q/1e3:.0f} kW, pump running, facility flow lost: loop warms {rate*60:.1f} K/min "
              f"-> 32 C to 40 C in {8/rate:.0f} s, to 45 C in {13/rate:.0f} s")
    print("Pump lost at full load: cold plates see no flow; server self-protection governs (seconds).")
    print("=> hardwired 'trip IT load' output on low flow; measured values replace these at test FT-3/FT-4.")

    # ============================================================================
    hr("9. HEAT-BALANCE MEASUREMENT UNCERTAINTY AT RATING")
    u_flow = 0.008 * TCS_FLOW + 0.005 * 50.0          # ifm SM7000: +/-(0.8 % MV + 0.5 % of 50 L/min)
    u_dT = 0.10                                        # K, matched Pt100 pair after in-situ calibration
    uq = math.sqrt((u_flow / TCS_FLOW) ** 2 + (u_dT / dT_t) ** 2 + 0.01 ** 2)  # + 1 % property uncertainty
    print(f"TCS flow uncertainty +/-{u_flow:.2f} L/min ({u_flow/TCS_FLOW*100:.1f} %), dT +/-{u_dT} K on {dT_t:.1f} K ({u_dT/dT_t*100:.1f} %)")
    print(f"Combined heat-balance uncertainty ~ +/-{uq*100:.1f} % (root-sum-square)")


if __name__ == "__main__":
    main()
