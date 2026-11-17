# 03 — Calculations

All figures come from [calc/cdu_calc.py](calc/cdu_calc.py); full output is in [calc/results.txt](calc/results.txt). These are design estimates. Inputs marked "assumed" are replaced by vendor data at the hold points.

## Fluid properties used

| Fluid | Density, kg/m³ | Heat capacity, kJ/(kg·K) | Viscosity, mPa·s | Conductivity, W/(m·K) |
|---|---:|---:|---:|---:|
| PG25 near 30 °C | 1,027.8 | 3.89 | 1.7 (assumed) | 0.47 (assumed) |
| Water near 30 °C | 995.7 | 4.18 | 0.80 | 0.615 |

## 1. Rating-point heat balance

| Circuit | Flow | Temperatures | Rise |
|---|---|---|---|
| Server loop, PG25 | 30 L/min | 37.0 → 32.0 °C | 5.0 K |
| Facility water | 24 L/min | 27.0 → 33.0 °C | 6.0 K |

Log-mean temperature difference is 4.48 K, so the exchanger needs **UA = 2,233 W/K** before any margin.

## 2. Heat exchanger selection

Method: Martin's 1996 chevron-plate correlation for film coefficient and friction, single-pass counterflow, 0.3 mm stainless wall. Plate geometry is taken from catalogue dimensions with pressing depth 2.0 mm, area enlargement 1.17 and chevron angle 60° assumed.

**Short plate (B10T class, 289 × 119 mm): rejected.**

| Plates | UA ÷ required |
|---:|---:|
| 30 | 0.89 |
| 40 | 1.01 |
| 60 | 1.22 |

Adding plates lowers channel velocity, so the film coefficient falls nearly as fast as area rises. Sixty plates still leave too little margin for fouling and correlation error.

**Long plate (B25T class, 526 × 119 mm): selected at 30 plates.**

| Plates | Area, m² | UA ÷ required | Server-side drop, kPa | Facility-side drop, kPa |
|---:|---:|---:|---:|---:|
| 20 | 1.08 | 1.46 | 12.2 | 5.8 |
| 24 | 1.32 | 1.58 | 8.9 | 4.3 |
| **30** | **1.68** | **1.75** | **6.3** | **3.1** |
| 40 | 2.28 | 1.99 | 4.2 | 2.1 |

At 30 plates the clean margin is 75 %. If the true chevron angle is as low as 45°, margin is still 38 %. Hold-up volume is about 1.6 L per side.

## 3. Off-design performance

Exchanger derated 20 % for fouling throughout.

**Lowest server supply temperature at full facility flow (24 L/min):**

| Load | Facility water in | Server supply | Server return | Approach |
|---:|---:|---:|---:|---:|
| 5 kW | 27 °C | 28.9 °C | 31.4 °C | 1.9 K |
| 10 kW | 18 °C | 21.7 °C | 26.7 °C | 3.7 K |
| 10 kW | 27 °C | 30.7 °C | 35.7 °C | 3.7 K |
| 10 kW | 32 °C | 35.7 °C | 40.7 °C | 3.7 K |
| 12 kW | 32 °C | 36.5 °C | 42.5 °C | 4.5 K |

The unit holds the 5 K rated approach when fouled, and on the hottest facility water still supplies under 37 °C at 12 kW.

**Facility flow the control valve passes to hold a 32 °C setpoint:**

| Load | Water at 18 °C | Water at 22 °C | Water at 27 °C |
|---:|---:|---:|---:|
| 2 kW | 1.9 L/min | 2.6 L/min | 4.8 L/min |
| 5 kW | 4.4 L/min | 5.9 L/min | 10.4 L/min |
| 10 kW | 7.9 L/min | 10.4 L/min | 18.6 L/min |

The valve works across roughly a 12:1 flow range. The lowest point, about 2 L/min, sets the turndown the valve and the facility flow meter must handle.

**Reduced server flow:** at 15 L/min and 10 kW, supply is 29.4 °C and return 39.4 °C, so low-flow trays are also covered.

## 4. Server-loop pressure budget at 30 L/min

| Item | Drop, kPa | Status |
|---|---:|---|
| Plate exchanger | 6.3 | Calculated |
| Filter at change-out limit | 30.0 | Assumed |
| Flow meter | 10.0 | Assumed |
| Internal pipe and valves (DN25, 0.90 m/s) | 6.4 | Calculated with assumed fittings |
| **Internal total** | **52.7** | |
| Allowance for the server loop | 100.0 | Requirement |
| **Pump duty** | **152.7 kPa = 15.1 m at 1.80 m³/h** | |

Hydraulic power is 76 W.

## 5. Pump

Grundfos CME 1-3 class. Published rated point is 2.0 m³/h at 26.2 m. Shut-off head of 31 m is assumed, giving the curve H = n² × 31 − 1.20 × Q².

| Condition | Speed | Shut-off pressure |
|---|---:|---:|
| Duty point, dirty filter | 78 % | 1.92 bar |
| Speed cap | 85 % | 2.26 bar |
| Uncapped | 100 % | 3.13 bar |

- Worst-case pressure at the cap, dead-headed and warm: **3.41 bar g**, 15 % under the 4.0 bar g relief.
- Flow at the cap against the full dirty-filter curve: 32.5 L/min.
- With a clean filter and a 40 kPa server loop the pump runs at about 58 %.
- Electrical input at duty: about 220 W, assuming 35 % wire-to-water efficiency. This ends up as heat in the coolant and is about 2 % of rated load.

## 6. Facility-side pressure and control valve

| Item | Drop, kPa | Status |
|---|---:|---|
| Plate exchanger | 3.1 | Calculated |
| Y-strainer, part loaded | 8.0 | Assumed |
| Flow meter | 7.0 | Assumed |
| Pipe, isolation and shut-off valves | 6.0 | Assumed |
| Control valve, Cv 4.7, fully open | 12.5 | Calculated |
| **Required at 24 L/min** | **36.6** | |

Valve authority is 0.34. The interface requirement is set at 50 kPa minimum.

## 7. Expansion tank

- System volume allowance: 25 L (cabinet about 5 L, plus hoses and servers).
- Expansion from 15 °C to 50 °C: 0.39 L (assumed coefficient 4.5 × 10⁻⁴ per K).
- 8 L tank, 0.8 bar g precharge: holds 0.79 L at the 1.0 bar g fill, and accepts a further 1.43 L before 1.5 bar g.
- Static pressure fully warm: 1.12 bar g.
- Losing 0.5 L of coolant drops cold static pressure to 0.87 bar g. Alarm is set at 0.7 bar g and trip at 0.5 bar g.

## 8. Loss of cooling

Lumped estimate using 25 L of coolant and an assumed 30 kg of wetted metal.

| Load | Warming rate | 32 → 40 °C | 32 → 45 °C |
|---:|---:|---:|---:|
| 10 kW | 5.2 K/min | 91 s | 149 s |
| 5 kW | 2.6 K/min | 183 s | 297 s |

If the pump stops at full load the cold plates lose flow at once and the servers' own protection governs, within seconds. Both cases are why the load trip is hardwired. Tests FT-3 and FT-4 replace these numbers with measurements.

## 9. Measurement uncertainty at rating

- Flow: ±0.49 L/min (1.6 %), from the ifm SM7000 published accuracy.
- Temperature rise: ±0.1 K on 5.0 K (2.0 %), using a matched and calibrated sensor pair.
- Combined heat balance: about **±2.8 %**. The acceptance band is set at ±5 %.
