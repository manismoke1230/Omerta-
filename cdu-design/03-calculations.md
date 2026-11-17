# 03 — Calculations (Rev C)

All figures come from [calc/cdu_calc.py](calc/cdu_calc.py); full output is in [calc/results.txt](calc/results.txt). They are design estimates. Transient behaviour is in [sim/results.md](sim/results.md).

## Changes since Rev A

| Input | Rev A | Now | Source |
|---|---|---|---|
| PG25 viscosity at the 34.5 °C loop mean | 1.7 mPa·s (assumed) | 1.79 mPa·s | Dow-linked data: 2.72 mPa·s at 20 °C, 1.15 at 50 °C |
| B25T area per plate | 0.060 m² (assumed) | 0.062 m² | SWEP sheets: 1.1 m² for 20 plates, 3.02 m² for 50 |
| Exchanger model | Martin correlation, uncalibrated | **Calibrated to a SWEP SSP rating** (Rev C) | SWEP B25THx50 rating sheet |
| Exchanger size | 30 plates | **40 plates** (Rev C) | Calibrated pressure drop |
| Pump curve | Parabola through the rated point, 31 m shut-off assumed | **Published curves** (Rev C) | Grundfos product datasheet and CM/CME data booklet |
| Pump | CME 1-3 | **CME 1-2** (Rev C) | Published curves |
| Wire-to-water efficiency | 35 % (assumed) | 27 % | Grundfos P1 and P2 curves |

## Fluid properties

| Fluid | Density, kg/m³ | Heat capacity, kJ/(kg·K) | Viscosity, mPa·s | Conductivity, W/(m·K) | Prandtl |
|---|---:|---:|---:|---:|---:|
| PG25 near 35 °C | 1,027.8 | 3.89 | 1.79 | 0.475 | 14.7 |
| Water near 30 °C | 995.7 | 4.18 | 0.80 | 0.615 | 5.4 |

## 1. Rating-point heat balance

| Circuit | Flow | Temperatures | Rise |
|---|---|---|---|
| Server loop, PG25 | 30 L/min | 37.0 → 32.0 °C | 5.0 K |
| Facility water | 24 L/min | 27.0 → 33.0 °C | 6.0 K |

The log-mean temperature difference is 4.48 K, so the exchanger needs **UA = 2,233 W/K** before margin.

## 2. Heat exchanger

### Calibration against the manufacturer's software

SWEP publishes an SSP rating for a B25THx50 unit: ethylene glycol 25 % against water, 14 kW, counterflow. I ran my model on that exact case:

| Quantity | Model before | SWEP | Model after calibration |
|---|---:|---:|---:|
| Overall coefficient, clean | 2,541 W/m²K | 3,500 W/m²K | 3,500 W/m²K |
| Pressure drop, glycol side | 5.3 kPa | 11.4 kPa | 11.6 kPa |
| Pressure drop, water side | 3.4 kPa | 7.36 kPa | 7.20 kPa |
| Area, 50 plates | 2.98 m² | 3.02 m² | — |
| Channel velocity, glycol side | 0.139 m/s | 0.132 m/s | — |

The calibration multiplies film coefficients by 1.41 and channel friction by 2.97, and sets the port loss coefficient to 0.96. The uncalibrated model was conservative on heat transfer but **under-predicted pressure drop by more than half**, which is unsafe for the pump budget. All results below use the calibrated model.

Limits of the calibration: it rests on one rating point, at similar Reynolds numbers (about 500–700 against our 230–510) but with a different glycol. The vendor's rating at our exact duty is still required (HP-03).

### Plate count

| Plates | Area, m² | UA ÷ required | Server-side drop, kPa | Facility-side drop, kPa |
|---:|---:|---:|---:|---:|
| 20 | 1.12 | 2.08 | 36.4 | 16.5 |
| 24 | 1.36 | 2.27 | 26.1 | 12.0 |
| 30 | 1.74 | 2.52 | 17.7 | 8.3 |
| **40** | **2.36** | **2.88** | **11.2** | **5.2** |
| 50 | 2.98 | 3.18 | 8.0 | 3.8 |

At 30 plates the server-side drop of 17.7 kPa breaks the 15 kPa-per-side limit in RFQ-02. **Forty plates are selected:** 11.2 / 5.2 kPa, with a clean thermal margin of 188 %. The uncalibrated Kumar correlation gives 158 %. Hold-up volume is about 2.2 L per side.

## 3. Off-design performance

The exchanger is derated 20 % for fouling throughout.

**Lowest server supply temperature at full facility flow (24 L/min):**

| Load | Facility water in | Server supply | Server return | Approach |
|---:|---:|---:|---:|---:|
| 5 kW | 27 °C | 28.2 °C | 30.7 °C | 1.2 K |
| 10 kW | 18 °C | 20.5 °C | 25.5 °C | 2.5 K |
| 10 kW | 27 °C | 29.5 °C | 34.5 °C | 2.5 K |
| 10 kW | 32 °C | 34.5 °C | 39.5 °C | 2.5 K |
| 12 kW | 32 °C | 35.0 °C | 41.0 °C | 3.0 K |

The 32 °C supply can be held at 10 kW with facility water up to about 29.5 °C. That covers cooling-tower water in a Columbus summer: the ASHRAE 0.4 % evaporation wet-bulb is 24.7 °C, plus a typical tower and plant approach.

**Facility flow the control valve passes to hold 32 °C:**

| Load | Water at 18 °C | Water at 22 °C | Water at 27 °C |
|---:|---:|---:|---:|
| 2 kW | 1.9 L/min | 2.6 L/min | 4.8 L/min |
| 5 kW | 4.4 L/min | 5.8 L/min | 9.7 L/min |
| 10 kW | 7.6 L/min | 9.7 L/min | 15.5 L/min |

**Reduced server flow:** at 15 L/min and 10 kW, supply is 27.9 °C and return 37.9 °C.

## 4. Server-loop pressure budget at 30 L/min

| Item | Drop, kPa | Status |
|---|---:|---|
| Plate exchanger, 40 plates | 11.2 | Calculated, calibrated to SWEP |
| Filter at change-out limit | 30.0 | Assumed (HP-04) |
| Flow meter | 10.0 | Assumed (HP-04) |
| Internal pipe and valves (DN25, 0.90 m/s) | 6.4 | Calculated with assumed fittings |
| **Internal total** | **57.6** | |
| Allowance for the server loop | 100.0 | Requirement |
| **Pump duty** | **158 kPa = 15.6 m at 1.80 m³/h** | Hydraulic power 79 W |

## 5. Pump selection

Curves are read from the published Grundfos charts. They are fitted as H = c₀n² + c₁nQ + c₂Q², with H in metres, Q in m³/h and n the speed fraction. Reading accuracy is about ±0.5 m.

| Pump | Curve at 100 % | Speed for duty | Speed cap for ≤ 3.5 bar g dead-head | Server pressure at cap, dirty filter | Flow at cap |
|---|---|---:|---:|---:|---:|
| CME 1-3 (3 stages) | 39.6 − 1.47Q − 2.33Q² | 80 % | 77 % | 81 kPa ✗ | 28.8 L/min ✗ |
| **CME 1-2 (2 stages)** | **25.6 − 1.55Q − 1.24Q²** | **93 %** | **95 %** | **108 kPa ✓** | **30.6 L/min ✓** |

The CME 1-3's shut-off head is 39.6 m, not the 31 m assumed in Rev A. Capped low enough to keep dead-head pressure safe, it cannot deliver 100 kPa to the servers. The CME 1-2 meets both limits on the same 0.55 kW single-phase motor, with Rp 1 ports and a 16 bar rating. It is the selected pump.

| Condition | Value |
|---|---|
| Speed at the 10 kW operating point (70 kPa setpoint, clean filter) | 77 % calculated, 78.7 % simulated |
| Speed with the filter fully loaded (simulated) | 84.6 % |
| Worst-case dead-head at the 95 % cap, warm | 3.48 bar g |
| Electrical input at the design duty (27 % wire-to-water) | about 290 W |
| Pump heat added to the coolant at the simulated operating point | 180 W |

## 6. Facility side

| Item | Drop, kPa | Status |
|---|---:|---|
| Plate exchanger, 40 plates | 5.2 | Calculated, calibrated |
| Y-strainer, part loaded | 8.0 | Assumed |
| Flow meter | 7.0 | Assumed |
| Pipe, isolation and shut-off valves | 6.0 | Assumed |
| Control valve, Cv 4.7, fully open | 12.5 | Calculated |
| **Required at 24 L/min** | **38.8** | Interface requirement: 50 kPa minimum |

Valve authority is 0.32.

## 7. Expansion tank and inventory monitoring

- Volume allowance: 25 L for tank sizing. The simulation loop holds 21 L.
- Expansion from 15 °C to 50 °C: 0.39 L. A 7.6–8 L tank (2 US gal) at 0.8 bar g precharge accepts 1.43 L between the 1.0 bar g fill and 1.5 bar g.
- Static pressure warm: 1.05 bar g simulated at 10 kW.
- Pressure cannot fall below the precharge until the tank is empty, so leak detection uses computed inventory (see [05-controls-and-safety.md](05-controls-and-safety.md)).
- Sensitivity: 3.4 L per bar at 1.05 bar g. A ±0.03 bar transmitter offset is ±0.1 L, removed by the inventory zero at fill.

## 8. Loss of cooling (from the simulation)

| Event at 10 kW | Result |
|---|---|
| Facility water lost | Alarm at 10 s; trip at 20 s with supply at 35.7 °C; peak 37.6 °C after load is shed |
| Facility water off for 15 s | No trip; peak 35.5 °C |
| Pump power lost | Flow under 50 % within 1 s; low-flow trip at 4.6 s; server outlet rises 1.7 K before load is shed |

## 9. Measurement uncertainty at rating

- Flow: ±0.49 L/min (1.6 %).
- Temperature rise: ±0.1 K on 5.0 K (2.0 %).
- Combined heat balance: about **±2.8 %**, against an acceptance band of ±5 %.
- The simulated two-sided balance is 10.00 kW server side against 10.18 kW facility side. The difference is the 180 W of pump heat.
