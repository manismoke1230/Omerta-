# 07 — Hold points (Rev B)

These are confirmations from vendors or the site, not open decisions. Each has a default the design already uses and a fallback already chosen, so none of them stops work. The requests that close the vendor items are written in [10-purchase-specs.md](10-purchase-specs.md).

| # | Confirm | With whom | Design assumes | If the answer differs | Rev B status |
|---|---|---|---|---|---|
| HP-01 | Server limits: minimum flow, maximum inlet temperature, maximum loop pressure, pressure drop, approved coolant, quick-disconnect type | Server manufacturer | 13 L/min at 70 kPa per 4U server (12 L/min minimum), 40 °C inlet limit, loop good to 4 bar g | Enter the limit on the HMI; the trip follows it (limit − 2 K). Lower the relief setting and speed cap if the loop is rated under 4 bar g. | Open |
| HP-02 | Pump curve, shut-off head, motor power, supply, leakage current | Grundfos (RFQ-01) | 31 m shut-off; 15.2 m at 1.8 m³/h at 78 % speed; single-phase | Reset the speed cap so dead-head pressure stays at or under 3.4 bar g; CME 1-4 if head is short; three-phase model with a phase-converting drive if single-phase is not offered | Open. Datasheet download blocked from the design environment. |
| HP-03 | Exchanger rating at the design point with 20 % fouling | SWEP or Alfa Laval (RFQ-02) | B25T × 30, 82 % clean margin by Martin, 129 % by Kumar | Accept the vendor's plate count for the same duty; the layout has room for up to 60 plates | **Narrowed:** area per plate now taken from SWEP's own sheets (0.062 m²). Thermal rating still needed. |
| HP-04 | Flow meter and filter pressure drop; meter suitability for PG25 conductivity | ifm, filter supplier (RFQ-03, -04) | 10 kPa meter, 30 kPa dirty filter | One size larger meter or filter housing | Open |
| HP-05 | Facility water: temperature range through the year, available dP, design pressure, chemistry | Site facilities | 18–32 °C, at least 50 kPa, 10 bar g, treated water | Under 50 kPa: Cv 7.4 valve. Copper-aggressive chemistry: all-stainless exchanger. Above 28 °C at full load: supply rises above 32 °C (see 03, section 3). No facility water: use a liquid-to-air unit instead. | Open |
| HP-06 | Climate data for the nearest ASHRAE station | ASHRAE climatic data | 23 °C design dew point | None needed for control (it tracks measured dew point); update insulation and room checks | Partly open. A city table gives about 89 °F (31.7 °C) dry-bulb with 73 °F wet-bulb for Columbus, but its column labels could not be confirmed; ASHRAE station data was blocked. |
| HP-07 | Whether the expansion tank or the assembly needs Ohio registration or inspection | Ohio Division of Industrial Compliance; NRTL | Tank exempt by size and pressure; field evaluation covers the electrics | Buy the ASME-stamped tank option (quoted in RFQ-05) | Open. ORC 4104.04 holds the exemptions; the statute site was blocked from the design environment. |
| HP-08 | PLC program compiles and passes the 18 logic cases on the selected controller | Panel builder | Program as written in `plc/` | Correct and re-test; reference model is the arbiter | **New.** No PLC toolchain in the design environment. |
| HP-09 | Bay sheds server load to under 20 % within 10 s of the permit opening | Site and server owner | 1 s delay and 1.5 s decay, as simulated | If slower: set the facility-loss trip earlier (10 s) and the temperature trip at server limit − 3 K, then re-simulate | **New.** Found by simulation. |

## Gates

| Gate | Passes when |
|---|---|
| Release long-lead orders (pump, exchanger) | HP-01, HP-02, HP-03 answered |
| Release remaining orders | HP-04 and HP-05 answered; design review with site facilities and the server owner |
| Ship to site | Factory tests in [08-test-plan.md](08-test-plan.md) passed, including HP-08 (test CT-13); HP-07 answered |
| Connect servers | Site tests passed; field-evaluation label applied; HP-09 demonstrated in test ST-5; server owner signs |
