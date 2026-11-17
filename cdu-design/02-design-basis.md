# 02 — Design basis and interfaces (Rev C)

## Site: New Albany, Ohio (reference)

| Item | Value | Source and status |
|---|---|---|
| ASHRAE station | Columbus John Glenn, WMO 724280, elevation 249 m, ASHRAE 2021 (data period 1994–2019) | ashrae-meteo.info |
| Winter design dry-bulb (99.6 %) | −15.3 °C; extreme annual mean minimum −18.3 °C | ASHRAE 2021 |
| Summer design dry-bulb (0.4 %) | 32.8 °C with mean coincident wet-bulb 23.0 °C; extreme annual mean maximum 34.6 °C | ASHRAE 2021 |
| Evaporation wet-bulb (0.4 %) | 24.7 °C, which sets the warmest cooling-tower water (about 28–30 °C supply) | ASHRAE 2021 |
| Dehumidification dew point (0.4 %) | 23.1 °C, humidity ratio 18.4 g/kg | ASHRAE 2021 |
| Design room dew point | **23 °C** | Confirmed by the ASHRAE 0.4 % value; used for all condensation checks |
| Campus cooling | Mix of liquid-to-air sidecars in older buildings and facility-water CDUs in newer ones | Public reporting on Meta's Prometheus campus |
| Building type | May be a conventional hall, a modular unit or a tent structure | Public reporting |

Central Ohio is humid in summer and well below freezing in winter. The design therefore runs the server loop warm, insulates the facility branch, and keeps all wetted parts inside conditioned space.

## Server-side interface (TCS)

| Parameter | Design value | Basis |
|---|---|---|
| Heat load | 0–10 kW continuous, 12 kW short-term | D-03 |
| Coolant | Inhibited PG25 | D-04 |
| Flow | 3–30 L/min | Two servers at 12 L/min minimum each, or GB200-class trays at about 1.5 L/min per kW |
| Supply temperature | 32 °C default, adjustable 25–40 °C | Supermicro publishes a 40 °C maximum inlet; a QCT document gives 45 °C for GB200 NVL72 |
| Supply stability | ±0.5 K steady state; under 2 K on a 2 → 10 kW step | Simulated: 0.14 K ripple, 0.93 K step overshoot |
| Pressure available | 100 kPa at 30 L/min | D-06 |
| Static pressure | 1.0 bar g cold, about 1.1 bar g warm | Calculated |
| Maximum pressure the servers can see | 3.4 bar g (pump dead-headed), 4.0 bar g (relief) | Calculated |
| High-temperature trip | Server maximum inlet − 2 K (38 °C for 40 °C servers), entered on the HMI | Rev B correction |
| Filtration | 50 µm full flow | D-14 |
| Connection | 1" sanitary clamp, hose kit to bay manifold | D-20 |

## Facility-side interface (FWS)

| Parameter | Design value | Basis |
|---|---|---|
| Fluid | Treated water | Assumed; chemistry to be confirmed (HP-05) |
| Supply temperature | 18–32 °C; rating at 27 °C | ASHRAE W32 class |
| Flow | 24 L/min at rating; valve throttles to about 2 L/min at light load | Calculated |
| Pressure difference needed | 37 kPa at 24 L/min; specify 50 kPa minimum | Calculated plus margin |
| Design pressure | 10 bar g | Assumed; thermal relief set to the site's figure (HP-05) |
| Return temperature | Up to about 36 °C | Calculated |
| Connection | 1" with isolation valves and unions | — |

## Room and utilities

| Item | Requirement |
|---|---|
| Room | 15–35 °C, non-condensing, dew point up to 23 °C |
| Heat released to room | Under 300 W from the pump motor, drive and controls |
| Power | 208–240 V single-phase 60 Hz, about 1.1 kW maximum, through a C20 inlet (see [09-electrical.md](09-electrical.md)) |
| Network | One Ethernet port for Modbus TCP, read-only by default |
| Hardwired signals | "Server load permit" relay contact out; remote stop in |
| **Load shedding** | **When the permit opens, server load must fall below 20 % within 10 s** (hold point HP-09) |
| Drain | Not required. Relief and drain discharge to the internal tray. |
| Service clearance | 900 mm in front; none needed at sides or rear after installation |
| Footprint and mass | 600 × 800 mm, 1200 mm high; about 149 kg filled |

## Applicable codes and approvals

| Area | Requirement | Action |
|---|---|---|
| Electrical | NEC (NFPA 70); UL 508A panel; NRTL field evaluation | Built into D-22 and the cost estimate |
| Mechanical | Ohio Mechanical Code for the facility tie-in | Site contractor pulls the permit |
| Pressure | Ohio boiler and pressure vessel law covers any pressure vessel (ORC 4104.01(G)); no exemption fits this unit (ORC 4104.04); new vessels to the referenced standard (OAC 4101:4-4-01) | Expansion tank ASME VIII stamped (D-33). Confirm registration and inspection with the Ohio Division of Industrial Compliance (HP-07). |
| Piping | ASME B31.9 practice for the facility branch | Applied in the test plan |
| Owner | Site design standards, approved coolant list, controls network rules | Site owner review at design review |

## Rating statement

Capacity is to be quoted only in this form, and only after test TT-1 in [08-test-plan.md](08-test-plan.md):

> 10 kW at 30 L/min PG25 with 32 °C supply, facility water 27 °C at 24 L/min, measured heat balance within ±5 %.
