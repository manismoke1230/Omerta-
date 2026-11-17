# CDU-10: 10 kW liquid-to-liquid coolant distribution unit

**Detailed design package, Rev C — 17 November 2026**

This folder carries the feasibility report's open questions through to a detailed design. Every engineering decision is made and recorded with its reason. It is a self-contained package, unrelated to the rest of this repository.

## What CDU-10 is

A free-standing, front-serviced unit that cools up to 10 kW of liquid-cooled servers or compute trays in a supervised hardware test bay. The reference site is a hyperscale AI campus in New Albany, Ohio. Heat passes from a PG25 server loop into the building's facility water through a brazed plate heat exchanger.

| | |
|---|---|
| Rated duty | 10 kW |
| Server loop | PG25, 29–30 L/min, 32 °C supply, about 37 °C return |
| Facility water | 27 °C supply (holds 32 °C up to 29.5 °C water), up to 24 L/min, 50 kPa minimum available |
| Heat exchanger | SWEP B25T × 40, 2.5 K fouled approach at rating (calibrated to SWEP's software) |
| Pump | Grundfos CME 1-2, 0.55 kW single-phase, 95 % speed cap |
| Pressure available to the servers | 108 kPa at 30 L/min with a dirty filter; controlled at 70 kPa by default |
| Supply stability (simulated) | ±0.15 K ripple; 0.7 K overshoot on a 2 → 10 kW step |
| Envelope | 600 W × 800 D × 1200 H mm, about 149 kg filled |
| Power | 208–240 V single-phase, about 345 W running, 780 W maximum |
| Parts cost | about US$28,500 including a spare pump (my estimate, ±40 %) |
| Prototype total | about US$66,500 (range $50,000–80,000), excluding design hours |

## Status

| Revision | Content |
|---|---|
| Rev A | Decisions, design basis, sizing, P&ID, controls concept, failure analysis, cost, test plan |
| Rev B | Dynamic simulation and control tuning; reference controller with 18 logic tests; PLC program; 3D layout model with automated checks; electrical design; purchase specifications |
| **Rev C (this issue)** | Assumptions replaced with published data now that the design environment can reach vendor and code sites (details below) |

**Not done, and cannot be done from a desk:** nothing has been bought, built, compiled on a PLC, pressure-tested or run. Every simulated number is a prediction. Seven confirmations remain open, two are closed or decided. They are in [07-hold-points.md](07-hold-points.md), each with a fallback.

## What Rev C changed, and why

| Finding | Source | Change |
|---|---|---|
| The CME 1-3's shut-off head is 39.6 m, not the assumed 31 m. At the 85 % cap it would dead-head at the relief setting, and capped lower it cannot deliver 100 kPa | Grundfos product datasheet curve | **Pump changed to CME 1-2**: 108 kPa to the servers with a dirty filter, 3.48 bar g dead-head at a 95 % cap |
| My exchanger model under-predicted pressure drop by more than half (unsafe) and heat transfer by 27 % (conservative) | Published SWEP SSP rating for a B25THx50 | **Model calibrated** to within 2 %; **40 plates** instead of 30, to keep pressure drop under 15 kPa per side |
| Ohio law defines a pressure vessel as any container under pressure; no exemption fits this unit | ORC 4104.01, 4104.04; OAC 4101:4-4-01 | **Expansion tank ASME VIII stamped** |
| Design dew point confirmed; summer cooling-tower water may reach about 28–30 °C | ASHRAE 2021, Columbus John Glenn | Design range confirmed; site climate hold point closed |
| Magnetic flow meters need at least 20 µS/cm | ifm product data | Coolant conductivity now a purchase requirement; ultrasonic fallback |
| Wire-to-water efficiency is 27 %, not 35 % | Grundfos power curves | Pump heat and electrical load updated |
| 3D viewer verified loading three.js from the CDN | Browser test | — |

All 18 logic tests and all 8 layout checks still pass, and every simulation was rerun. Control performance improved slightly with the larger exchanger.

## Contents

| File | What it holds |
|---|---|
| [01-decisions.md](01-decisions.md) | All 34 decisions, with reasons and rejected options |
| [02-design-basis.md](02-design-basis.md) | Site conditions (ASHRAE data), interfaces, codes |
| [03-calculations.md](03-calculations.md) | Steady-state sizing, exchanger calibration, pump selection |
| [04-pid.svg](04-pid.svg), [04-pid-and-equipment.md](04-pid-and-equipment.md) | P&ID, equipment, valve and instrument lists, packaging |
| [05-controls-and-safety.md](05-controls-and-safety.md) | Control loops and tuning, alarms and trips, failure analysis |
| [06-bom-and-cost.md](06-bom-and-cost.md) | Bill of materials and cost |
| [07-hold-points.md](07-hold-points.md) | Confirmations needed before purchase |
| [08-test-plan.md](08-test-plan.md) | Factory, thermal, fault, endurance and site tests, with simulated predictions |
| [09-electrical.md](09-electrical.md) | Electrical design |
| [10-purchase-specs.md](10-purchase-specs.md) | Nine requests for quotation |
| [sim/results.md](sim/results.md) | Simulation results and charts for 13 scenarios |
| [visuals/](visuals/) | Realistic 3D scene of the unit in a test bay (`cdu10-scene.html`, open in a browser) and five rendered views |
| [cad/](cad/) | Layout model (`.obj`), drawing (`cdu10_views.svg`), 3D viewer (`viewer.html`), checks (`layout_checks.md`) |
| [plc/](plc/) | PLC program and Modbus map |
| [calc/](calc/) | All scripts: sizing, controller, simulation, tests, P&ID generator |

## Reproducing the results

Python 3 and numpy only.

```
cd calc
python3 cdu_calc.py > results.txt     # steady-state sizing, calibration, pump selection
python3 test_control.py               # 18 controller logic tests
python3 cdu_sim.py                    # 13 simulations -> ../sim/
python3 make_pid.py                   # P&ID -> ../04-pid.svg
cd ../cad && python3 make_layout.py   # layout model, drawing, viewer, checks
```

## Sources

- Pump: [Grundfos CME 1-3 product datasheet 98394758](https://www.anglianpumping.com/app/uploads/2023/03/98394758_CME1-3_A-R-G-E-AQQE.pdf) (curve, motor, materials, weight); [Grundfos CM, CME data booklet](https://portals.grundfos.com/content/dam/portals/extranet-landing/gpk/CM,%20CME(Data%20booklet)%20201216.pdf) (CME 1 curves p. 66, dimensions p. 103, weights pp. 122–124).
- Exchanger: [SWEP SSP rating, B25THx50](https://cdn.shopify.com/s/files/1/0610/4108/2554/files/B25T_638520795380159853_2.pdf) (calibration case); [B25THx20 sheet](https://cdn.shopify.com/s/files/1/0610/4108/2554/files/B25THx20_517685.pdf); [SWEP B10T sheet](https://pdf.directindustry.com/pdf/swep-international/b10t/111139-832691.html).
- Climate: [ASHRAE climatic design conditions, Columbus John Glenn, WMO 724280](https://ashrae-meteo.info/v3.0/index.php?lat=39.99&lng=-82.88&place=%27%27&wmo=724280&ashrae_version=2021).
- Ohio law: [ORC 4104.01](https://codes.ohio.gov/ohio-revised-code/section-4104.01), [ORC 4104.04](https://codes.ohio.gov/ohio-revised-code/section-4104.04), [OAC 4101:4-1-01](https://codes.ohio.gov/assets/laws/administrative-code/authenticated/4101/4/1/4101$4-1-01_20240701.pdf), [OAC chapter 4101:4-4](https://codes.ohio.gov/ohio-administrative-code/chapter-4101:4-4), [OAC 4101:2-10-01](https://codes.ohio.gov/assets/laws/administrative-code/rules/4101/2/4101$2-10-01_eff_11_1_17.pdf).
- Server limits: [Supermicro FAQ](https://www.supermicro.com/en/support/faqs/faq.php?faq=44120) (12 L/min, 40 °C); [QCT GB200 NVL72 document](https://blog.qct.io/wp-content/uploads/2025/04/QCT-Qoolrack-Stand-Alone_Advanced-Liquid-Cooling-for-NVIDIA-GB200-NVL72-Systems.pdf) (45 °C inlet).
- PG25 properties: [CAPLINQ DOWFROST LC 25 listing](https://www.caplinq.com/dowfrost-lc-25-heat-transfer-liquid-for-technology-cooling-systems-tcs-ds-lc25.html); [Chempoint listing](https://www.chempoint.com/en-ca/products/dow/dowfrost-glycol-thermal-fluids/dowfrost-propylene-glycol-thermal-fluids/dowfrost-lc-25).
- Flow meter: [ifm SM7000](https://ifm.com/us/en/product/SM7000); [ifm flow sensor brochure](https://media.ifm.com/CIP/mediadelivery/asset/06b646ba78515a429a44861cd5ed319e/Brochure_flow-sensors_ENGB_012025_low.pdf) (20 µS/cm minimum).
- Control valve: [Belimo B2 series data](https://www.meiersupply.com/customer/docs/skudocs/Document_Links/Vendors/Belimo/B2/Technical%20Data/B2_LRB_X_24_SR.pdf).
- Site context: [DCD on the Prometheus campus](https://datacenterdynamics.com/en/news/meta-details-ohio-prometheus-data-center-campus-with-first-phase-live); [Meta Hot Chips 2025 rack tutorial](https://hc2025.hotchips.org/assets/program/tutorials/HC2025.T1DCRacks.S6.Arnold_Bowman.pdf).
- Correlations: Martin (1996) chevron-plate model, calibrated to SWEP; Kumar (1984) constants as tabulated in Kakaç and Liu, used as an uncalibrated cross-check.
