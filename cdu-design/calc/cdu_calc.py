#!/usr/bin/env python3
"""CDU-10 preliminary sizing calculations (Rev A).

Pure-Python, no dependencies.  Run:  python3 cdu_calc.py > results.txt

Every number marked ASSUMED is an engineering assumption that must be
replaced with vendor/site data at the hold points listed in
../07-hold-points.md.  Nothing here is a validated rating.
"""
import math

# ----------------------------------------------------------------------------
# Fluids (near 30-35 C)
# ----------------------------------------------------------------------------
# PG25: rho, cp from Dow DOWFROST LC25 typical properties (as cited in the
# feasibility report).  mu, k are ASSUMED typical values for 25 vol% inhibited PG.
PG25 = dict(name="PG25", rho=1027.8, cp=3890.0, mu=1.7e-3, k=0.47)
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
# as are effective width, pressing depth, enlargement factor, chevron angle
# and channel volume.  Vendor rating run replaces all of this (HP-03).
# ----------------------------------------------------------------------------
HX = dict(L=0.479, w=0.107, b=2.0e-3, phi_enl=1.17, chev_deg=60.0,
          t_wall=0.3e-3, k_wall=15.0, d_port=0.024, ch_vol=0.115e-3)
HX["Dh"] = 2 * HX["b"] / HX["phi_enl"]
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


def side(fluid, flow_lpm, n_ch):
    """Per-side film coefficient and pressure drop."""
    V = flow_lpm * LPM
    u = V / n_ch / (HX["w"] * HX["b"])
    Re = fluid["rho"] * u * HX["Dh"] / fluid["mu"]
    f, Nu = martin(Re, fluid["Pr"], HX["chev_deg"])
    h = Nu * fluid["k"] / HX["Dh"]
    dp_ch = f * HX["L"] / HX["Dh"] * fluid["rho"] * u ** 2 / 2
    u_port = V / (math.pi / 4 * HX["d_port"] ** 2)
    dp_port = 1.4 * fluid["rho"] * u_port ** 2 / 2
    return dict(u=u, Re=Re, h=h, dp=dp_ch + dp_port)


def hx_perf(n_plates, tcs_lpm, fws_lpm):
    """Clean UA and pressure drops for an n-plate single-pass counterflow unit."""
    n_ch_tot = n_plates - 1
    n_tcs = n_ch_tot // 2
    n_fws = n_ch_tot - n_tcs
    s1 = side(PG25, tcs_lpm, n_tcs)
    s2 = side(WATER, fws_lpm, n_fws)
    U = 1.0 / (1 / s1["h"] + 1 / s2["h"] + HX["t_wall"] / HX["k_wall"])
    A = (n_plates - 2) * HX["A_plate"]
    return dict(U=U, A=A, UA=U * A, tcs=s1, fws=s2, n_tcs=n_tcs, n_fws=n_fws)


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


def hr(t):
    print("\n" + "=" * 78 + "\n" + t + "\n" + "=" * 78)


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
hr("2. PLATE-COUNT SCAN (SWEP B25T-class geometry, Martin correlation)")
print(f"Dh = {HX['Dh']*1e3:.2f} mm   area/plate = {HX['A_plate']*1e4:.0f} cm2   chevron = {HX['chev_deg']:.0f} deg")
print(" N   A[m2]  Re_tcs Re_fws  U[W/m2K]  UA[W/K]  UA/UAreq  dP_tcs[kPa] dP_fws[kPa]")
for n in (14, 20, 24, 30, 40):
    p = hx_perf(n, TCS_FLOW, FWS_FLOW)
    print(f"{n:3d}  {p['A']:.3f}  {p['tcs']['Re']:5.0f}  {p['fws']['Re']:5.0f}   {p['U']:6.0f}   {p['UA']:6.0f}    {p['UA']/UA_req:4.2f}"
          f"      {p['tcs']['dp']/1e3:5.1f}       {p['fws']['dp']/1e3:5.1f}")
print("Sensitivity of the chosen size to the ASSUMED chevron angle:")
N_SEL = 30
for ang in (45.0, 55.0, 60.0, 65.0):
    HX["chev_deg"] = ang
    p = hx_perf(N_SEL, TCS_FLOW, FWS_FLOW)
    print(f"  chevron {ang:.0f} deg: UA/UAreq = {p['UA']/UA_req:4.2f}   dP_tcs = {p['tcs']['dp']/1e3:4.1f} kPa   dP_fws = {p['fws']['dp']/1e3:4.1f} kPa")
HX["chev_deg"] = 60.0
sel = hx_perf(N_SEL, TCS_FLOW, FWS_FLOW)
print(f"SELECTED: {N_SEL} plates.  Clean UA margin = {(sel['UA']/UA_req-1)*100:.0f} %")
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
hr("5. PUMP: Grundfos CME 1-3 class, variable speed")
# Published rated point: 2.0 m3/h at 26.2 m (100 % speed).
# ASSUMED shut-off head 31 m -> parabolic curve H = n^2*H0 - k*Q^2.
H0, Q_R, H_R = 31.0, 2.0, 26.2
k = (H0 - H_R) / Q_R ** 2
Qh = V * 3600
n_req = math.sqrt((H_req + k * Qh ** 2) / H0)
print(f"Curve model: H = n^2*{H0:.0f} - {k:.2f}*Q^2  (Q in m3/h; shut-off head ASSUMED)")
print(f"Speed for duty point: {n_req*100:.0f} %")
N_CAP = 0.85
for n in (n_req, N_CAP, 1.0):
    hs = n ** 2 * H0
    print(f"  speed {n*100:3.0f} %: shut-off head {hs:4.1f} m = {hs*PG25['rho']*G/1e5:.2f} bar")
P_FILL = 1.0  # bar g cold fill at pump suction
P_WARM = 1.15  # bar g static when warm (section 7 predicts ~1.12)
p_max = P_WARM + N_CAP ** 2 * H0 * PG25["rho"] * G / 1e5
print(f"Max discharge pressure at {N_CAP*100:.0f} % speed cap, dead-headed, warm: {p_max:.2f} bar g  (relief set 4.0 bar g, margin {(4.0-p_max)/4.0*100:.0f} %)")
print(f"Flow available at speed cap against the full dirty-filter system curve: {math.sqrt(N_CAP**2*H0/(k + H_req/Qh**2))/0.06:.1f} L/min")
ETA = 0.35  # ASSUMED wire-to-water at this small duty
print(f"Electrical input at duty (ASSUMED {ETA*100:.0f} % wire-to-water): {P_hyd/ETA:.0f} W -> heat added to coolant <= that")
print("Clean-filter, low-resistance IT loop (40 kPa external): speed "
      f"{math.sqrt(((dp_int-25e3+40e3)/(PG25['rho']*G) + k*Qh**2)/H0)*100:.0f} %")

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
