# CDU-10: 10 kW liquid-to-liquid coolant distribution unit

**Preliminary design package, Rev A — 17 November 2026**

This folder takes the feasibility report's open questions, makes every engineering decision needed to get to a buildable design, and records the reasoning. It is a self-contained package and is unrelated to the rest of this repository.

## What CDU-10 is

A free-standing, front-serviced unit that cools up to 10 kW of liquid-cooled servers or compute trays in a supervised hardware test bay. The reference site is a hyperscale AI campus in New Albany, Ohio. It moves heat from a PG25 server loop into the building's facility water through a brazed plate heat exchanger.

| | |
|---|---|
| Rated duty | 10 kW |
| Server loop (TCS) | PG25, 30 L/min, 32 °C supply, 37 °C return |
| Facility water (FWS) | 27 °C supply, 24 L/min, about 37 kPa needed |
| Rated approach | 5 K (predicted 3.7 K with a fouled exchanger) |
| Pressure available to the servers | 100 kPa at 30 L/min |
| Facility water range | 18–32 °C (ASHRAE W32 class) |
| Envelope | 600 W × 800 D × 1000 H mm, about 105 kg filled |
| Power | 208–240 V single-phase, under 1 kW |
| Parts cost | about US$24,000 (my estimate, ±40 %) |
| Prototype total | about US$50,000–75,000 excluding design hours |

## Status

**Done on paper:** decisions, design basis, sizing calculations, P&ID, equipment and instrument list, control and safety design, failure analysis, cost estimate, and the test plan with acceptance criteria.

**Not done, and cannot be done from a desk:** nothing has been bought, built, pressure-tested or run. The 10 kW figure is a calculated design point, not a tested rating. Seven vendor and site confirmations stand between this package and a purchase order; they are listed in [07-hold-points.md](07-hold-points.md) with the fallback I have already chosen for each.

## Contents

| File | What it holds |
|---|---|
| [01-decisions.md](01-decisions.md) | Every decision, with the reason and what was rejected |
| [02-design-basis.md](02-design-basis.md) | Site conditions, interfaces, requirements |
| [03-calculations.md](03-calculations.md) | Sizing results and method |
| [04-pid.svg](04-pid.svg) | Simplified P&ID |
| [04-pid-and-equipment.md](04-pid-and-equipment.md) | Equipment, valve and instrument list, packaging |
| [05-controls-and-safety.md](05-controls-and-safety.md) | Control loops, alarms, interlocks, failure analysis |
| [06-bom-and-cost.md](06-bom-and-cost.md) | Bill of materials and cost estimate |
| [07-hold-points.md](07-hold-points.md) | Confirmations needed before purchase, with fallbacks |
| [08-test-plan.md](08-test-plan.md) | Factory, thermal, fault and endurance tests |
| [calc/cdu_calc.py](calc/cdu_calc.py) | Calculation script (`python3 cdu_calc.py`, no dependencies) |
| [calc/results.txt](calc/results.txt) | Script output used throughout this package |

## The three findings that shaped the design

1. **The short plate exchanger does not work.** A SWEP B10T-class unit with 40 plates gives only 1 % margin at a 5 K approach. A long-plate unit (B25T class, 30 plates) gives 75 % clean margin at modest extra cost.
2. **The pump must be speed-capped.** A pump with enough head for a dirty filter and 100 kPa of server resistance can exceed the 4.0 bar relief setting if dead-headed at full speed. Capping the drive at 85 % keeps the worst case at 3.4 bar g.
3. **Loss of facility water gives about 90 seconds.** At 10 kW the loop warms about 5 K per minute, so it goes from 32 °C to 40 °C in roughly a minute and a half. The trip that sheds server load is therefore hardwired, not left to software or an operator.

## Sources for published figures

- Server limits: [Supermicro FAQ](https://www.supermicro.com/en/support/faqs/faq.php?faq=44120) (12 L/min, 40 °C); [QCT GB200 NVL72 document](https://blog.qct.io/wp-content/uploads/2025/04/QCT-Qoolrack-Stand-Alone_Advanced-Liquid-Cooling-for-NVIDIA-GB200-NVL72-Systems.pdf) (45 °C inlet). Other GB200 figures found online disagree with each other and were not used.
- Pump rated point: [Grundfos CME 1-3 datasheet](https://www.anglianpumping.com/app/uploads/2023/03/98394758_CME1-3_A-R-G-E-AQQE.pdf), read from a search summary only; the file itself could not be opened from this environment.
- Short-plate exchanger dimensions: [SWEP B10T product sheet](https://pdf.directindustry.com/pdf/swep-international/b10t/111139-832691.html).
- Flow meter accuracy and price: [ifm SM7000](https://ifm.com/us/en/product/SM7000); [RS listing](https://benl.rs-online.com/web/p/flow-sensors/7406424).
- Control valve: [Belimo B2 series data](https://www.meiersupply.com/customer/docs/skudocs/Document_Links/Vendors/Belimo/B2/Technical%20Data/B2_LRB_X_24_SR.pdf).
- Winter design temperature: [ASHRAE-derived city table](https://fgiaonline.org/wp-content/uploads/2025/02/ASHRAE-Temperatures-for-Major-US-Cities.pdf).
- Site context: [DCD on the Prometheus campus](https://datacenterdynamics.com/en/news/meta-details-ohio-prometheus-data-center-campus-with-first-phase-live); [Meta Hot Chips 2025 rack tutorial](https://hc2025.hotchips.org/assets/program/tutorials/HC2025.T1DCRacks.S6.Arnold_Bowman.pdf).
- Fluid properties and the original scope: the feasibility report this package follows.
