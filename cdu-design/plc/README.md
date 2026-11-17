# CDU-10 PLC program

| File | Content |
|---|---|
| `CDU10_Main.st` | Complete program in IEC 61131-3 Structured Text (CODESYS 3.5 dialect) |

## How it relates to the reference model

`calc/cdu_control.py` is the executable specification. It is tuned and verified against the plant model (`calc/cdu_sim.py`, results in `sim/results.md`) and tested by `calc/test_control.py` (18 logic tests, all passing). This program implements the same blocks in the same order.

**Status:** written but **not yet compiled**; no PLC toolchain is available in the design environment. Compiling on the selected controller and running the 18 logic cases on the real PLC is factory test CT-13.

Known differences from the reference model:

| Item | Reference | PLC | Effect |
|---|---|---|---|
| Pump-loop tracking signal | Output of the current scan | Output of the previous scan | 0.1 s lag in anti-windup; negligible |
| Start command | Level (held true in simulation) | Rising edge of HMI Start | None; same after one press |
| Operator stop | Not modelled | Returns to Off with no trip | Intended |

## Task and hardware safety

- Cyclic task at 100 ms.
- **Load permit is hardwired in series:** PLC output → permit relay coil → contact of a hardware watchdog relay, retriggered by a PLC heartbeat output. If the PLC stops, faults or loses power, the watchdog drops within 500 ms and the permit opens. The software is not the only protection.
- Facility shut-off XV-201 is spring-return closed: loss of control power closes it.
- Pump drive is configured with its own fallback: on loss of the analogue speed signal it runs at a fixed 60 % (CME drive menu setting), so circulation continues if the PLC fails.
- Remote stop input is normally closed (wire break = stop).

## Modbus TCP map (server on port 502)

Input registers (read-only). REAL values are scaled 16-bit signed integers.

| Address | Value | Scale |
|---:|---|---|
| 30001 | State (0 Off, 1 Starting, 2 Running, 3 Tripped) | 1 |
| 30002 | Trip word (bits per `E_Trip`) | bits |
| 30003 | Alarm word (bits per `E_Alarm`) | bits |
| 30004 | TT-101 supply temperature | 0.01 °C |
| 30005 | TT-102 return temperature | 0.01 °C |
| 30006 | TT-201 facility supply temperature | 0.01 °C |
| 30007 | TT-202 facility return temperature | 0.01 °C |
| 30008 | FT-101 server-loop flow | 0.01 L/min |
| 30009 | FT-201 facility flow | 0.01 L/min |
| 30010 | PT-101 static pressure | 0.001 bar |
| 30011 | PT-102 pump discharge | 0.001 bar |
| 30012 | Supply-return differential | 0.1 kPa |
| 30013 | Filter differential PDT-101 | 0.1 kPa |
| 30014 | Pump speed | 0.1 % |
| 30015 | Control valve command / feedback | 0.1 % each (30015/30016) |
| 30017 | Heat duty, server side | 1 W |
| 30018 | Heat duty, facility side | 1 W |
| 30019 | Effective setpoint | 0.01 °C |
| 30020 | Room dew point | 0.01 °C |
| 30021 | Coolant inventory deficit | 0.001 L |
| 30022 | Load permit (1 = closed) | 1 |

Holding registers (writable only when write access is enabled on the HMI; disabled by default): 40001 supply setpoint (0.01 °C), 40002 dP setpoint (0.1 kPa), 40003 expected flow (0.01 L/min), 40004 minimum flow (0.01 L/min), 40005 server maximum inlet temperature (0.01 °C). Start, stop, reset and inventory zero are local-only.

## HMI screens

1. **Overview:** P&ID mimic with live values, state, permit status.
2. **Alarms:** active and historical alarms and trips, with time stamps; reset button.
3. **Server configuration:** number and type of connected servers. This sets expected and minimum flow and the server temperature limit. It is part of the tray-swap procedure.
4. **Trends:** 24 h of supply, return, facility temperatures, flows, valve, speed, static pressure, inventory.
5. **Maintenance:** fill-and-vent mode (manual pump speed, facility closed), inventory zero, filter-change log, I/O test page (password).
