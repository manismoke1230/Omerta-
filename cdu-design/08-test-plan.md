# 08 — Test and commissioning plan

No test here has been run. Each has a pass criterion taken from the calculations so the result is unambiguous.

## Stage 1 — Cold tests at the factory

| ID | Test | Method | Pass |
|---|---|---|---|
| CT-1 | Inspection | Check build against the P&ID, tag list and materials list | No deviations open |
| CT-2 | Flush | Circulate clean water through a 25 µm temporary filter until it stays clean; drain fully | Filter clean after 30 minutes |
| CT-3 | Pressure test, server loop | Hydrostatic at 6.0 bar g for 30 minutes with tank and relief isolated | No visible leak; pressure loss under 0.1 bar |
| CT-4 | Pressure test, facility side | Hydrostatic at 1.5 × facility design pressure for 30 minutes | Same |
| CT-5 | Relief valve | Raise pressure slowly with a hand pump | Opens at 4.0 bar g ± 3 %; reseats above 3.6 bar g |
| CT-6 | Fill and vent | Fill with PG25 through the low-point coupling; run fill-and-vent mode | Stable flow reading within 15 minutes; static 1.0 bar g |
| CT-7 | Instrument check | Compare all four Pt100s in a stirred bath at 25 °C and 40 °C; check pressure transmitters against a reference gauge | Matched pairs within 0.1 K; pressures within 0.5 % of range |
| CT-8 | Pump and system curve | With a throttle valve standing in for the servers, record flow, pressures and speed at 10 points | 30 L/min at 100 kPa external reached at or under 85 % speed |
| CT-9 | Dead-head pressure | Close V-102 with bypass closed, pump at speed cap | Discharge pressure at or under 3.5 bar g |
| CT-10 | Bypass setting | All external flow shut; set V-105 | 3 L/min ± 0.5 at 70 kPa |
| CT-11 | Service trial | Change filter cartridge, clean strainer, swap pump, all from the front | Each done by one person in under 30 minutes; spill stays in tray |
| CT-12 | Drain | Drain to a container through the low point | At least 90 % of fill volume recovered |

## Stage 2 — Thermal tests with a liquid load bank

| ID | Test | Method | Pass |
|---|---|---|---|
| TT-1 | Rating point | 10 kW, 30 L/min, facility water 27 °C at 24 L/min, hold 30 minutes steady | Supply at or under 32.0 °C; heat balance on both circuits within ±5 % of heater input plus pump power |
| TT-2 | Part load | 2, 5 and 7.5 kW at 32 °C setpoint | Supply within ±1 K; no valve hunting over 20 minutes |
| TT-3 | Overload | 12 kW with facility water at 32 °C | Supply at or under 37.5 °C |
| TT-4 | Cold facility water | 5 kW with facility water at 18 °C | Supply holds setpoint ±1 K; no condensation on any surface |
| TT-5 | Load step | Step from 2 kW to 10 kW and back | Supply overshoot under 3 K; settles within 5 minutes |
| TT-6 | Low server flow | 10 kW at 15 L/min | Supply at or under 32 °C; return near 42 °C |
| TT-7 | Dirty filter | Throttle to simulate 30 kPa filter drop at rating | Flow and temperature criteria of TT-1 still met |
| TT-8 | Dew-point tracking | Feed a simulated humidity signal giving a 30 °C dew point | Setpoint rises to 33 °C automatically |

## Stage 3 — Fault tests with the load bank

| ID | Test | Method | Pass |
|---|---|---|---|
| FT-1 | Low-flow trip | Close V-102 slowly at 10 kW | Load permit opens within 5 s of flow passing 50 % |
| FT-2 | High-temperature trip | Raise the heater outlet with facility flow restricted | Load permit opens at 43 °C ± 0.5 K |
| FT-3 | Facility water lost | Close V-201 at 10 kW; record supply temperature against time | Warning is immediate; trip occurs before 44 °C; **record time from loss to trip** (estimate is about 2 minutes) |
| FT-4 | Pump lost | Cut pump power at 10 kW | Load permit opens within 5 s; **record load-bank outlet temperature rise** |
| FT-5 | Leak in tray | Pour 100 mL of coolant onto the rope | Trip within 10 s; facility shut-off closes; pump stops after 60 s |
| FT-6 | Coolant loss | Bleed coolant slowly from the sample port | Warning at 0.7 bar g, trip at 0.5 bar g; record the volume lost at each |
| FT-7 | Control power lost | Open the supply breaker | Load permit opens; facility shut-off closes |
| FT-8 | PLC stopped | Put the PLC in stop | Load permit opens; pump continues at fallback speed |
| FT-9 | Sensor fault | Disconnect TT-101, then FT-101, then PT-101 | Each gives the trip in the alarm table |
| FT-10 | Network lost | Unplug Ethernet at 10 kW | No change in operation |
| FT-11 | Tray swap | Disconnect and reconnect a dry-break pair 50 times under pressure | Total spill under 5 mL; no air alarm afterwards |

The times recorded in FT-3 and FT-4 become the basis for the site's shutdown procedure.

## Stage 4 — Endurance at the factory

| ID | Test | Pass |
|---|---|---|
| ET-1 | Run 200 hours at 5–10 kW with daily load cycling | No leak; no unplanned trip; filter differential rise under 5 kPa |
| ET-2 | Coolant samples at 0, 100 and 200 hours | pH, glycol concentration and inhibitor level within the coolant supplier's limits; no visible particles |

## Stage 5 — Site commissioning

| ID | Step | Pass |
|---|---|---|
| ST-1 | Delivery inspection and field evaluation | Label applied |
| ST-2 | Facility tie-in, flush of the branch, insulation and vapour seal | Site facilities sign |
| ST-3 | Repeat CT-3, CT-6 and CT-8 with site hoses and manifold | Same criteria |
| ST-4 | Repeat TT-1 and FT-1 to FT-7 on site water with the load bank | Same criteria |
| ST-5 | Monitoring points and load-permit wiring checked end to end | Every alarm seen at the site system; permit drops the bay supply |
| ST-6 | One non-critical server connected and run for 72 hours | Inlet temperature and flow within the server maker's limits throughout |
| ST-7 | Handover | Manual, as-built drawings, test records, spares and sampling schedule delivered; server owner signs |

## Routine maintenance after handover

| Interval | Task |
|---|---|
| Weekly | Check static pressure, filter differential and tray; review alarm log |
| Quarterly | Coolant sample to the supplier's test list; clean strainer; test leak sensors |
| Yearly | Calibrate temperature pairs and flow meters; test relief valve; check tank precharge; exercise the fail-closed valve |
| As needed | Change the filter at 20 kPa; top up only with the same coolant product |
