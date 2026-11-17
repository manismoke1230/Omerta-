# 07 — Hold points (Rev C)

These are confirmations from vendors or the site, not open decisions. Each has a default the design already uses and a fallback already chosen. The requests that close the vendor items are in [10-purchase-specs.md](10-purchase-specs.md).

| # | Confirm | With whom | Design assumes | If the answer differs | Rev C status |
|---|---|---|---|---|---|
| HP-01 | Server limits: minimum flow, maximum inlet temperature, maximum loop pressure, pressure drop, approved coolant, quick-disconnect type | Server manufacturer | 13 L/min at 70 kPa per 4U server (12 L/min minimum), 40 °C inlet limit, loop good to 4 bar g | Enter the limit on the HMI; the trip follows it (limit − 2 K). Lower the relief setting and speed cap if the loop is rated under 4 bar g. | Open |
| HP-02 | Pump curve and electrical data | Grundfos (RFQ-01) | Published CME 1-2 curve, 25.6 − 1.55Q − 1.24Q²; 0.55 kW, 1 × 200–240 V 50/60 Hz, 3.45 A | Recalculate the speed cap so dead-head stays at or under 3.5 bar g | **Mostly closed.** Curves from the Grundfos CM/CME data booklet and the CME 1-3 product datasheet; dimensions and weights from the booklet. Remaining: US product number, price, and confirmation of the curve read from the chart (±0.5 m). |
| HP-03 | Exchanger rating at the design point with 20 % fouling | SWEP or Alfa Laval (RFQ-02) | B25T × 40; 188 % clean margin; 11.2 / 5.2 kPa | Accept the vendor's plate count if pressure drop is under 15 kPa per side; the layout has room for up to 60 plates | **Narrowed.** Model now calibrated to a published SWEP SSP rating (within 2 % on coefficient and pressure drop). A vendor rating at our fluids and duty is still needed. |
| HP-04 | Flow meter and filter pressure drop; **coolant conductivity at least 20 µS/cm** (magnetic meter minimum) | ifm, filter supplier, coolant supplier (RFQ-03, -04) | 10 kPa meter, 30 kPa dirty filter; inhibited PG25 well above 20 µS/cm | Pressure drop: one size larger meter or filter housing (the pump has 8 kPa in hand at the cap). Conductivity under 20 µS/cm: ultrasonic meters (ifm SU7000 class) instead. | Narrowed. SM7000: 16 bar, −10 to 70 °C fluid; ifm states 20 µS/cm minimum for the SM series. Pressure-loss curve not obtained (ifm downloads blocked to automated requests). |
| HP-05 | Facility water: temperature range through the year, available dP, design pressure, chemistry | Site facilities | 18–32 °C, at least 50 kPa, 10 bar g, treated water | Under 50 kPa: Cv 7.4 valve. Copper-aggressive chemistry: all-stainless exchanger. Above 29.5 °C at full load: supply rises above 32 °C (still under the trip up to 32 °C water). | Open. ASHRAE data now shows cooling-tower water could reach about 28–30 °C in a Columbus summer, which is inside the design range. |
| HP-06 | Climate data | ASHRAE | 23 °C design dew point | — | **Closed.** ASHRAE 2021, Columbus John Glenn (WMO 724280): 0.4 % dew point 23.1 °C; 0.4 % dry-bulb 32.8 °C; 0.4 % evaporation wet-bulb 24.7 °C; 99.6 % heating −15.3 °C. |
| HP-07 | Ohio registration and inspection of the expansion tank and the assembly | Ohio Division of Industrial Compliance; NRTL | ASME VIII stamped tank (D-33); field evaluation covers the electrics | If the state requires an installation certificate or periodic inspection, add it to the site commissioning and maintenance schedule | **Decided.** The statute and rules give no exemption for this case, so the tank is specified ASME-stamped. Only the administrative registration question remains. |
| HP-08 | PLC program compiles and passes the 18 logic cases on the selected controller | Panel builder | Program as written in `plc/` | Correct and re-test; the reference model is the arbiter | Open (no PLC toolchain in the design environment) |
| HP-09 | Bay sheds server load to under 20 % within 10 s of the permit opening | Site and server owner | 1 s delay and 1.5 s decay, as simulated | If slower: facility-loss trip at 10 s and temperature trip at server limit − 3 K, then re-simulate | Open |

## Gates

| Gate | Passes when |
|---|---|
| Release long-lead orders (pump, exchanger) | HP-01 answered; HP-02 and HP-03 vendor confirmations received |
| Release remaining orders | HP-04 and HP-05 answered; design review with site facilities and the server owner |
| Ship to site | Factory tests in [08-test-plan.md](08-test-plan.md) passed, including CT-13 (HP-08); HP-07 registration settled |
| Connect servers | Site tests passed; field-evaluation label applied; HP-09 shown in test ST-5; server owner signs |
