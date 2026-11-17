#!/usr/bin/env python3
"""CDU-10 control logic, reference implementation (Rev B).

This module is the executable specification of the controller.  The PLC
program in ../plc/CDU10_Main.st implements the same logic block for block;
the simulation in cdu_sim.py drives this module to tune and verify it.

Units: temperature C, pressure bar g (PT) or kPa (dP), flow L/min,
outputs in percent.  Scan time 0.1 s.
"""
import math

DEFAULTS = dict(
    # setpoints
    SP_T=32.0,            # supply temperature setpoint, C
    DEW_MARGIN=3.0,       # supply kept >= room dew point + this, K
    SP_T_MIN=25.0, SP_T_MAX=40.0,
    DP_SP=70.0,           # supply-return differential pressure setpoint, kPa
    # limits
    SPEED_MIN=30.0, SPEED_MAX=95.0,   # pump drive, % (CME 1-2: 95 % cap keeps dead-head <= 3.5 bar g, D-11)
    VALVE_MIN_RUN=5.0,                # control valve minimum while running, %
    VALVE_START=30.0,                 # preposition at start, %
    # configuration set by the operator for the connected servers
    F_EXP=29.0,           # expected TCS flow (servers + bypass), L/min
    F_MIN=27.0,           # minimum TCS flow (sum of server minimums + bypass), L/min
    T_SERVER_MAX=40.0,    # server maximum inlet temperature, C
    FWS_TRIP_S=20.0,      # facility-water loss confirmed for this long -> shed load, s
    LOW_FLOW_TRIP_S=3.0,  # s
    # coolant inventory (zeroed at each fill: decision D-24)
    V_SYS=21.0,           # loop volume, L
    V_TANK=8.0, P_PRE=0.8, BETA=4.5e-4,
    VTW_REF=0.79, T_REF=15.0,          # tank water volume and loop temperature at the fill
    INV_WARN_L=0.25, INV_TRIP_L=0.60,
    # tuning (from cdu_sim.py)
    T_KP=8.0, T_TI=60.0,         # %/K, s   -- valve loop
    T_TD=0.0, T_TF=8.0,          # s, s  -- derivative on measurement (off: sim showed no benefit)
    T_IBAND=2.0,                 # K, integrate only within this band of setpoint
    T_EDB=0.05,                  # K, error deadband (sensor noise)
    T_FF=True,                   # load feed-forward on the valve loop
    FF_TF=10.0,                  # s, filter on the feed-forward output
    VALVE_DEADBAND=0.3,          # %, command only changes by more than this (actuator wear)
    DP_KP=0.4, DP_TI=4.0,        # %/kPa, s -- pump loop
    FL_KP=2.0, FL_TI=4.0,        # %/(L/min), s -- minimum-flow override
)


def dew_point(t_c, rh_pct):
    """Magnus formula, valid 0-60 C."""
    b, c = 17.62, 243.12
    g = math.log(max(rh_pct, 1.0) / 100.0) + b * t_c / (c + t_c)
    return c * g / (b - g)


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


class PI:
    """Positional PI with back-calculation anti-windup.

    `track` is the output actually applied (after limits or selector);
    the integrator is pulled toward it so the loop takes over bumplessly.
    """

    def __init__(self, kp, ti, lo, hi):
        self.kp, self.ti, self.lo, self.hi = kp, ti, lo, hi
        self.iband = math.inf
        self.i = 0.0
        self.u = lo

    def step(self, error, dt, bias=0.0):
        self.u_raw = self.kp * error + self.i + bias
        self.u = clamp(self.u_raw, self.lo, self.hi)
        self._e, self._bias = error, bias
        return self.u

    def update(self, dt, applied):
        """Call once per scan after the applied output is known."""
        self.i += dt * (self.kp * self._e / self.ti + (applied - self.u_raw) / self.ti)

    def update_conditional(self, dt, feedback=None, lag_band=5.0):
        """Conditional integration (clamping) anti-windup.

        The integrator is frozen while the output is saturated in the direction
        the error is pushing, or while a slow actuator is still travelling
        toward the command.  Unlike back-calculation, this leaves the
        feed-forward bias intact during saturation, so the loop recovers as
        soon as the error starts to shrink.
        """
        e = self._e
        sat = (self.u_raw >= self.hi and e > 0) or (self.u_raw <= self.lo and e < 0)
        sat = sat or abs(e) > self.iband
        lag = feedback is not None and abs(self.u - feedback) > lag_band and (self.u - feedback) * e > 0
        if not (sat or lag):
            self.i = clamp(self.i + dt * self.kp * e / self.ti, -100.0, 100.0)

    def preset(self, value, bias=0.0):
        self.i = value - bias
        self.u = value


class OnDelay:
    def __init__(self, delay):
        self.delay, self.t = delay, 0.0

    def __call__(self, cond, dt):
        self.t = self.t + dt if cond else 0.0
        return self.t >= self.delay


TRIP_ACTIONS = {
    # trip: (pump stops after s, close facility shut-off, hold valve)
    "LOW_FLOW":    (30.0, False, False),
    "HIGH_TEMP":   (math.inf, False, False),
    "LOW_STATIC":  (0.0, False, False),
    "HIGH_DISCH":  (0.0, False, False),
    "LEAK_TRAY":   (60.0, True, True),
    "INVENTORY":   (60.0, False, False),
    "FWS_LOST":    (math.inf, False, False),
    "SENSOR":      (math.inf, False, True),
    "START_FAIL":  (0.0, False, False),
    "REMOTE_STOP": (0.0, False, False),
}


class Controller:
    OFF, STARTING, RUNNING, TRIPPED = "OFF", "STARTING", "RUNNING", "TRIPPED"

    def __init__(self, **kw):
        self.p = dict(DEFAULTS, **kw)
        p = self.p
        self.state = self.OFF
        self.t_valve = PI(p["T_KP"], p["T_TI"], p["VALVE_MIN_RUN"], 100.0)
        self.t_valve.iband = p["T_IBAND"]
        self.dp_pi = PI(p["DP_KP"], p["DP_TI"], p["SPEED_MIN"], p["SPEED_MAX"])
        self.fl_pi = PI(p["FL_KP"], p["FL_TI"], p["SPEED_MIN"], p["SPEED_MAX"])
        self.tm = dict(
            lf_warn=OnDelay(10.0), lf_trip=OnDelay(p["LOW_FLOW_TRIP_S"]), ht_warn=OnDelay(60.0),
            ht_trip=OnDelay(5.0), run_ok=OnDelay(10.0), fws_lost=OnDelay(10.0),
            fws_trip=OnDelay(p["FWS_TRIP_S"]), inv_warn=OnDelay(30.0), inv_trip=OnDelay(10.0),
        )
        self.alarms, self.trips = set(), set()
        self.t_state = 0.0
        self.t_trip = 0.0
        self.speed, self.valve = 0.0, 0.0
        self.pump_run, self.xv_open, self.permit = False, False, False
        self.sp_eff = p["SP_T"]
        self.pv_prev, self.dpv = None, 0.0
        self.inventory_deficit = 0.0
        self.ff_f = 0.0

    # ------------------------------------------------------------------
    def _enter(self, state):
        self.state, self.t_state = state, 0.0

    def _trip(self, name):
        if name not in self.trips:
            self.trips.add(name)
            if self.state != self.TRIPPED:
                self.t_trip = 0.0
            self._enter(self.TRIPPED)

    def valve_feedforward(self, x):
        """Valve position needed at setpoint for the measured heat duty.

        Estimates the facility flow from a heat balance (facility outlet taken
        1.5 K below the steady-state return), then inverts the installed
        equal-percentage valve using the measured facility pressure difference.
        """
        # Heat delivered by the servers.  FT-101 is total flow before the bypass
        # tee and TT-102 is mixed return after it, so this is exact at steady state.
        q = 1027.8 * 3890.0 * max(x["FT101"], 0.0) / 60000.0 * (x["TT102"] - x["TT101"])
        if q <= 200.0:
            return 0.0
        # Valve position needed AT SETPOINT for this load: at steady state the
        # return would be SP + measured rise, and with a large counterflow
        # exchanger the facility outlet runs ~1.5 K below that return.
        # Using the setpoint (not the present return temperature) keeps the
        # feed-forward meaningful during warm-up, when the loop is colder than
        # the facility water.
        dt_fws = self.sp_eff + (x["TT102"] - x["TT101"]) - 1.5 - x["TT201"]
        if dt_fws <= 1.0:
            return 100.0
        f_req = q / (995.7 * 4180.0 * dt_fws) * 60000.0   # L/min
        fws_dp = (x["PT201"] - x["PT202"]) * 100.0          # kPa, measured
        return valve_position_for_flow(f_req, fws_dp if fws_dp > 10.0 else 50.0)

    # ------------------------------------------------------------------
    def step(self, x, dt):
        """x: dict of measured inputs; returns dict of outputs."""
        p = self.p
        self.t_state += dt
        self.t_trip += dt
        dew = dew_point(x["T_ROOM"], x["RH_ROOM"])
        self.sp_eff = clamp(max(p["SP_T"], dew + p["DEW_MARGIN"]), p["SP_T_MIN"], p["SP_T_MAX"])
        t_trip_level = p["T_SERVER_MAX"] - 2.0
        dp_meas = (x["PT103"] - x["PT101"]) * 100.0      # kPa

        # ---------------- alarms (always evaluated) -------------------
        al = set()
        sensor_bad = not (0 < x["TT101"] < 100) or not (-1 < x["PT101"] < 6) or x["FT101"] < -1
        if sensor_bad:
            al.add("SENSOR")
        if self.state in (self.RUNNING, self.TRIPPED) and self.pump_run:
            if self.tm["lf_warn"](x["FT101"] < 0.8 * p["F_EXP"], dt):
                al.add("LOW_FLOW_W")
            if self.tm["lf_trip"](x["FT101"] < 0.5 * p["F_EXP"], dt):
                self._trip("LOW_FLOW")
        if self.tm["ht_warn"](x["TT101"] > self.sp_eff + 3.0, dt):
            al.add("HIGH_TEMP_W")
        if self.tm["ht_trip"](x["TT101"] > t_trip_level, dt):
            self._trip("HIGH_TEMP")
        if x["TT101"] < dew + 2.0:
            al.add("DEW_W")
        # coolant inventory: tank water volume from the gas law, against the
        # volume the measured loop temperature says it should hold
        t_mean = 0.5 * (x["TT101"] + x["TT102"])
        vtw_meas = p["V_TANK"] * (1.0 - (p["P_PRE"] + 1.013) / max(x["PT101"] + 1.013, 0.2))
        vtw_exp = p["VTW_REF"] + p["V_SYS"] * p["BETA"] * (t_mean - p["T_REF"])
        self.inventory_deficit = vtw_exp - vtw_meas
        if self.tm["inv_warn"](self.inventory_deficit > p["INV_WARN_L"], dt):
            al.add("INVENTORY_W")
        if self.tm["inv_trip"](self.inventory_deficit > p["INV_TRIP_L"], dt) and self.state != self.OFF:
            self._trip("INVENTORY")
        if x["PT101"] < 0.5 and self.state != self.OFF:     # tank empty: protect the pump
            self._trip("LOW_STATIC")
        if x["PT102"] > 3.5:
            al.add("HIGH_DISCH_W")
        if x["PT102"] > 3.8:
            self._trip("HIGH_DISCH")
        if x["PDT101"] > 20.0:
            al.add("FILTER_W")
        if x["LDS301"]:
            self._trip("LEAK_TRAY")
        if x["LDS302"]:
            al.add("LEAK_HOSE_W")
        fws_dp = (x["PT201"] - x["PT202"]) * 100.0
        fws_bad = self.xv_open and (fws_dp < 20.0 or (x["FT201"] < 0.5 and self.valve > 20.0))
        if self.tm["fws_lost"](fws_bad, dt):
            al.add("FWS_LOST_W")
        if self.tm["fws_trip"](fws_bad and self.state == self.RUNNING, dt):
            self._trip("FWS_LOST")
        if sensor_bad and self.state in (self.RUNNING, self.STARTING):
            self._trip("SENSOR")
        if x.get("REMOTE_STOP"):
            self._trip("REMOTE_STOP")
        self.alarms = al

        # ---------------- state machine -------------------------------
        if self.state == self.OFF:
            self.pump_run, self.xv_open, self.permit = False, False, False
            self.speed = 0.0
            if x.get("START"):
                self._enter(self.STARTING)
                self.t_valve.preset(0.0)
                self.dp_pi.preset(50.0)
                self.fl_pi.preset(50.0)

        elif self.state == self.STARTING:
            self.pump_run, self.xv_open, self.permit = True, True, False
            ok = x["FT101"] >= 0.8 * p["F_EXP"] and x["PT101"] >= 0.7 and x["TT101"] < t_trip_level
            if self.tm["run_ok"](ok, dt):
                self._enter(self.RUNNING)
            elif self.t_state > 30.0:
                self._trip("START_FAIL")

        elif self.state == self.RUNNING:
            self.pump_run, self.xv_open, self.permit = True, True, True

        if self.state == self.TRIPPED:
            self.permit = False
            stop_after = min(TRIP_ACTIONS[t][0] for t in self.trips)
            close_xv = any(TRIP_ACTIONS[t][1] for t in self.trips)
            hold_valve = any(TRIP_ACTIONS[t][2] for t in self.trips)
            self.pump_run = self.t_trip < stop_after
            if close_xv:
                self.xv_open = False
            if x.get("RESET"):
                self.trips.clear()
                for t in self.tm.values():
                    t.t = 0.0
                self._enter(self.OFF)          # operator restarts with START
                self.t_valve.preset(0.0)
                self.dp_pi.preset(50.0)
                self.fl_pi.preset(50.0)
        else:
            hold_valve = False

        # ---------------- pump speed: dP control with min-flow override
        if self.pump_run:
            if self.state == self.STARTING and self.t_state < 5.0:
                u = 50.0
                self.dp_pi.preset(u)
                self.fl_pi.preset(u)
            elif self.state == self.TRIPPED and "LOW_FLOW" in self.trips:
                u = p["SPEED_MAX"]            # keep trying
            elif self.state == self.TRIPPED and "SENSOR" in self.trips:
                u = self.speed                # hold last speed
            else:
                u_dp = self.dp_pi.step(p["DP_SP"] - dp_meas, dt)
                u_fl = self.fl_pi.step(p["F_MIN"] - x["FT101"], dt)
                u = max(u_dp, u_fl)
                self.dp_pi.update(dt, u)
                self.fl_pi.update(dt, u)
            self.speed = clamp(u, p["SPEED_MIN"], p["SPEED_MAX"])
        else:
            self.speed = 0.0

        # ---------------- valve: supply temperature -------------------
        if not self.xv_open or self.state == self.OFF:
            pass                                    # valve held (fails in place)
        elif hold_valve:
            pass
        elif self.state == self.STARTING and self.t_state < 5.0:
            self.valve = p["VALVE_START"]
        else:
            if p["T_FF"]:      # filtered: every input to it carries sensor noise
                self.ff_f += dt / p["FF_TF"] * (self.valve_feedforward(x) - self.ff_f)
            ff = self.ff_f if p["T_FF"] else 0.0
            # derivative on measurement (not error), filtered
            pv = x["TT101"]
            if self.pv_prev is not None:
                self.dpv += dt / p["T_TF"] * ((pv - self.pv_prev) / dt - self.dpv)
            self.pv_prev = pv
            d = p["T_KP"] * p["T_TD"] * self.dpv
            e = pv - self.sp_eff
            db = p["T_EDB"]                     # error deadband: no action on noise
            e = 0.0 if abs(e) < db else e - math.copysign(db, e)
            u = self.t_valve.step(e, dt, bias=ff + d)
            self.t_valve.update_conditional(dt, x.get("TCV_POS"))
            if abs(u - self.valve) > p["VALVE_DEADBAND"] or u in (p["VALVE_MIN_RUN"], 100.0):
                self.valve = u

        return dict(speed=self.speed, valve=self.valve, pump_run=self.pump_run,
                    xv_open=self.xv_open, permit=self.permit, state=self.state,
                    sp_eff=self.sp_eff, alarms=set(self.alarms), trips=set(self.trips))


# Facility-circuit model used by the feed-forward (must match the plant data).
CV_MAX = 4.7          # control valve
RANGEABILITY = 50.0   # equal-percentage characteristic
K_FIXED_KPA = 26.2    # facility circuit excluding control valve, kPa at 24 L/min (40-plate HX, calibrated)


def valve_cv(pos_pct):
    x = pos_pct / 100.0
    if x <= 0.0:
        return 0.0
    cv_ep = CV_MAX * RANGEABILITY ** (x - 1.0)
    # below 5 % open blend linearly to shut-off
    return cv_ep if x >= 0.05 else cv_ep * x / 0.05


def valve_position_for_flow(f_lpm, dp_avail_kpa):
    """Invert the installed characteristic: position giving f_lpm."""
    if f_lpm <= 0:
        return 0.0
    dp_fixed = K_FIXED_KPA * (f_lpm / 24.0) ** 2
    dp_v = dp_avail_kpa - dp_fixed
    if dp_v <= 0.1:
        return 100.0
    cv_req = (f_lpm / 3.785) / math.sqrt(dp_v / 6.89476)
    if cv_req >= CV_MAX:
        return 100.0
    x = 1.0 + math.log(cv_req / CV_MAX) / math.log(RANGEABILITY)
    return clamp(x * 100.0, 5.0, 100.0)
