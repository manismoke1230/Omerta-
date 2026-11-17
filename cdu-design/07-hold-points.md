# 07 — Hold points

These are confirmations from vendors or the site, not open decisions. Each has a default the design already uses and a fallback I have already chosen, so none of them stops work.

| # | Confirm | With whom | Design assumes | If the answer differs |
|---|---|---|---|---|
| HP-01 | Server or tray limits: minimum flow, maximum inlet temperature, maximum loop pressure, pressure drop at rated flow, approved coolant | Server manufacturer | 12 L/min per 4U server, 40 °C inlet limit, loop good for at least 4 bar g, under 100 kPa drop | Lower the relief setting and speed cap to suit; the pump has speed in hand. Change the trip temperature to 2 K under the stated limit. |
| HP-02 | Pump curve, shut-off head, motor power and supply voltage for the exact CME 1-3 model | Grundfos | 31 m shut-off head; 15.1 m at 1.8 m³/h reached at 78 % speed; single-phase 208–240 V | Recalculate the speed cap so dead-head pressure stays at or under 3.4 bar g. If single-phase is not offered, use a three-phase model. If head is short, use CME 1-4. |
| HP-03 | Exchanger thermal rating at the design point, with 20 % fouling allowance and under 15 kPa drop per side | SWEP or Alfa Laval, using their rating software | B25T-class plate, 30 plates, 75 % clean margin by my calculation | Accept the vendor's plate count for the same duty. The cabinet has room for a unit up to 60 plates. |
| HP-04 | Flow meter and filter pressure drop at 30 L/min in PG25; meter suitability for the coolant's conductivity | ifm; filter vendor | 10 kPa meter, 30 kPa dirty filter | Move up one meter size (SM8000 class) or one filter housing size. |
| HP-05 | Facility water: temperature range through the year, available pressure difference, design pressure, chemistry | Site facilities | 18–32 °C, at least 50 kPa, 10 bar g, treated water | If under 50 kPa: fit a control valve with Cv 7.4. If chemistry is aggressive to copper: use an all-stainless fusion-bonded exchanger. If there is no facility water: this design does not apply and a liquid-to-air unit is used. |
| HP-06 | Climate figures for the station nearest the site | ASHRAE climatic data | 23 °C design dew point | Adjust the dew-point floor; the control logic already tracks measured dew point. |
| HP-07 | Whether the expansion tank and the assembled unit need registration or inspection | Ohio Division of Industrial Compliance; NRTL | Tank is exempt by size and pressure; field evaluation covers the electrical build | Buy an ASME-stamped tank, about $300 more. |

## Gates

| Gate | Passes when |
|---|---|
| Release long-lead orders | HP-01, HP-02 and HP-03 answered |
| Release remaining orders | HP-04 and HP-05 answered; design review held with site facilities and the server owner |
| Ship to site | Factory tests in [08-test-plan.md](08-test-plan.md) passed; HP-07 answered |
| Connect servers | Site tests passed; field evaluation label applied; server owner signs |
