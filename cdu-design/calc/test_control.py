#!/usr/bin/env python3
"""Logic tests for the CDU-10 reference controller (cdu_control.py).

    python3 test_control.py

Each test drives the controller with fixed inputs (no plant model) and checks
one protective function or state transition against 05-controls-and-safety.md.
The same cases form the PLC logic test at factory acceptance (test CT-13).
"""
import math

import cdu_control as ctl

DT = 0.1


def healthy(**over):
    x = dict(TT101=32.0, TT102=37.0, TT201=27.0, TT202=34.0, PT101=1.05, PT102=2.0, PT103=1.75,
             PT201=3.25, PT202=2.75, PDT101=5.0, FT101=29.0, FT201=19.0, T_ROOM=24.0, RH_ROOM=50.0,
             LDS301=False, LDS302=False, TCV_POS=80.0, START=True, RESET=False)
    # inventory consistent with the fill reference at the healthy loop temperature
    c = ctl.DEFAULTS
    vtw = c["VTW_REF"] + c["V_SYS"] * c["BETA"] * (34.5 - c["T_REF"])
    x["PT101"] = (c["P_PRE"] + 1.013) / (1 - vtw / c["V_TANK"]) - 1.013
    x.update(over)
    return x


def run(c, x, seconds):
    out = None
    for _ in range(int(round(seconds / DT))):
        out = c.step(x, DT)
    return out


def started():
    c = ctl.Controller()
    out = run(c, healthy(), 20.0)
    assert out["state"] == "RUNNING", out["state"]
    return c


def test_start_to_running():
    c = ctl.Controller()
    out = run(c, healthy(), 5.0)
    assert out["state"] == "STARTING" and not out["permit"]
    out = run(c, healthy(), 10.0)
    assert out["state"] == "RUNNING" and out["permit"] and out["pump_run"] and out["xv_open"]


def test_start_fail():
    c = ctl.Controller()
    out = run(c, healthy(FT101=5.0), 31.0)
    assert "START_FAIL" in out["trips"] and not out["pump_run"] and not out["permit"]


def test_low_flow_trip():
    c = started()
    out = run(c, healthy(FT101=10.0), 2.5)
    assert out["permit"], "must not trip before 3 s"
    out = run(c, healthy(FT101=10.0), 0.7)
    assert "LOW_FLOW" in out["trips"] and not out["permit"]
    out = run(c, healthy(FT101=10.0), 25.0)
    assert out["pump_run"] and out["speed"] == ctl.DEFAULTS["SPEED_MAX"], "keeps trying"
    out = run(c, healthy(FT101=10.0), 6.0)
    assert not out["pump_run"], "pump stops 30 s after the trip"


def test_low_flow_warning_only():
    c = started()
    out = run(c, healthy(FT101=20.0), 11.0)        # 69 % of expected
    assert "LOW_FLOW_W" in out["alarms"] and out["permit"]


def test_high_temp_trip_level_follows_server_limit():
    c = started()
    out = run(c, healthy(TT101=37.9), 10.0)
    assert out["permit"], "37.9 C is under the 38 C trip for 40 C servers"
    out = run(c, healthy(TT101=38.3), 5.2)
    assert "HIGH_TEMP" in out["trips"] and not out["permit"] and out["pump_run"]
    c = ctl.Controller(T_SERVER_MAX=45.0)
    run(c, healthy(), 20.0)
    out = run(c, healthy(TT101=42.0), 10.0)
    assert out["permit"], "45 C servers trip at 43 C"


def test_leak_tray():
    c = started()
    out = run(c, healthy(LDS301=True), 0.2)
    assert "LEAK_TRAY" in out["trips"] and not out["permit"] and not out["xv_open"]
    v0 = out["valve"]
    out = run(c, healthy(LDS301=True), 55.0)
    assert out["pump_run"] and out["valve"] == v0, "valve held, pump runs on"
    out = run(c, healthy(LDS301=True), 6.0)
    assert not out["pump_run"]


def test_hose_leak_is_alarm_only():
    c = started()
    out = run(c, healthy(LDS302=True), 5.0)
    assert "LEAK_HOSE_W" in out["alarms"] and out["permit"]


def test_inventory_warning_then_trip():
    c = started()
    base = healthy()
    # gas law: lower PT101 so the tank holds 0.35 L less than expected
    p = ctl.DEFAULTS
    vtw = p["V_TANK"] * (1 - (p["P_PRE"] + 1.013) / (base["PT101"] + 1.013)) - 0.35
    low = (p["P_PRE"] + 1.013) / (1 - vtw / p["V_TANK"]) - 1.013
    out = run(c, healthy(PT101=low), 29.0)
    assert "INVENTORY_W" not in out["alarms"]
    out = run(c, healthy(PT101=low), 2.0)
    assert "INVENTORY_W" in out["alarms"] and out["permit"]
    vtw2 = vtw - 0.35                                # 0.70 L lost
    lower = (p["P_PRE"] + 1.013) / (1 - vtw2 / p["V_TANK"]) - 1.013
    out = run(c, healthy(PT101=lower), 10.5)
    assert "INVENTORY" in out["trips"] and not out["permit"]
    assert lower > 0.7, "trip comes while the tank still holds coolant"


def test_tank_empty_stops_pump():
    c = started()
    out = run(c, healthy(PT101=0.4), 0.2)
    assert "LOW_STATIC" in out["trips"] and not out["pump_run"]


def test_high_discharge():
    c = started()
    out = run(c, healthy(PT102=3.6), 1.0)
    assert "HIGH_DISCH_W" in out["alarms"] and out["permit"]
    out = run(c, healthy(PT102=3.9), 0.2)
    assert "HIGH_DISCH" in out["trips"] and not out["pump_run"]


def test_facility_loss_ride_through_and_trip():
    c = started()
    lost = healthy(PT201=3.0, PT202=3.0, FT201=0.0)
    out = run(c, lost, 15.0)
    assert "FWS_LOST_W" in out["alarms"] and out["permit"], "rides through 15 s"
    out = run(c, healthy(), 1.0)
    assert out["permit"]
    out = run(c, lost, 20.5)
    assert "FWS_LOST" in out["trips"] and not out["permit"] and out["pump_run"]


def test_filter_alarm():
    c = started()
    out = run(c, healthy(PDT101=22.0), 0.2)
    assert "FILTER_W" in out["alarms"] and out["permit"]


def test_sensor_fault_holds_valve():
    c = started()
    v0 = run(c, healthy(), 0.1)["valve"]
    out = run(c, healthy(TT101=150.0), 0.2)
    assert "SENSOR" in out["trips"] and not out["permit"] and out["valve"] == v0 and out["pump_run"]


def test_remote_stop():
    c = started()
    out = run(c, healthy(REMOTE_STOP=True), 0.2)
    assert "REMOTE_STOP" in out["trips"] and not out["pump_run"] and not out["permit"]


def test_reset_returns_to_off_then_start():
    c = started()
    run(c, healthy(LDS301=True), 1.0)
    x = healthy(RESET=True, START=False)
    out = run(c, x, 0.1)
    assert out["state"] == "OFF" and not out["trips"]
    out = run(c, healthy(), 20.0)
    assert out["state"] == "RUNNING"


def test_dew_point_raises_setpoint():
    c = started()
    rh = 100.0 * math.exp(17.62 * 30.5 / (243.12 + 30.5) - 17.62 * 34 / (243.12 + 34))   # 30.5 C dew point at 34 C
    out = run(c, healthy(T_ROOM=34.0, RH_ROOM=rh), 1.0)
    assert abs(out["sp_eff"] - 33.5) < 0.05, out["sp_eff"]
    assert "DEW_W" in out["alarms"], "32 C supply is under dew point + 2 K"


def test_output_limits():
    c = started()
    out = run(c, healthy(PT103=1.05, FT101=15.0), 30.0)     # no dP, low flow: drive wants max
    assert out["speed"] <= ctl.DEFAULTS["SPEED_MAX"] + 1e-9
    c = started()
    out = run(c, healthy(TT101=25.0), 30.0)                 # far below setpoint
    assert out["valve"] >= ctl.DEFAULTS["VALVE_MIN_RUN"] - 1e-9


def test_valve_feedforward_inverse():
    for f in (2.0, 10.0, 18.6):
        pos = ctl.valve_position_for_flow(f, 50.0)
        cv = ctl.valve_cv(pos)
        dp_v = 50.0 - ctl.K_FIXED_KPA * (f / 24.0) ** 2
        f_back = cv * 3.785 * math.sqrt(dp_v / 6.89476)
        assert abs(f_back - f) / f < 0.01, (f, f_back)


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    failed = 0
    for n, f in tests:
        try:
            f()
            print(f"PASS {n}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {n}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
