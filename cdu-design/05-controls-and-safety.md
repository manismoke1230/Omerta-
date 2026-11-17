# 05 — Controls and safety (Rev C)

The control logic is defined by executable code, not only by this description:

| File | Role |
|---|---|
| [calc/cdu_control.py](calc/cdu_control.py) | Reference controller: the executable specification |
| [calc/cdu_sim.py](calc/cdu_sim.py) | Plant model used to tune it; results in [sim/results.md](sim/results.md) |
| [calc/test_control.py](calc/test_control.py) | 18 logic tests of every trip, alarm and state change (all pass) |
| [plc/CDU10_Main.st](plc/CDU10_Main.st) | PLC program implementing the same logic |

## Hardware

- CODESYS 3.5 compact PLC with a 7 in. touchscreen; 100 ms scan. Full I/O list in [09-electrical.md](09-electrical.md).
- 24 V supply with a 2 s buffer, so the PLC can record a power loss.
- Modbus TCP to site monitoring. Read-only by default; register map in [plc/README.md](plc/README.md).
- **Server load permit:** the PLC output drives the permit relay through a hardware watchdog contact. If the PLC stops or loses power, the permit opens within 500 ms regardless of software.

## Operating states

| State | Pump | Facility shut-off | Control valve | Load permit |
|---|---|---|---|---|
| Off | Stopped | Closed | Held | Open |
| Starting | 50 % for 5 s, then pressure control | Open | Prepositioned to 30 % for 5 s, then in control | Open |
| Running | In control | Open | In control | **Closed** |
| Tripped | Per trip table | Per trip table | Per trip table | Open |

Starting moves to Running when flow is at least 80 % of expected, static pressure is at least 0.7 bar g, and supply is under the trip level, all held for 10 s. If that has not happened within 30 s, the unit trips on start failure.

Trips latch. Reset returns the unit to Off, and the operator restarts it. The operator stop button returns to Off without a trip.

## Control loops

### Pump speed

PI control of the differential pressure across the server loop and bypass, measured as PT-103 (after the flow meter) minus PT-101.

| Item | Value |
|---|---|
| Setpoint | 70 kPa, adjustable 30–100 kPa |
| Speed limits | 30–95 % (95 % cap keeps the CME 1-2 dead-head at 3.48 bar g) |
| Minimum-flow override | A second PI on flow is max-selected with the pressure loop, so speed rises if flow falls below the configured minimum |
| Tuning | Pressure loop 0.4 %/kPa, 4 s; flow loop 2 %/(L/min), 4 s |
| Anti-windup | Both loops track the selected output |

Because pressure is held across the server loop, filter loading and unplugging a server do not change the flow to the servers that remain. The simulation shows 13.0 L/min to the remaining server before and after its neighbour is unplugged (S8), and server flow held at 26.0 L/min while the filter loads from 5 to 30 kPa (S11).

### Supply temperature

PI control of TT-101 by control valve TCV-201, with load feedforward. The settings below were tuned in simulation.

| Item | Value | Reason |
|---|---|---|
| Effective setpoint | The higher of the operator setpoint (32 °C) and room dew point + 3 K, limited to 25–40 °C | Condensation protection |
| Gain, integral time | 8 %/K, 60 s | Best compromise across 2–10 kW and 18–27 °C facility water |
| Derivative | Off | Simulated at 40 s and 80 s; no benefit, more valve travel |
| Feedforward | Valve position needed **at setpoint** for the measured duty: facility flow from a heat balance, then the inverse of the installed valve characteristic, using the measured facility pressure difference; filtered 10 s | Without it, cold start overshoots to 37.6 °C; with it, 32.6 °C |
| Anti-windup | Conditional integration: integrator frozen while the valve is saturated, while the error exceeds 2 K, or while the actuator is more than 5 % behind the command (uses position feedback) | Back-calculation cancelled the feedforward during saturation and caused the cold-start overshoot |
| Error deadband | 0.05 K | Stops valve movement on sensor noise |
| Output deadband | 0.3 % | Cuts valve travel from about 650 % to under 6 % of stroke per hour |
| Valve minimum while running | 5 % | Sensors always see some flow |
| Actuator | Standard 90 s running time | A 35 s actuator was simulated and gave no thermal benefit |

## Alarms and trips

The supply high-temperature trip is a setting, **server maximum inlet temperature minus 2 K**. This gives 38 °C for servers rated at 40 °C, and 43 °C for 45 °C trays. Rev A fixed it at 43 °C, which was too high for 40 °C servers.

| Condition | Warning | Trip | Trip action |
|---|---|---|---|
| Server-loop flow low | Under 80 % of expected for 10 s | Under 50 % for 3 s | Open permit; pump runs at the speed cap for 30 s, then stops |
| Supply temperature high | Effective setpoint + 3 K for 60 s | Server limit − 2 K for 5 s | Open permit; pump and valve keep running |
| Facility water lost (dP under 20 kPa, or no flow with valve over 20 %) | After 10 s | **After 20 s** | Open permit; pump keeps circulating |
| Supply near dew point | Under dew point + 2 K | — | Setpoint raised automatically |
| **Coolant inventory deficit** | Over 0.25 L for 30 s | Over 0.60 L for 10 s | Open permit; pump stops after 60 s |
| Tank empty (static pressure) | — | Under 0.5 bar g | Open permit; stop pump immediately (cavitation) |
| Pump discharge pressure high | 3.5 bar g | 3.8 bar g | Stop pump; open permit |
| Filter differential high | 20 kPa | — | Change filter |
| Leak in drip tray | — | Immediate | Open permit; close facility shut-off; hold valve; pump stops after 60 s |
| Leak at hose connections | Immediate | — | Operator checks |
| Sensor out of range (TT-101, PT-101, FT-101) | Immediate | Immediate | Open permit; pump and valve held |
| Start failure | — | 30 s | Stop pump |
| Remote stop input open | — | Immediate | Stop pump; open permit |
| PLC fault, watchdog or control power lost | — | Hardware | Permit opens by the watchdog relay; facility shut-off springs closed; pump drive falls back to 60 % on its own |
| Network lost | Logged | — | No effect |

### Why the facility-loss trip exists

Without it, the supply trip at 38 °C fires about 58 s after facility water is lost at 10 kW. The loop then mixes toward its stored mean temperature, and supply peaks at 41.4 °C. With a 20 s confirmed facility-loss trip, load is shed at 35.7 °C supply and the peak is 37.6 °C. A 15 s interruption rides through with no trip and a peak of 35.5 °C (simulations S6, S13).

### Why inventory monitoring replaced the low-pressure warning

The tank precharge is 0.8 bar g, so static pressure cannot fall below it until the tank is empty. The Rev A warning at 0.7 bar g would only have fired after about 1 L had already been lost. Rev B computes the tank's water volume from PT-101 using the gas law. It compares that with the volume the loop's measured mean temperature predicts, using a reference captured by an "inventory zero" button after each fill. In simulation, a 0.1 L/min leak gives a warning at 0.31 L lost and a trip at 0.64 L, while the tank still holds coolant (S10).

### Requirement on the site

When the permit opens, the server load must fall below 20 % within 10 s. This can be done through server power capping, the management controller or the bay power contactor. The simulation assumes a 1 s delay and a 1.5 s decay. This is hold point HP-09.

## Failure analysis

Severity (S) and likelihood (L) are each scored from 1 (low) to 5 (high).

| # | Failure | Effect | Detected by | Protection | S | L |
|---|---|---|---|---|---:|---:|
| 1 | Pump stops | No flow to cold plates | FT-101, drive fault | Low-flow trip within 5 s (simulated 4.6 s); spare pump | 4 | 2 |
| 2 | Facility water lost | Loop warms about 5 K/min at 10 kW | PT-201/202, FT-201 | Facility-loss trip at 20 s; peak supply 37.6 °C | 3 | 3 |
| 3 | Hose or disconnect leak outside cabinet | Coolant on floor or hardware | LDS-302, inventory deficit | Warning at 0.25 L, trip at 0.6 L; dry-break couplings; external tray | 4 | 3 |
| 4 | Leak inside cabinet, server loop | Coolant in tray | LDS-301, inventory | Tray holds 2.9× cabinet volume; pump stops | 2 | 2 |
| 5 | Leak inside cabinet, facility side | Unlimited water supply | LDS-301 | Fail-closed shut-off XV-201 | 4 | 2 |
| 6 | Plate leak between circuits | Fluids mix | Inventory rising or falling, coolant sample | Inventory alarm in both directions; quarterly sampling | 3 | 1 |
| 7 | Control valve sticks closed | Supply rises | TT-101, position feedback | High-temperature trip | 3 | 2 |
| 8 | Control valve sticks open on cold water | Supply falls toward dew point | TT-101, AT-301 | Dew-point warning; insulation | 2 | 2 |
| 9 | Filter blocks | Pump speeds up to hold pressure | PDT-101 | Warning at 20 kPa; flow held to 30 kPa (S11) | 2 | 3 |
| 10 | Pump dead-headed, all servers unplugged | Pressure rise | PT-102 | Bypass V-105; 95 % speed cap (3.48 bar g worst case); relief valve | 2 | 4 |
| 11 | Liquid trapped and heated between closed valves | Overpressure | — | Relief on the server loop; thermal relief on the facility side | 3 | 2 |
| 12 | Temperature sensor drifts | Wrong supply temperature | Two-sided heat balance mismatch | Out-of-range trip; annual calibration | 3 | 2 |
| 13 | Air after a server swap | Noisy flow, poor cooling | Flow fluctuation | Automatic vent; fill-and-vent mode | 2 | 4 |
| 14 | Condensation on facility pipe | Water on equipment | LDS-301 | Vapour-sealed insulation; warm loop | 2 | 3 |
| 15 | PLC failure | No control | Watchdog | Permit opens by hardware; drive runs at 60 % fallback | 3 | 1 |
| 16 | Site does not shed load on permit | Servers run hot | TT-101 | Servers' own thermal protection; HP-09 makes shedding a site requirement | 4 | 2 |

## Pressure protection summary

| Level | Value |
|---|---:|
| Cold fill | 1.0 bar g |
| Normal running, pump discharge (simulated at 10 kW) | 2.06 bar g |
| Worst case, dead-headed at the 95 % speed cap (published CME 1-2 curve) | 3.48 bar g |
| High-pressure trip | 3.8 bar g |
| Relief valve | 4.0 bar g |
| Hydrostatic test | 6.0 bar g, with the relief valve removed and its port plugged, and the tank isolated |
| Lowest component rating | 6 bar (expansion tank) |
