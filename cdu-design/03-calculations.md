# 03 — Calculations (Rev B)

All figures come from [calc/cdu_calc.py](calc/cdu_calc.py); full output is in [calc/results.txt](calc/results.txt). They are design estimates. Inputs marked "assumed" are replaced by vendor data at the hold points. Transient behaviour is in [sim/results.md](sim/results.md).

## Changes from Rev A

| Input | Rev A | Rev B | Source |
|---|---|---|---|
| PG25 viscosity at the 34.5 °C loop mean | 1.7 mPa·s (assumed) | 1.79 mPa·s | Interpolated from Dow-linked data: 2.72 mPa·s at 20 °C, 1.15 at 50 °C |
| PG25 conductivity | 0.47 W/(m·K) (assumed) | 0.475 W/(m·K) | 0.485 published at 50 °C |
| B25T area per plate | 0.060 m² (assumed) | 0.062 m² | SWEP sheets: 1.1 m² for 20 plates, 3.02 m² for 50 |
| Exchanger correlation | Martin only | Martin, cross-checked with Kumar | — |

## Fluid properties used

| Fluid | Density, kg/m³ | Heat capacity, kJ/(kg·K) | Viscosity, mPa·s | Conductivity, W/(m·K) | Prandtl |
|---|---:|---:|---:|---:|---:|
| PG25 near 35 °C | 1,027.8 | 3.89 | 1.79 | 0.475 | 14.7 |
| Water near 30 °C | 995.7 | 4.18 | 0.80 | 0.615 | 5.4 |

## 1. Rating-point heat balance

| Circuit | Flow | Temperatures | Rise |
|---|---|---|---|
| Server loop, PG25 | 30 L/min | 37.0 → 32.0 °C | 5.0 K |
| Facility water | 24 L/min | 27.0 → 33.0 °C | 6.0 K |

Log-mean temperature difference is 4.48 K, so the exchanger needs **UA = 2,233 W/K** before margin.

## 2. Heat exchanger

Method: Martin's 1996 chevron-plate correlation, single-pass counterflow, 0.3 mm stainless wall. Plate geometry is taken from catalogue dimensions. The enlargement factor is set so the area matches SWEP's published figures. Pressing depth (2.0 mm) and chevron angle (60°) are assumed.

**Short plate (B10T class): rejected in Rev A.** Forty plates gave only 1 % margin, because adding plates lowers channel velocity and the film coefficient falls nearly as fast as the area rises.

**Long plate (B25T class): selected at 30 plates.**

| Plates | Area, m² | UA ÷ required | Server-side drop, kPa | Facility-side drop, kPa |
|---:|---:|---:|---:|---:|
| 20 | 1.12 | 1.52 | 12.9 | 6.0 |
| 24 | 1.36 | 1.65 | 9.4 | 4.5 |
| **30** | **1.74** | **1.82** | **6.6** | **3.2** |
| 40 | 2.36 | 2.08 | 4.4 | 2.2 |

- Clean margin at 30 plates: **82 %** by Martin. The Kumar correlation gives 129 %. Martin is the lower and is the design value.
- If the real chevron angle is 45°, margin is still 44 %.
- Hold-up volume is about 1.6 L per side.

## 3. Off-design performance

The exchanger is derated 20 % for fouling throughout.

**Lowest server supply temperature at full facility flow (24 L/min):**

| Load | Facility water in | Server supply | Server return | Approach |
|---:|---:|---:|---:|---:|
| 5 kW | 27 °C | 28.8 °C | 31.3 °C | 1.8 K |
| 10 kW | 18 °C | 21.6 °C | 26.6 °C | 3.6 K |
| 10 kW | 27 °C | 30.6 °C | 35.6 °C | 3.6 K |
| 10 kW | 32 °C | 35.6 °C | 40.6 °C | 3.6 K |
| 12 kW | 32 °C | 36.3 °C | 42.3 °C | 4.3 K |

The rated 5 K approach holds with a fouled exchanger. A 32 °C supply needs facility water at or below about 28 °C at 10 kW; above that, supply rises with facility temperature.

**Facility flow the control valve passes to hold 32 °C:**

| Load | Water at 18 °C | Water at 22 °C | Water at 27 °C |
|---:|---:|---:|---:|
| 2 kW | 1.9 L/min | 2.6 L/min | 4.8 L/min |
| 5 kW | 4.4 L/min | 5.8 L/min | 10.3 L/min |
| 10 kW | 7.8 L/min | 10.3 L/min | 18.2 L/min |

That is about a 10:1 flow range. The simulation shows the valve stable at both ends: 19 % open at 2 kW on 18 °C water, and 82 % at 10 kW on 27 °C water.

**Reduced server flow:** at 15 L/min and 10 kW, supply is 29.2 °C and return 39.2 °C.

## 4. Server-loop pressure budget at 30 L/min

| Item | Drop, kPa | Status |
|---|---:|---|
| Plate exchanger | 6.6 | Calculated |
| Filter at change-out limit | 30.0 | Assumed |
| Flow meter | 10.0 | Assumed |
| Internal pipe and valves (DN25, 0.90 m/s) | 6.4 | Calculated with assumed fittings |
| **Internal total** | **53.0** | |
| Allowance for the server loop | 100.0 | Requirement |
| **Pump duty** | **153 kPa = 15.2 m at 1.80 m³/h** | Hydraulic power 77 W |

## 5. Pump

Grundfos CME 1-3 class. The published rated point is 2.0 m³/h at 26.2 m. Shut-off head of 31 m is assumed (HP-02), giving the curve H = n² × 31 − 1.20 × Q².

| Condition | Value |
|---|---|
| Speed at duty with dirty filter and 100 kPa server loop | 78 % |
| Speed at the 10 kW simulated operating point (70 kPa setpoint, clean filter) | 65 % |
| Worst-case pressure, dead-headed at the 85 % cap, warm | 3.41 bar g (15 % under the relief setting) |
| Flow at the cap against the full dirty-filter curve | 32.5 L/min |
| Electrical input at duty (35 % wire-to-water assumed) | about 220 W, about 2 % of rated load added as heat |

## 6. Facility side

| Item | Drop, kPa | Status |
|---|---:|---|
| Plate exchanger | 3.2 | Calculated |
| Y-strainer, part loaded | 8.0 | Assumed |
| Flow meter | 7.0 | Assumed |
| Pipe, isolation and shut-off valves | 6.0 | Assumed |
| Control valve, Cv 4.7, fully open | 12.5 | Calculated |
| **Required at 24 L/min** | **36.7** | Interface requirement set at 50 kPa minimum |

Valve authority is 0.34.

## 7. Expansion tank and inventory monitoring

- System volume allowance: 25 L for tank sizing. The simulation loop holds 21 L.
- Expansion from 15 °C to 50 °C: 0.39 L.
- 8 L tank, 0.8 bar g precharge: holds 0.79 L at the 1.0 bar g fill and accepts a further 1.43 L before 1.5 bar g.
- Static pressure fully warm: about 1.1 bar g (1.05 bar g simulated at 10 kW).
- Pressure cannot fall below the 0.8 bar g precharge until the tank is empty. Leak detection therefore uses the computed inventory (see [05-controls-and-safety.md](05-controls-and-safety.md)), not a pressure threshold.
- Sensitivity at 1.05 bar g: 3.4 L per bar. A transmitter offset of ±0.03 bar is about ±0.1 L, and is removed by the inventory zero at fill. A 1 K error in mean temperature is 0.01 L.

## 8. Loss of cooling

From the dynamic simulation, which supersedes Rev A's lumped estimate:

| Event at 10 kW | Result |
|---|---|
| Facility water lost | Facility-loss alarm at 10 s, trip at 20 s with supply at 35.6 °C; peak supply 37.4 °C after load is shed |
| Facility water off for 15 s | No trip; peak supply 35.5 °C |
| Pump power lost | Flow below 50 % within 1 s; low-flow trip at 4.6 s; server outlet rises 1.7 K before load is shed |

## 9. Measurement uncertainty at rating

- Flow: ±0.49 L/min (1.6 %).
- Temperature rise: ±0.1 K on 5.0 K (2.0 %), using a matched, calibrated pair.
- Combined heat balance: about **±2.8 %**. The acceptance band is ±5 %. The simulated two-sided balance closes to 10.00 kW against 10.14 kW, a difference equal to the 133 W of pump heat.
