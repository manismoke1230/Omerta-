# CDU-10: 10 kW liquid-to-liquid coolant distribution unit

**Detailed design package, Rev B — 17 November 2026**

This folder carries the feasibility report's open questions through to a detailed design. Every engineering decision is made and recorded with its reason. It is a self-contained package, unrelated to the rest of this repository.

## What CDU-10 is

A free-standing, front-serviced unit that cools up to 10 kW of liquid-cooled servers or compute trays in a supervised hardware test bay. The reference site is a hyperscale AI campus in New Albany, Ohio. Heat passes from a PG25 server loop into the building's facility water through a brazed plate heat exchanger.

| | |
|---|---|
| Rated duty | 10 kW |
| Server loop | PG25, 29–30 L/min, 32 °C supply, about 37 °C return |
| Facility water | 27 °C supply, up to 24 L/min, 50 kPa minimum available |
| Rated approach | 5 K (3.6 K predicted with a fouled exchanger) |
| Pressure available to the servers | 100 kPa at 30 L/min; controlled at 70 kPa by default |
| Supply stability (simulated) | ±0.14 K ripple; under 1 K on a 2 → 10 kW step |
| Envelope | 600 W × 800 D × 1200 H mm, about 151 kg filled |
| Power | 208–240 V single-phase, about 275 W running, 1.1 kW maximum |
| Parts cost | about US$28,000 including a spare pump (my estimate, ±40 %) |
| Prototype total | about US$66,000 (range $50,000–80,000), excluding design hours |

## Status

**Rev A (preliminary):** decisions, design basis, sizing, P&ID, controls concept, failure analysis, cost, test plan.

**Rev B (this issue) adds:**

- Calculations updated with SWEP plate area and Dow viscosity data, plus a second exchanger correlation as a cross-check.
- A dynamic simulation of the whole unit, used to tune the control loops. It predicts the results of 13 test cases.
- A reference controller in Python with 18 logic tests, all passing.
- A complete PLC program in Structured Text.
- A 3D layout model with automated checks for fit, clashes, service access, wet/dry segregation, drip-tray capacity and tipping, all passing. It comes with an interactive viewer and a three-view drawing.
- The electrical design: I/O list, load schedule, power distribution, panel and network.
- Purchase specifications ready to send to suppliers.

**Not done, and cannot be done from a desk:** nothing has been bought, built, compiled on a PLC, pressure-tested or run. The 10 kW figure and every simulated number are predictions, not measurements. Nine confirmations stand between this package and a purchase order. They are in [07-hold-points.md](07-hold-points.md), each with a fallback already chosen.

## Contents

| File | What it holds |
|---|---|
| [01-decisions.md](01-decisions.md) | All 32 decisions, with reasons and rejected options |
| [02-design-basis.md](02-design-basis.md) | Site conditions, interfaces, requirements |
| [03-calculations.md](03-calculations.md) | Steady-state sizing |
| [04-pid.svg](04-pid.svg), [04-pid-and-equipment.md](04-pid-and-equipment.md) | P&ID, equipment, valve and instrument lists, packaging |
| [05-controls-and-safety.md](05-controls-and-safety.md) | Control loops and tuning, alarms and trips, failure analysis |
| [06-bom-and-cost.md](06-bom-and-cost.md) | Bill of materials and cost |
| [07-hold-points.md](07-hold-points.md) | Confirmations needed before purchase |
| [08-test-plan.md](08-test-plan.md) | Factory, thermal, fault, endurance and site tests, with simulated predictions |
| [09-electrical.md](09-electrical.md) | Electrical design |
| [10-purchase-specs.md](10-purchase-specs.md) | Nine requests for quotation |
| [sim/results.md](sim/results.md) | Simulation results and charts for 13 scenarios |
| [cad/](cad/) | Layout model (`.obj`), drawing (`cdu10_views.svg`), 3D viewer (`viewer.html`), checks (`layout_checks.md`) |
| [plc/](plc/) | PLC program and Modbus map |
| [calc/](calc/) | All scripts: sizing, controller, simulation, tests, P&ID generator |

## Reproducing the results

Python 3 and numpy only; no other packages.

```
cd calc
python3 cdu_calc.py > results.txt     # steady-state sizing
python3 test_control.py               # 18 controller logic tests
python3 cdu_sim.py                    # 13 simulations -> ../sim/
python3 make_pid.py                   # P&ID -> ../04-pid.svg
cd ../cad && python3 make_layout.py   # layout model, drawing, viewer, checks
```

## What Rev B changed, and why

| Finding | Found by | Change |
|---|---|---|
| The 43 °C trip was above the 40 °C limit of the servers designed for | Review while building the simulation | Trip = server limit − 2 K, set on the HMI |
| Losing facility water at 10 kW let supply reach 41.4 °C after the trip | Simulation | Facility-loss trip after 20 s; peak now 37.4 °C. A 15 s interruption rides through. |
| The low-pressure warning sat below the tank precharge, so it could not warn until the tank was empty | Simulation | Coolant inventory monitoring: warning at 0.31 L lost, trip at 0.64 L |
| Cold start overshot to 37.6 °C, near the trip | Simulation | Setpoint-based feedforward and conditional-integration anti-windup; peak 32.6 °C |
| Valve travelled about 650 % of stroke per hour on sensor noise | Simulation | Error and output deadbands, filtered feedforward: under 6 %/h |
| 1000 mm cabinet could not hold the exchanger and a separate panel | Layout model | 1200 mm cabinet |
| Isolation valves at the rear would be out of reach | Layout model | Front valve bank |
| Three clashes and a blocked lever swing | Layout checks | Parts moved; all checks pass |
| Pump pressure control measured across the flow meter | Simulation set-up | PT-103 moved after the meter |

## Sources for published figures

- Server limits: [Supermicro FAQ](https://www.supermicro.com/en/support/faqs/faq.php?faq=44120) (12 L/min, 40 °C); [QCT GB200 NVL72 document](https://blog.qct.io/wp-content/uploads/2025/04/QCT-Qoolrack-Stand-Alone_Advanced-Liquid-Cooling-for-NVIDIA-GB200-NVL72-Systems.pdf) (45 °C inlet).
- Pump rated point: [Grundfos CME 1-3 datasheet](https://www.anglianpumping.com/app/uploads/2023/03/98394758_CME1-3_A-R-G-E-AQQE.pdf), read from a search summary; the file could not be opened from the design environment.
- Exchanger: [SWEP B10T sheet](https://pdf.directindustry.com/pdf/swep-international/b10t/111139-832691.html); B25T areas from SWEP specification sheets ([B25THx20](https://cdn.shopify.com/s/files/1/0610/4108/2554/files/B25THx20_517685.pdf), [B25T](https://cdn.shopify.com/s/files/1/0610/4108/2554/files/B25T_638520795380159853_2.pdf)).
- PG25 properties: [CAPLINQ DOWFROST LC 25 listing](https://www.caplinq.com/dowfrost-lc-25-heat-transfer-liquid-for-technology-cooling-systems-tcs-ds-lc25.html); [Chempoint listing](https://www.chempoint.com/en-ca/products/dow/dowfrost-glycol-thermal-fluids/dowfrost-propylene-glycol-thermal-fluids/dowfrost-lc-25).
- Flow meter: [ifm SM7000](https://ifm.com/us/en/product/SM7000); [RS listing](https://benl.rs-online.com/web/p/flow-sensors/7406424).
- Control valve: [Belimo B2 series data](https://www.meiersupply.com/customer/docs/skudocs/Document_Links/Vendors/Belimo/B2/Technical%20Data/B2_LRB_X_24_SR.pdf).
- Climate: [ASHRAE-derived city table](https://fgiaonline.org/wp-content/uploads/2025/02/ASHRAE-Temperatures-for-Major-US-Cities.pdf); [ASHRAE-based design conditions summary](https://hvaclogic.org/ashrae-climatic-data).
- Site context: [DCD on the Prometheus campus](https://datacenterdynamics.com/en/news/meta-details-ohio-prometheus-data-center-campus-with-first-phase-live); [Meta Hot Chips 2025 rack tutorial](https://hc2025.hotchips.org/assets/program/tutorials/HC2025.T1DCRacks.S6.Arnold_Bowman.pdf).
- Correlations: Martin (1996) chevron-plate model; Kumar (1984) constants as tabulated in Kakaç and Liu, used only as a cross-check.
