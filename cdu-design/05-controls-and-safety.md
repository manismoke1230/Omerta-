# 05 — Controls and safety

## Hardware

- Compact industrial PLC with analogue input, analogue output and relay modules.
- 7" touchscreen on the front door.
- 24 V DC supply with a small buffer module, so the controller rides through brief dips and can report a power loss.
- Modbus TCP server for site monitoring: all values readable; writes limited to setpoints and disabled by default.
- **Server load permit relay:** a hardwired, normally-open contact held closed only while the unit is healthy. The bay's power distribution or the servers' management interlock uses it. Loss of control power opens it.

## Operating states

| State | Pump | Facility shut-off | Control valve | Load permit |
|---|---|---|---|---|
| Off | Stopped | Closed | Held | Open |
| Fill and vent | Low speed, manual | Closed | Held | Open |
| Starting | Ramps to setpoint; waits for flow and pressure for 30 s | Open | In control | Open |
| Running | In control | Open | In control | **Closed** |
| Warning | In control | Open | In control | Closed |
| Tripped | Per trip table | Per trip table | Per trip table | Open |

A trip latches and needs a local reset.

## Control loops

**Pump speed.** PI control of supply-to-return differential pressure (PT-103 minus PT-101). Default setpoint 70 kPa, adjustable 30–100 kPa. Speed limited to 30–85 %. If flow falls below a set minimum, speed is raised regardless of pressure.

**Supply temperature.** PI control of TT-101 by control valve TCV-201. The setpoint in use is the higher of the operator setpoint (default 32 °C) and room dew point plus 3 K. Valve minimum opening is 5 % while running so the sensors always see flow.

**Start-up.** The control valve opens to 30 % before the pump ramps, to avoid an initial temperature overshoot.

## Alarms and trips

| Condition | Warning | Trip | Trip action |
|---|---|---|---|
| Server-loop flow low | Below 80 % of expected for 10 s | Below 50 % for 5 s | Open load permit; pump keeps trying for 30 s, then stops |
| Supply temperature high | Setpoint + 3 K for 60 s | 43 °C for 5 s (set 2 K under the server limit) | Open load permit; pump and facility flow continue |
| Supply temperature near dew point | Under dew point + 2 K | — | Setpoint raised automatically |
| Static pressure low (coolant loss) | 0.7 bar g | 0.5 bar g | Open load permit; stop pump to prevent dry running |
| Pump discharge pressure high | 3.5 bar g | 3.8 bar g | Stop pump; open load permit |
| Filter differential high | 20 kPa | — | Change filter |
| Leak in drip tray | — | Immediate | Open load permit; close facility shut-off; pump runs 60 s, then stops |
| Leak at hose connections | Immediate | — | Operator checks; no automatic stop |
| Facility water lost (low pressure difference or flow) | Immediate | Via high supply temperature | Pump keeps circulating to use the loop's thermal mass |
| Sensor out of range | Immediate | If the sensor is TT-101, FT-101 or PT-101 | Open load permit; pump holds last speed |
| PLC fault or watchdog | — | Immediate | Load permit opens by hardware; pump drive falls back to its own fixed speed |
| Network lost | Logged | — | No effect on operation |
| Control power lost | — | Immediate | Load permit opens; facility shut-off springs closed |

## Failure analysis

Severity and likelihood are scored 1 (low) to 5 (high).

| # | Failure | Effect | Detected by | Protection | Sev. | Lik. |
|---|---|---|---|---|---:|---:|
| 1 | Pump stops | No flow to cold plates | FT-101, drive fault | Hardwired load trip; spare pump on shelf | 4 | 2 |
| 2 | Facility water lost | Loop warms about 5 K/min at 10 kW | PT-201/202, FT-201, TT-101 | High-temperature trip at 43 °C, about 2 minutes of margin | 3 | 3 |
| 3 | Hose or disconnect leak outside cabinet | Coolant on floor or hardware | LDS-302, static pressure | Low-pressure trip; dry-break couplings; external tray | 4 | 3 |
| 4 | Leak inside cabinet, server loop | Coolant in tray | LDS-301, static pressure | Tray holds three times cabinet volume; pump stops | 2 | 2 |
| 5 | Leak inside cabinet, facility side | Unlimited water supply | LDS-301 | Fail-closed shut-off XV-201 | 4 | 2 |
| 6 | Exchanger plate leak between circuits | Facility water enters server loop, or coolant leaves | Rising or falling static pressure, coolant sample | Pressure alarms both directions; periodic sampling | 3 | 1 |
| 7 | Control valve sticks closed | Supply temperature rises | TT-101 | High-temperature trip; valve position feedback | 3 | 2 |
| 8 | Control valve sticks open on cold water | Supply falls toward dew point | TT-101, AT-301 | Dew-point warning; insulation on facility side | 2 | 2 |
| 9 | Filter blocks | Flow falls | PDT-101, FT-101 | Early warning at 20 kPa; pump has head in reserve | 2 | 3 |
| 10 | Pump dead-headed, all trays unplugged | Pressure rise, pump heating | PT-102 | Bypass V-105; 85 % speed cap; relief valve | 2 | 4 |
| 11 | Trapped liquid heated between closed valves | Overpressure | — | Relief on server loop; thermal relief on facility side | 3 | 2 |
| 12 | Temperature sensor drifts | Wrong supply temperature | Cross-check with TT-102 and heat balance | Out-of-range trip; annual calibration | 3 | 2 |
| 13 | Air in loop after tray swap | Noisy flow, poor cooling | Flow fluctuation | Automatic vent; fill-and-vent mode | 2 | 4 |
| 14 | Condensation on facility pipe | Water on equipment | Visual, LDS-301 | Vapour-sealed insulation; warm loop | 2 | 3 |

The highest combined scores are items 3 and 10, both tied to frequent tray swaps. The design answers them with dry-break couplings rated for high cycle counts, an external tray under the manifold, the bypass and the speed cap.

## Pressure protection summary

| Level | Value |
|---|---:|
| Cold fill | 1.0 bar g |
| Normal running, pump discharge | about 2.6 bar g |
| Worst case, dead-headed at speed cap | 3.4 bar g |
| High-pressure trip | 3.8 bar g |
| Relief valve | 4.0 bar g |
| Hydrostatic test | 6.0 bar g |
| Lowest component rating | 6 bar (expansion tank) |
