#!/usr/bin/env python3
"""CDU-10 dynamic simulation (Rev B).

Transient model of both circuits driving the reference controller in
cdu_control.py.  Used to tune the control loops and to predict the results of
the thermal and fault tests in ../08-test-plan.md before hardware exists.

    python3 cdu_sim.py            # all scenarios, writes ../sim/*.svg and ../sim/results.md
    python3 cdu_sim.py S1 S6      # selected scenarios

Model summary
- Server loop (TCS): 27 well-mixed cells in loop order -- internal return,
  exchanger (10 counterflow cells with wall nodes), internal supply/filter,
  external supply hose, servers, external return hose -- with a bypass from
  the supply tee to the return tee.  Explicit upwind transport, dt = 0.05 s.
- Hydraulics are quasi-steady: pump curve against internal, bypass and
  external resistances; facility flow from available dP through the fixed
  resistance, the equal-percentage control valve and the shut-off valve.
- Film coefficients come from cdu_calc.py (Martin correlation) as functions of
  flow, derated 20 % for fouling.  Metal heat capacity is lumped with fluid.
- Actuators: valve rate limit (running time), pump drive ramp and coast-down,
  shut-off valve stroke.  Sensors: first-order lag plus noise.
- Static pressure from the expansion-tank gas law and coolant expansion.
- Not modelled: heat loss to room (conservative), cold-plate local
  temperatures, server self-protection, water hammer.
"""
import math
import os
import random
import sys

import numpy as np

import cdu_calc as cc
import cdu_control as ctl

RT, CT = cc.PG25["rho"], cc.PG25["cp"]
RW, CW = cc.WATER["rho"], cc.WATER["cp"]
LPM = 1.0 / 60000.0
G = 9.81
DT = 0.05
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sim")

# ---------------------------------------------------------------- exchanger
N_PL, N_HX = cc.HX_PLATES, 10
_p0 = cc.hx_perf(N_PL, 30.0, 24.0)
HX_A = _p0["A"]
FOUL = 0.80
_FL = np.concatenate([[0.02, 0.1, 0.3, 0.6], np.arange(1.0, 46.0, 1.0)])
_HT = np.array([cc.side(cc.PG25, f, _p0["n_tcs"])["h"] for f in _FL]) * FOUL
_HW = np.array([cc.side(cc.WATER, f, _p0["n_fws"])["h"] for f in _FL]) * FOUL
C_WALL = (1.15 + 0.096 * N_PL) * 500.0 / N_HX          # J/K per cell (316, B10T mass basis)

# ---------------------------------------------------------------- loop layout
#            name     vol L  cells metal J/K  flow   heat
SEGMENTS = [("RET_INT", 1.0, 2, 3000.0, "int", "pump"),
            ("HX",      1.6, N_HX, 0.0, "int", None),
            ("SUP_INT", 2.5, 3, 4000.0, "int", None),
            ("EXT_S",   4.0, 4, 0.0, "ext", None),
            ("IT",      8.0, 4, 3000.0, "ext", "it"),
            ("EXT_R",   4.0, 4, 0.0, "ext", None)]
V_TCS = sum(s[1] for s in SEGMENTS)

# ---------------------------------------------------------------- hydraulics
def k_of(dp_pa, lpm):
    return dp_pa / (lpm * LPM) ** 2


K_HX = k_of(_p0["tcs"]["dp"], 30.0)
K_METER = k_of(10e3, 30.0)
K_PIPE = k_of(6.4e3, 30.0)
K_BYP = k_of(70e3, 3.0)
K_BRANCH = k_of(70e3, 13.0)         # one 4U GPU server branch: 13 L/min at 70 kPa
PUMP_C = cc.PUMPS[cc.PUMP_SEL]      # published curve, see cdu_calc.py
ETA_PUMP = cc.ETA_W2W

# ---------------------------------------------------------------- tank
V_TANK, P_PRE_ABS, VTW_FILL, T_FILL, BETA = 8.0, 0.8 + 1.013, 0.79, 15.0, 4.5e-4


class Plant:
    def __init__(self, t_init=32.0, fws_in=27.0, seed=1):
        self.rng = random.Random(seed)
        vols, metal, kind, heat = [], [], [], []
        self.idx = {}
        for name, v, n, m, k, h in SEGMENTS:
            self.idx[name] = (len(vols), len(vols) + n)
            vols += [v / n] * n
            metal += [m / n] * n
            kind += [k] * n
            heat += [h] * n
        self.V = np.array(vols) * 1e-3
        self.C = RT * CT * self.V + np.array(metal)
        self.is_ext = np.array([k == "ext" for k in kind])
        self.it_cells = np.array([h == "it" for h in heat])
        self.n = len(vols)
        self.T = np.full(self.n, t_init)
        self.Tw = np.full(N_HX, t_init)
        v_fws = 1.6e-3 * _p0["n_fws"] / _p0["n_tcs"]
        self.Cc = RW * CW * v_fws / N_HX
        self.Tc = np.full(N_HX, fws_in)
        # boundary conditions (scenarios change these)
        self.load_w = 0.0
        self.fws_in = fws_in
        self.fws_dp_kpa = 50.0
        self.v201_open = True
        self.n_servers = 2
        self.pump_power = True
        self.filter_kpa = 5.0              # filter drop at 30 L/min
        self.leak_lpm = 0.0
        self.v_lost = 0.0
        self.lds301 = False
        self.t_room, self.rh_room = 24.0, 57.0
        self.valve_run_s = 90.0            # control-valve actuator running time
        # actuator states
        self.speed = 0.0                   # pump, fraction of max
        self.tcv = 0.0                     # %
        self.xv = 0.0                      # 0..1
        self.load_factor = 0.0
        self.permit_delay = 0.0
        # flows (L/min) and pressures
        self.q = self.q_ext = self.q_byp = self.q_fws = 0.0
        self.dp_pump = self.dp_eq = 0.0
        self.p_static = 1.0
        # sensors
        self.s = None

    # ------------------------------------------------------------ hydraulics
    def hydraulics(self):
        k_int = K_HX + k_of(self.filter_kpa * 1e3, 30.0) + K_METER + K_PIPE
        c = 1.0 / math.sqrt(K_BYP)
        if self.n_servers > 0:
            k_ext = K_BRANCH / self.n_servers ** 2
            c += 1.0 / math.sqrt(k_ext)
        k_eq = 1.0 / c ** 2
        k_sys = (k_int + k_eq) / (RT * G) / 3600.0 ** 2       # m per (m3/h)^2
        qh = cc.pump_flow_on_system(self.speed, k_sys, PUMP_C) if self.speed > 1e-4 else 0.0
        Q = qh / 3600.0
        self.dp_eq = k_eq * Q * Q
        self.dp_pump = RT * G * cc.pump_head(qh, self.speed, PUMP_C)
        self.q = Q / LPM
        self.q_ext = math.sqrt(self.dp_eq / k_ext) / LPM if self.n_servers > 0 else 0.0
        self.q_byp = self.q - self.q_ext
        # facility side
        cv = ctl.valve_cv(self.tcv)
        cv_xv = 30.0 * self.xv
        if not self.v201_open or cv <= 0 or cv_xv <= 0:
            self.q_fws = 0.0
        else:
            r = ctl.K_FIXED_KPA / 24.0 ** 2 + 6.89476 / (3.785 * cv) ** 2 + 6.89476 / (3.785 * cv_xv) ** 2
            self.q_fws = math.sqrt(self.fws_dp_kpa / r)

    # ------------------------------------------------------------ thermal
    def thermal(self, dt):
        T = self.T
        a, b = self.idx["HX"]
        s0, s1 = self.idx["SUP_INT"]
        e0, _ = self.idx["EXT_S"]
        _, r1 = self.idx["EXT_R"]
        r0, _ = self.idx["RET_INT"]
        F = np.where(self.is_ext, self.q_ext, self.q) * LPM          # m3/s per cell
        Tin = np.roll(T, 1)
        t_sup = T[s1 - 1]
        Tin[e0] = t_sup
        if self.q > 1e-9:
            Tin[r0] = (self.q_ext * T[r1 - 1] + self.q_byp * t_sup) / self.q
        else:
            Tin[r0] = T[r0]
        Qh = np.zeros(self.n)
        Qh[self.it_cells] = self.load_w * self.load_factor / self.it_cells.sum()
        Qh[r0 + 1] += self.dp_pump * self.q * LPM / ETA_PUMP if self.speed > 0 else 0.0
        # exchanger
        hA_h = np.interp(self.q, _FL, _HT) * HX_A / N_HX
        hA_c = np.interp(self.q_fws, _FL, _HW) * HX_A / N_HX
        Th = T[a:b]
        q_hw = hA_h * (Th - self.Tw)
        q_wc = hA_c * (self.Tw - self.Tc)
        Qh[a:b] -= q_hw
        Fc = self.q_fws * LPM
        Tc_in = np.append(self.Tc[1:], self.fws_in)                  # counterflow
        self.Tc = self.Tc + dt * (RW * CW * Fc * (Tc_in - self.Tc) + q_wc) / self.Cc
        self.Tw = self.Tw + dt * (q_hw - q_wc) / C_WALL
        self.T = T + dt * (RT * CT * F * (Tin - T) + Qh) / self.C

    # ------------------------------------------------------------ static pressure
    def static_pressure(self):
        tmean = float(np.dot(self.T, self.V) / self.V.sum())
        vtw = VTW_FILL + V_TCS * BETA * (tmean - T_FILL) - self.v_lost
        if vtw > 0:
            self.p_static = P_PRE_ABS * V_TANK / (V_TANK - vtw) - 1.013
        else:   # tank empty: pressure collapses quickly
            self.p_static = max(P_PRE_ABS + vtw * 2.0, 0.1) - 1.013

    # ------------------------------------------------------------ sensors
    def sensors(self, dt):
        s0, s1 = self.idx["SUP_INT"]
        r0, _ = self.idx["RET_INT"]
        _, r1 = self.idx["EXT_R"]
        t_ret_mix = ((self.q_ext * self.T[r1 - 1] + self.q_byp * self.T[s1 - 1]) / self.q
                     if self.q > 1e-6 else self.T[r0])
        fws_dp = self.fws_dp_kpa if (self.v201_open and self.xv > 0) else 0.0
        true = dict(
            TT101=self.T[s1 - 1], TT102=t_ret_mix, TT201=self.fws_in, TT202=self.Tc[0],
            FT101=self.q, FT201=self.q_fws,
            PT101=self.p_static, PT102=self.p_static + self.dp_pump / 1e5,
            PT103=self.p_static + self.dp_eq / 1e5,
            PT201=3.0 + fws_dp / 200.0, PT202=3.0 - fws_dp / 200.0,
            PDT101=k_of(self.filter_kpa * 1e3, 30.0) * (self.q * LPM) ** 2 / 1e3,
        )
        tau = dict(TT101=6.0, TT102=6.0, TT201=6.0, TT202=6.0, FT101=1.0, FT201=1.0,
                   PT101=0.3, PT102=0.3, PT103=0.3, PT201=0.3, PT202=0.3, PDT101=0.5)
        noise = dict(TT101=0.015, TT102=0.015, TT201=0.015, TT202=0.015, FT101=0.1, FT201=0.1,
                     PT101=0.002, PT102=0.002, PT103=0.002, PT201=0.002, PT202=0.002, PDT101=0.1)
        if self.s is None:
            self.s = dict(true)
        for k, v in true.items():
            self.s[k] += dt / tau[k] * (v - self.s[k])
        meas = {k: v + self.rng.gauss(0.0, noise[k]) for k, v in self.s.items()}
        meas.update(T_ROOM=self.t_room, RH_ROOM=self.rh_room, LDS301=self.lds301,
                    LDS302=False, TCV_POS=self.tcv)
        return meas

    # ------------------------------------------------------------ actuators
    def actuators(self, out, dt):
        rate = 100.0 / self.valve_run_s
        self.tcv += clamp_step(out["valve"] - self.tcv, rate * dt)
        if out["xv_open"]:
            self.xv = min(1.0, self.xv + dt / 75.0)        # motor open 75 s
        else:
            self.xv = max(0.0, self.xv - dt / 20.0)        # spring close 20 s
        if out["pump_run"] and self.pump_power:
            self.speed += clamp_step(out["speed"] / 100.0 - self.speed, dt / 3.0)
        else:
            self.speed -= dt * self.speed / 1.0            # coast-down
        # servers shed load ~1 s after permit opens; resume when re-permitted
        if out["permit"]:
            self.permit_delay = 0.0
            self.load_factor = min(1.0, self.load_factor + dt / 30.0)
        else:
            self.permit_delay += dt
            if self.permit_delay > 1.0:
                self.load_factor -= dt * self.load_factor / 1.5

    def step(self, dt):
        self.hydraulics()
        self.thermal(dt)
        self.v_lost += self.leak_lpm * dt / 60.0
        self.static_pressure()


def clamp_step(d, lim):
    return max(-lim, min(lim, d))


def rh_for_dew(t_room, dew):
    b, c = 17.62, 243.12
    return 100.0 * math.exp(b * dew / (c + dew) - b * t_room / (c + t_room))


# ==================================================================== runner
def run(scn, ctrl_kw=None, plant_kw=None, seed=1):
    plant = Plant(t_init=scn.get("t_init", 32.0), fws_in=scn.get("fws_in", 27.0), seed=seed)
    for k, v in (plant_kw or {}).items():
        setattr(plant, k, v)
    for k, v in scn.get("plant", {}).items():
        setattr(plant, k, v)
    ctrl = ctl.Controller(**dict(scn.get("ctrl", {}), **(ctrl_kw or {})))
    pre = scn.get("pre", 900.0)
    t = -pre
    events = sorted(scn.get("events", []), key=lambda e: e[0])
    ei = 0
    rec = {k: [] for k in ("t", "TT101", "TT102", "T_IT", "TT201", "TT202", "valve", "tcv", "speed",
                           "q", "q_ext", "q_fws", "load", "p_static", "p_disch", "dp_eq", "sp")}
    events_log = []
    out = None
    meas = plant.sensors(DT)
    step = 0
    while t < scn["dur"] - 1e-9:
        while ei < len(events) and events[ei][0] <= t + 1e-9:
            events[ei][1](plant, ctrl)
            ei += 1
        if step % 2 == 0:
            meas["START"] = True
            meas["RESET"] = False
            prev = (set(ctrl.alarms), set(ctrl.trips), ctrl.permit)
            out = ctrl.step(meas, 2 * DT)
            if t >= 0:
                for a in out["alarms"] - prev[0]:
                    events_log.append((t, "alarm", a))
                for a in out["trips"] - prev[1]:
                    events_log.append((t, "trip", a))
                if prev[2] and not out["permit"]:
                    events_log.append((t, "permit", "opened"))
        plant.actuators(out, DT)
        plant.step(DT)
        meas = plant.sensors(DT)
        step += 1
        t += DT
        if step % 20 == 0 and t >= -60.0:
            _, i1 = plant.idx["IT"]
            for k, v in (("t", t), ("TT101", meas["TT101"]), ("TT102", meas["TT102"]),
                         ("T_IT", plant.T[i1 - 1]), ("TT201", meas["TT201"]), ("TT202", meas["TT202"]),
                         ("valve", out["valve"]), ("tcv", plant.tcv), ("speed", plant.speed * 100),
                         ("q", plant.q), ("q_ext", plant.q_ext), ("q_fws", plant.q_fws),
                         ("load", plant.load_w * plant.load_factor / 1e3), ("p_static", plant.p_static),
                         ("p_disch", plant.p_static + plant.dp_pump / 1e5), ("dp_eq", plant.dp_eq / 1e3),
                         ("sp", out["sp_eff"])):
                rec[k].append(v)
    return {k: np.array(v) for k, v in rec.items()}, events_log, plant, ctrl


def ev(t, **kw):
    """Event setting plant attributes at time t."""
    def f(plant, ctrl):
        for k, v in kw.items():
            if k.startswith("ctrl_"):
                ctrl.p[k[5:]] = v
            else:
                setattr(plant, k, v)
    return (t, f)


# ==================================================================== scenarios
SCENARIOS = {
    "S1": dict(title="Load step 2 to 10 to 2 kW, facility water 27 C (test TT-5)", dur=1500,
               plant=dict(load_w=2e3), events=[ev(60, load_w=10e3), ev(780, load_w=2e3)]),
    "S2": dict(title="Light load on cold facility water: 2 kW, 18 C, 30 min (tests TT-2, TT-4)", dur=1800,
               fws_in=18.0, plant=dict(load_w=2e3, fws_in=18.0)),
    "S3": dict(title="Rating point: 10 kW, facility water 27 C (test TT-1)", dur=900,
               plant=dict(load_w=10e3)),
    "S4": dict(title="Facility water temperature step 22 to 27 C at 8 kW", dur=900, fws_in=22.0,
               plant=dict(load_w=8e3, fws_in=22.0), events=[ev(60, fws_in=27.0)]),
    "S5": dict(title="Facility pressure step 50 to 90 kPa at 10 kW", dur=600,
               plant=dict(load_w=10e3), events=[ev(60, fws_dp_kpa=90.0), ev(330, fws_dp_kpa=50.0)]),
    "S6": dict(title="Facility water lost at 10 kW (test FT-3)", dur=400,
               plant=dict(load_w=10e3), events=[ev(60, v201_open=False)]),
    "S7": dict(title="Pump power lost at 10 kW (test FT-4)", dur=90,
               plant=dict(load_w=10e3), events=[ev(30, pump_power=False)]),
    "S8": dict(title="One of two servers unplugged at 10 kW", dur=600,
               plant=dict(load_w=10e3),
               events=[ev(60, ctrl_F_EXP=16.0, ctrl_F_MIN=15.0), ev(90, n_servers=1, load_w=5e3)]),
    "S9": dict(title="Room dew point rises 15 to 30 C at 5 kW (test TT-8)", dur=900,
               plant=dict(load_w=5e3, rh_room=rh_for_dew(24.0, 15.0)),
               events=[ev(60, t_room=34.0, rh_room=rh_for_dew(34.0, 30.0))]),
    "S10": dict(title="Slow coolant leak 0.1 L/min at 5 kW (test FT-6)", dur=600,
                plant=dict(load_w=5e3), events=[ev(60, leak_lpm=0.1)]),
    "S11": dict(title="Filter loading 5 to 30 kPa over 10 min at 10 kW (test TT-7)", dur=900,
                plant=dict(load_w=10e3), events=[ev(60 + 60 * i, filter_kpa=5.0 + 2.5 * (i + 1)) for i in range(10)]),
    "S13": dict(title="Facility water interrupted for 15 s at 10 kW (ride-through)", dur=400,
                plant=dict(load_w=10e3), events=[ev(60, v201_open=False), ev(75, v201_open=True)]),
    "S12": dict(title="Cold start: loop at 15 C, servers start when permitted", dur=600, pre=0.0,
                t_init=15.0, plant=dict(load_w=10e3)),
}


# ==================================================================== metrics
def settle_time(t, y, sp, t0, band=0.5):
    mask = t >= t0
    tt, yy = t[mask], y[mask]
    out = np.abs(yy - sp) > band
    if not out.any():
        return 0.0
    last = np.where(out)[0][-1]
    return tt[last] - t0 if last < len(tt) - 1 else math.inf


def metrics(name, r, log, plant, ctrl):
    t = r["t"]
    m = {}
    after = t >= 0
    sp = ctrl.sp_eff
    if name == "S1":
        up = (t >= 60) & (t < 780)
        dn = t >= 780
        m["overshoot_up_K"] = float(r["TT101"][up].max() - 32.0)
        m["settle_up_s"] = settle_time(t[t < 780], r["TT101"][t < 780], 32.0, 60.0)
        m["undershoot_down_K"] = float(32.0 - r["TT101"][dn].min())
        m["settle_down_s"] = settle_time(t, r["TT101"], 32.0, 780.0)
    if name in ("S2", "S3"):
        w = t >= 300
        m["supply_mean_C"] = float(r["TT101"][w].mean())
        m["supply_pk_pk_K"] = float(np.ptp(r["TT101"][w]))
        v = r["tcv"][w]
        m["valve_pk_pk_pct"] = float(np.ptp(v))
        m["valve_travel_pct_per_h"] = float(np.abs(np.diff(v)).sum() / ((t[w][-1] - t[w][0]) / 3600))
        m["valve_mean_pct"] = float(v.mean())
        m["fws_flow_mean_lpm"] = float(r["q_fws"][w].mean())
        if name == "S3":
            q_tcs = RT * CT * r["q"][w] * LPM * (r["TT102"][w] - r["TT101"][w])
            q_fws = RW * CW * r["q_fws"][w] * LPM * (r["TT202"][w] - r["TT201"][w])
            pump_heat = plant.dp_pump * plant.q * LPM / ETA_PUMP
            m["heat_tcs_kW"] = float(q_tcs.mean() / 1e3)
            m["heat_fws_kW"] = float(q_fws.mean() / 1e3)
            m["pump_heat_W"] = float(pump_heat)
            m["flow_lpm"] = float(r["q"][w].mean())
            m["pump_speed_pct"] = float(r["speed"][w].mean())
            m["discharge_bar_g"] = float(r["p_disch"][w].mean())
            m["static_bar_g"] = float(r["p_static"][w].mean())
    if name in ("S4", "S5"):
        m["max_dev_K"] = float(np.abs(r["TT101"][after] - 32.0).max())
        m["settle_s"] = settle_time(t, r["TT101"], 32.0, 60.0)
    if name == "S13":
        m["peak_supply_C"] = float(r["TT101"].max())
        m["max_dev_K"] = float(np.abs(r["TT101"][after] - 32.0).max())
    if name == "S6":
        trip = [e for e in log if e[2] in ("HIGH_TEMP", "FWS_LOST")]
        warn = [e for e in log if e[2] == "FWS_LOST_W"]
        m["fws_lost_alarm_after_s"] = warn[0][0] - 60 if warn else None
        m["first_trip"] = trip[0][2] if trip else None
        m["first_trip_after_s"] = trip[0][0] - 60 if trip else None
        m["supply_at_trip_C"] = float(np.interp(trip[0][0], t, r["TT101"])) if trip else None
        m["peak_supply_C"] = float(r["TT101"].max())
        m["peak_server_outlet_C"] = float(r["T_IT"].max())
    if name == "S7":
        trip = [e for e in log if e[2] == "LOW_FLOW"]
        m["low_flow_trip_after_s"] = trip[0][0] - 30 if trip else None
        half = t[(t > 30) & (r["q"] < 0.5 * 29.0)]
        m["flow_below_50pct_after_s"] = float(half[0] - 30) if len(half) else None
        m["server_outlet_rise_K"] = float(r["T_IT"][t > 30].max() - r["T_IT"][t <= 30][-1])
    if name == "S8":
        w = t >= 300
        m["remaining_server_flow_before"] = float(r["q_ext"][(t > 0) & (t < 90)].mean() / 2)
        m["remaining_server_flow_after"] = float(r["q_ext"][w].mean())
        m["pump_speed_after_pct"] = float(r["speed"][w].mean())
        m["max_discharge_bar_g"] = float(r["p_disch"].max())
        m["max_dev_K"] = float(np.abs(r["TT101"][after] - 32.0).max())
    if name == "S9":
        m["setpoint_after_C"] = float(r["sp"][-1])
        m["supply_end_C"] = float(r["TT101"][-30:].mean())
        dw = [e for e in log if e[2] == "DEW_W"]
        m["dew_warning"] = bool(dw)
    if name == "S10":
        w = [e for e in log if e[2] == "INVENTORY_W"]
        tr = [e for e in log if e[2] == "INVENTORY"]
        m["warning_after_s"] = w[0][0] - 60 if w else None
        m["volume_at_warning_L"] = (w[0][0] - 60) * 0.1 / 60 if w else None
        m["trip_after_s"] = tr[0][0] - 60 if tr else None
        m["volume_at_trip_L"] = (tr[0][0] - 60) * 0.1 / 60 if tr else None
    if name == "S11":
        m["server_flow_start"] = float(r["q_ext"][(t > 0) & (t < 60)].mean())
        m["server_flow_end"] = float(r["q_ext"][-30:].mean())
        m["pump_speed_end_pct"] = float(r["speed"][-30:].mean())
        m["max_dev_K"] = float(np.abs(r["TT101"][after] - 32.0).max())
        fw = [e for e in log if e[2] == "FILTER_W"]
        m["filter_alarm_at_s"] = fw[0][0] if fw else None
    if name == "S12":
        p = [e for e in log if e[2] == "permit"]
        run_t = t[(r["load"] > 0.01)]
        m["permit_closed_at_s"] = float(run_t[0]) if len(run_t) else None
        m["peak_supply_C"] = float(r["TT101"][t > 60].max())
        m["supply_end_C"] = float(r["TT101"][-30:].mean())
    m["trips"] = sorted({e[2] for e in log if e[1] == "trip"})
    return m


# ==================================================================== SVG charts
PAL = dict(s1="#2a78d6", s2="#eb6834", s3="#1baf7a", s1d="#3987e5", s2d="#d95926", s3d="#199e70")


def nice_ticks(lo, hi, n=4):
    span = hi - lo
    if span <= 0:
        return [lo]
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), default=10 * mag)
    start = math.ceil(lo / step) * step
    ticks, v = [], start
    while v <= hi + 1e-9:
        ticks.append(round(v, 10))
        v += step
    return ticks


def svg_chart(path, title, t, panels, events=()):
    W, LM, RM, TM, PH, GAP = 920, 64, 150, 56, 150, 34
    H = TM + len(panels) * (PH + GAP) + 30
    x0, x1 = LM, W - RM
    tmin, tmax = float(t[0]), float(t[-1])
    X = lambda v: x0 + (v - tmin) / (tmax - tmin) * (x1 - x0)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="Helvetica,Arial,sans-serif" font-size="12">',
         '<style>svg{--bg:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e4e3df;--s1:%s;--s2:%s;--s3:%s}'
         '@media (prefers-color-scheme: dark){svg{--bg:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#3a3936;--s1:%s;--s2:%s;--s3:%s}}'
         '.ink{fill:var(--ink)}.ink2{fill:var(--ink2)}.g{stroke:var(--grid)}'
         '.l1{stroke:var(--s1)}.l2{stroke:var(--s2)}.l3{stroke:var(--s3)}.f1{fill:var(--s1)}.f2{fill:var(--s2)}.f3{fill:var(--s3)}'
         '.th{stroke:var(--ink2)}</style>' % (PAL["s1"], PAL["s2"], PAL["s3"], PAL["s1d"], PAL["s2d"], PAL["s3d"]),
         f'<rect width="{W}" height="{H}" style="fill:var(--bg)"/>',
         f'<text x="{LM}" y="26" font-size="15" font-weight="bold" class="ink">{title}</text>']
    seen = {}
    for ev_t, label in events:
        key = round(ev_t)
        if key in seen:
            seen[key] += ", " + label
        else:
            seen[key] = label
    for i, (ev_t, label) in enumerate(sorted(seen.items())):
        o.append(f'<line x1="{X(ev_t):.1f}" y1="{TM - 8}" x2="{X(ev_t):.1f}" y2="{H - 30}" class="th" stroke-width="1" stroke-dasharray="2 4"/>')
        o.append(f'<text x="{X(ev_t) + 4:.1f}" y="{TM - 10 + 11 * (i % 2)}" font-size="10" class="ink2">{label}</text>')
    for pi, pan in enumerate(panels):
        y0 = TM + pi * (PH + GAP)
        vals = np.concatenate([np.asarray(s[1]) for s in pan["series"]] + [np.array([h[0] for h in pan.get("hlines", [])])])
        lo, hi = pan.get("ylim", (float(vals.min()), float(vals.max())))
        if hi - lo < 1e-6:
            lo, hi = lo - 1, hi + 1
        pad = 0.06 * (hi - lo)
        lo, hi = (lo - pad, hi + pad) if "ylim" not in pan else (lo, hi)
        Y = lambda v: y0 + PH - (v - lo) / (hi - lo) * PH
        o.append(f'<text x="{LM}" y="{y0 - 8}" font-size="12" font-weight="bold" class="ink">{pan["label"]}</text>')
        for tk in nice_ticks(lo, hi):
            o.append(f'<line x1="{x0}" y1="{Y(tk):.1f}" x2="{x1}" y2="{Y(tk):.1f}" class="g" stroke-width="1"/>')
            o.append(f'<text x="{x0 - 6}" y="{Y(tk) + 4:.1f}" text-anchor="end" font-size="10" class="ink2">{tk:g}</text>')
        for hv, hl in pan.get("hlines", []):
            o.append(f'<line x1="{x0}" y1="{Y(hv):.1f}" x2="{x1}" y2="{Y(hv):.1f}" class="th" stroke-width="1" stroke-dasharray="6 4"/>')
            o.append(f'<text x="{x1 - 4}" y="{Y(hv) - 4:.1f}" text-anchor="end" font-size="10" class="ink2">{hl}</text>')
        stride = max(1, len(t) // 700)
        for si, (name, ys) in enumerate(pan["series"]):
            ys = np.asarray(ys)
            pts = " ".join(f"{X(tt):.1f},{Y(min(max(v, lo), hi)):.1f}" for tt, v in zip(t[::stride], ys[::stride]))
            o.append(f'<polyline points="{pts}" fill="none" class="l{si + 1}" stroke-width="2" stroke-linejoin="round"/>')
            # direct label at the right end + legend swatch
            yl = Y(min(max(float(ys[-1]), lo), hi))
            ly = y0 + 14 + si * 32
            o.append(f'<rect x="{x1 + 12}" y="{ly - 8}" width="14" height="3" class="f{si + 1}"/>')
            o.append(f'<text x="{x1 + 32}" y="{ly - 3}" font-size="11" class="ink">{name}</text>')
            o.append(f'<text x="{x1 + 32}" y="{ly + 9}" font-size="10" class="ink2">end {ys[-1]:.1f}</text>')
        o.append(f'<line x1="{x0}" y1="{y0 + PH}" x2="{x1}" y2="{y0 + PH}" class="th" stroke-width="1"/>')
    ybase = TM + len(panels) * (PH + GAP) - GAP + 4
    for tk in nice_ticks(tmin, tmax, 8):
        o.append(f'<text x="{X(tk):.1f}" y="{ybase + 12}" text-anchor="middle" font-size="10" class="ink2">{tk:g}</text>')
    o.append(f'<text x="{(x0 + x1) / 2}" y="{ybase + 28}" text-anchor="middle" font-size="11" class="ink2">time, s</text>')
    o.append("</svg>")
    with open(path, "w") as fh:
        fh.write("\n".join(o))


def chart(name, scn, r, log, ctrl):
    t = r["t"]
    trip_level = ctrl.p["T_SERVER_MAX"] - 2.0
    marks = [(e[0], e[2].replace("_", " ").lower()) for e in log if e[1] == "trip"][:3]
    panels = [
        dict(label="Temperatures, C", series=[("supply TT-101", r["TT101"]), ("return TT-102", r["TT102"]),
                                              ("facility out TT-202", r["TT202"])],
             hlines=[(trip_level, f"trip {trip_level:g} C")] if r["TT101"].max() > trip_level - 3 else []),
        dict(label="Heat load, kW", series=[("server load", r["load"])]),
        dict(label="Valve position and pump speed, %", series=[("valve TCV-201", r["tcv"]), ("pump speed", r["speed"])],
             ylim=(0, 100)),
        dict(label="Flows, L/min", series=[("server loop FT-101", r["q"]), ("servers only", r["q_ext"]),
                                          ("facility FT-201", r["q_fws"])]),
    ]
    svg_chart(os.path.join(OUT, f"{name}.svg"), f"{name}: {scn['title']}", t, panels, marks)


# ==================================================================== main
def fmt(v):
    if isinstance(v, float):
        return "inf" if math.isinf(v) else f"{v:.2f}"
    return str(v)


def main(names):
    os.makedirs(OUT, exist_ok=True)
    lines = ["# Simulation results (generated by calc/cdu_sim.py)", "",
             "Model and assumptions are described at the top of `calc/cdu_sim.py`. "
             "These are predictions, not measurements.", ""]
    allm = {}
    for name in names:
        scn = SCENARIOS[name]
        r, log, plant, ctrl = run(scn)
        m = metrics(name, r, log, plant, ctrl)
        allm[name] = m
        chart(name, scn, r, log, ctrl)
        lines.append(f"## {name}: {scn['title']}")
        lines.append("")
        lines.append(f"![{name}]({name}.svg)")
        lines.append("")
        lines.append("| Result | Value |")
        lines.append("|---|---|")
        for k, v in m.items():
            lines.append(f"| {k} | {fmt(v)} |")
        ev_lines = [f"{e[0]:.1f} s {e[1]} {e[2]}" for e in log][:12]
        if ev_lines:
            lines.append("")
            lines.append("Events: " + "; ".join(ev_lines))
        lines.append("")
        print(name, {k: fmt(v) for k, v in m.items()})
    if len(names) == len(SCENARIOS):
        with open(os.path.join(OUT, "results.md"), "w") as fh:
            fh.write("\n".join(lines) + "\n")
    return allm


if __name__ == "__main__":
    main(sys.argv[1:] or list(SCENARIOS))
