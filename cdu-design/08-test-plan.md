# 08 — Test and commissioning plan (Rev B)

No test has been run on hardware. Where the dynamic simulation covers a test, its prediction is shown, so a hardware result far from it points to a model or build error worth investigating. Predictions come from [sim/results.md](sim/results.md).

## Stage 1 — Cold tests at the factory

| ID | Test | Method | Pass |
|---|---|---|---|
| CT-1 | Inspection | Build against P&ID, tag list, materials list and the layout drawing | No deviations open |
| CT-2 | Flush | Circulate clean water through a 25 µm temporary filter until clean; drain | Filter clean after 30 minutes |
| CT-3 | Pressure test, server loop | Hydrostatic at 6.0 bar g for 30 minutes. Relief valve removed and its port plugged; tank isolated. | No visible leak; pressure loss under 0.1 bar |
| CT-4 | Pressure test, facility side | Hydrostatic at 1.5 × facility design pressure for 30 minutes | Same |
| CT-5 | Relief valve | Bench test with a hand pump before refitting | Opens at 4.0 bar g ± 3 %; reseats above 3.6 bar g |
| CT-6 | Fill, vent, inventory zero | Fill PG25 through the low-point coupling; fill-and-vent mode; press inventory zero when cold | Stable flow within 15 minutes; static pressure 1.0 bar g; inventory deficit within ±0.05 L |
| CT-7 | Instrument check | Pt100s in a stirred bath at 25 °C and 40 °C; pressure transmitters against a reference gauge | Matched pairs within 0.1 K; pressures within 0.5 % of range |
| CT-8 | Pump and system curve | Throttle valve standing in for the servers; record flow, pressures and speed at 10 points | 30 L/min at 100 kPa external at or under 85 % speed |
| CT-9 | Dead-head pressure | V-102 and bypass closed, pump at the speed cap | Discharge at or under 3.5 bar g (predicted 3.4) |
| CT-10 | Bypass setting | All external flow shut; set V-105 | 3 L/min ± 0.5 at 70 kPa |
| CT-11 | Service trial | Change the filter cartridge, clean the strainer, swap the pump, all from the front | Each done by one person in under 30 minutes; spill stays in the tray |
| CT-12 | Drain | Drain through the low point | At least 90 % of fill recovered |
| CT-13 | PLC logic test (HP-08) | Run the 18 cases of `calc/test_control.py` on the real PLC by forcing inputs | Every case gives the same result as the reference model |

## Stage 2 — Thermal tests with a liquid load bank

| ID | Test | Method | Pass | Predicted |
|---|---|---|---|---|
| TT-1 | Rating point | 10 kW, 29 L/min, facility 27 °C, 30 minutes steady | Supply 32.0 ± 0.5 °C; both heat balances within ±5 % of heater plus pump power | 32.03 °C; 10.00 kW server side, 10.14 kW facility side (133 W pump heat) |
| TT-2 | Light load | 2 kW on 18 °C facility water, 30 minutes | Supply ±0.5 K; valve travel under 50 % of stroke per hour | 31.99 °C, ripple 0.14 K, valve 19 %, travel 1.5 %/h |
| TT-3 | Overload | 12 kW, facility 32 °C | Supply at or under 37 °C; no trip | 36.3 °C steady-state calculation |
| TT-4 | Cold facility water | 5 kW on 18 °C facility water | Setpoint held ±0.5 K; no condensation | Covered by TT-2 behaviour |
| TT-5 | Load step | 2 → 10 → 2 kW | Overshoot under 2 K; back within ±0.5 K in under 5 minutes | +0.93 K / −0.96 K; 111 s / 144 s |
| TT-6 | Low server flow | 10 kW at 15 L/min | Supply at or under 32 °C | 29.2 °C capability (calculation) |
| TT-7 | Filter loading | Throttle the filter from 5 to 30 kPa at 10 kW | Server flow within 2 % of start; filter warning at 20 kPa | 26.00 → 26.01 L/min; warning issued |
| TT-8 | Dew-point tracking | Simulated humidity signal giving a 30 °C dew point | Setpoint rises to 33 °C | 33.0 °C, supply 33.0 °C |
| TT-9 | Facility temperature step | 22 → 27 °C at 8 kW | Deviation under 1.5 K | 0.81 K |
| TT-10 | Facility pressure step | 50 → 90 → 50 kPa at 10 kW | Deviation under 1 K | 0.34 K |
| TT-11 | Cold start | Loop at 15 °C, 10 kW servers start when permitted | Supply peak under 34 °C; no trip | 32.6 °C; permit at 16 s |
| TT-12 | Server unplugged | One of two branches closed at 10 kW (load halves) | Remaining branch flow within 3 %; supply within 1.5 K | 13.0 → 13.0 L/min; 0.98 K |

## Stage 3 — Fault tests with the load bank

| ID | Test | Method | Pass | Predicted |
|---|---|---|---|---|
| FT-1 | Pump lost | Cut pump power at 10 kW | Permit opens within 6 s of the power cut | 4.6 s |
| FT-2 | High-temperature trip | Restrict facility flow so supply rises slowly | Permit opens at server limit − 2 K ± 0.5 K (38 °C for 40 °C servers) | Logic test passes |
| FT-3 | Facility water lost | Close V-201 at 10 kW; record supply against time | Alarm at 10 ± 1 s; trip at 20 ± 1 s; peak supply under the server limit | 10.3 s; 20.2 s; 37.4 °C |
| FT-4 | Facility interruption | Close V-201 for 15 s at 10 kW, then reopen | No trip | Peak 35.5 °C, no trip |
| FT-5 | Leak in tray | 100 mL of coolant on the sensing rope | Trip within 10 s; shut-off closes; pump stops after 60 s | Logic test passes |
| FT-6 | Slow leak | Bleed 0.1 L/min from the sample port at 5 kW | Warning before 0.4 L lost; trip before 0.8 L lost; record both | 0.31 L; 0.64 L |
| FT-7 | Control power lost | Open the 24 V supply breaker | Permit opens; shut-off springs closed | Hardware behaviour |
| FT-8 | PLC stopped | Put the PLC in stop | Permit opens within 0.5 s by watchdog; pump continues at 60 % | Hardware behaviour |
| FT-9 | Sensor faults | Disconnect TT-101, then FT-101, then PT-101 | Each trips; valve and pump held | Logic test passes |
| FT-10 | Network lost | Unplug Ethernet at 10 kW | No change in operation | — |
| FT-11 | Quick-disconnect cycling | Connect and disconnect a pair 50 times under pressure | Total spill under 5 mL; no inventory warning afterwards | — |

Times measured in FT-1 and FT-3 go into the site shutdown procedure. If they differ from the predictions by more than 25 %, the plant model is updated and the trip settings are re-checked in simulation before site delivery.

## Stage 4 — Endurance at the factory

| ID | Test | Pass |
|---|---|---|
| ET-1 | 200 hours at 5–10 kW with daily load cycling | No leak; no unplanned trip; filter differential rise under 5 kPa; inventory drift under 0.1 L |
| ET-2 | Coolant samples at 0, 100 and 200 hours | pH, glycol and inhibitor within the supplier's limits; no visible particles |

## Stage 5 — Site commissioning

| ID | Step | Pass |
|---|---|---|
| ST-1 | Delivery inspection and NRTL field evaluation | Label applied |
| ST-2 | Facility tie-in, branch flush, insulation and vapour seal | Site facilities sign |
| ST-3 | Repeat CT-3, CT-6 (with a new inventory zero) and CT-8 with site hoses and manifold | Same criteria |
| ST-4 | Repeat TT-1, FT-1, FT-3, FT-4 and FT-5 on site water with the load bank | Same criteria |
| ST-5 | Load-permit end-to-end (HP-09) | Opening the permit cuts server load below 20 % within 10 s |
| ST-6 | Monitoring points and Modbus map checked against the site system | Every alarm seen at the site |
| ST-7 | One non-critical server connected for 72 hours | Inlet temperature and flow within the maker's limits throughout |
| ST-8 | Handover | Manual, as-built drawings, test records, spares and sampling schedule delivered; server owner signs |

## Routine maintenance

| Interval | Task |
|---|---|
| Weekly | Check static pressure, inventory deficit, filter differential and tray; review alarm log |
| Quarterly | Coolant sample; clean strainer; test leak sensors |
| Yearly | Calibrate temperature pairs and flow meters; test relief valve; check tank precharge and redo inventory zero; exercise the shut-off valve |
| After any top-up or server swap | Inventory zero once the loop is cold and vented |
| As needed | Change filter at 20 kPa; top up only with the same coolant product |
