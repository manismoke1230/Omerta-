# 10 — Purchase specifications

Ready-to-send requests for quotation. Each lists what the supplier must meet and what they must state back. Named products are the basis of design; equivalents are accepted if they meet every line. Send each with [02-design-basis.md](02-design-basis.md) attached.

Answers to the items marked **(HP-xx)** close the hold points in [07-hold-points.md](07-hold-points.md).

---

## RFQ-01 — Circulation pump P-101 (long lead; order first)

Basis of design: Grundfos CME 1-2 A-R-G-E-AQQE class (316 stainless, EPDM, AQQE seal), built-in variable-speed drive, 1 × 200–240 V 50/60 Hz (supply voltage U). Rev C changed this from the CME 1-3 after checking the published curves.

| Requirement | Value |
|---|---|
| Fluid | Inhibited propylene glycol 25 % by volume, 15–50 °C |
| Duty point | 1.8 m³/h at 15.6 m head (PG25 at 35 °C), reached at 95 % speed or less |
| Turndown | Stable down to 0.2 m³/h on a minimum-flow bypass |
| Materials | 316 stainless wetted parts; EPDM elastomers; SiC/SiC or SiC/carbon mechanical seal; no brass, zinc or aluminium wetted |
| Pressure rating | At least 10 bar |
| Drive | Built in; 0–10 V speed input; two signal relays (fault, running); programmable fallback speed on loss of signal |
| Shut-off head at 100 % speed | 27 m or less (keeps dead-head under 3.5 bar g at the 95 % cap) |
| Supply | 208–240 V single-phase 60 Hz preferred |
| Approvals | UL or ETL listed motor and drive |

Supplier to state: **(HP-02)** confirmation of the published CME 1-2 curve (shut-off about 25.6 m) for the 60 Hz US product number; curves at 60, 80 and 95 % speed; motor P2 and maximum P1; full-load current; earth leakage current; minimum inlet pressure (NPSHr) at duty; weight; dimensions; lead time; price for two units (one installed, one spare).

## RFQ-02 — Plate heat exchanger E-101

Basis of design: SWEP B25T × 40 plates, 316L plates, copper brazed.

| Requirement | Value |
|---|---|
| Duty | 10.0 kW |
| Hot side | PG25, 30 L/min, 37.0 °C in → 32.0 °C out |
| Cold side | Water, 24 L/min, 27.0 °C in → 33.0 °C out |
| Arrangement | Single pass, counterflow, all four ports on the front plate |
| Fouling | Rated with at least 20 % excess area over the clean duty |
| Pressure drop | Under 15 kPa per side at the duty flows |
| Design pressure | At least 16 bar both sides |
| Connections | 1 in. BSP or NPT male threaded |
| Extras | Insulation jacket; mounting bolts or bracket |

Supplier to state: **(HP-03)** plate count and model; clean and fouled UA; pressure drops; hold-up volumes; dimensions and weight; suitability of copper braze with inhibited PG25 at a pH of 8–10; alternative all-stainless (fusion-bonded) unit for the same duty with price; lead time.

## RFQ-03 — Flow meters FT-101, FT-201

Basis of design: ifm SM7000 (0.2–50 L/min, magnetic-inductive).

| Requirement | Value |
|---|---|
| Range | 0.2–50 L/min |
| Accuracy | ±(0.8 % of reading + 0.5 % of full scale) or better |
| Fluids | PG25 and treated water; magnetic meters need at least 20 µS/cm (coolant supplier to confirm for the chosen PG25). If not met, quote ultrasonic meters (ifm SU7000 class). |
| Output | 4–20 mA plus a switching output |
| Pressure rating | At least 16 bar (SM7000: 16 bar) |
| Fluid temperature | At least −10 to 70 °C (SM7000) |
| Connection | 1 in. or ¾ in. thread; M12 electrical |

Supplier to state: **(HP-04)** pressure drop at 30 L/min in PG25 and in water; minimum fluid conductivity, with confirmation that PG25 meets it; response time; price; lead time.

## RFQ-04 — Filter F-101 and strainer STR-201

| Item | Requirement |
|---|---|
| F-101 housing | 316 stainless, 10 in. single cartridge, bowl-down, 1 in. ports, at least 10 bar, vent and drain on the bowl |
| F-101 cartridge | 50 µm nominal, pleated 316 stainless mesh or polypropylene compatible with PG25; two supplied |
| STR-201 | 1 in. Y-strainer, 316 body, 20 mesh 316 screen, blow-down valve, at least 16 bar |

Supplier to state: **(HP-04)** clean and dirty pressure drop at 30 L/min PG25; recommended change-out differential; withdrawal clearance below the bowl; price; lead time.

## RFQ-05 — Expansion tank, relief valves, air vent

| Item | Requirement |
|---|---|
| TK-101 | 7.6–8 L (2 US gal) diaphragm tank, EPDM or butyl diaphragm, precharge 0.8 bar g, at least 6 bar, ¾ in. connection. **ASME Section VIII Division 1 stamped and National Board registered (required, D-33).** |
| PSV-101 | ½ in. relief valve, 316 body, EPDM seat, set 4.0 bar g, capacity at least 30 L/min PG25 at 10 % overpressure, threaded outlet |
| PSV-201 | ½ in. thermal relief valve for the facility side, set at the facility design pressure (10 bar g assumed) |
| AV-101 | Automatic float air vent, brass-free (stainless or engineering polymer), at least 10 bar, with an isolation valve |

## RFQ-06 — Control and shut-off valves

| Item | Requirement |
|---|---|
| TCV-201 | ½ in. two-way characterised control valve, equal-percentage, Cv 4.7, close-off at least 2 bar, 0 % leakage, rated for glycol up to 60 %. Actuator 24 V AC/DC, 2–10 V command, 2–10 V position feedback, non-spring return (fails in place), running time 90 s or less. Basis: Belimo characterised control valve with LRB24-SR actuator. |
| XV-201 | 1 in. full-bore two-way ball valve, stainless ball and stem. Actuator 24 V, on/off, spring return to closed in 25 s or less, auxiliary switches for open and closed. |

## RFQ-07 — Instruments

| Item | Requirement |
|---|---|
| TT-101/102/201/202 | Pt100 class A, 4-wire, 6 mm sheath in 316 thermowells with 50 mm immersion; supplied as two matched pairs (within 0.05 K at 25 °C and 40 °C), with calibration certificates |
| PT-101/102/103 | 0–6 bar g, 4–20 mA, 316 wetted, accuracy ±0.25 % of span, M12 |
| PT-201/202 | 0–16 bar g, otherwise as above |
| PDT-101 | 0–100 kPa differential, 4–20 mA, 316 wetted, accuracy ±0.5 % of span |
| AT-301 | Room temperature and humidity transmitter, 4–20 mA, ±2 % RH |
| LDS-301 | Glycol-responsive leak sensing rope, about 2.5 m, with controller and relay output |
| LDS-302 | Spot leak sensor with relay output for the external hose tray |

## RFQ-08 — Cabinet fabrication

| Requirement | Value |
|---|---|
| Envelope | 600 W × 800 D × 1200 H mm overall, on four 100 mm castors (two braked), with levelling feet |
| Frame | Welded or bolted steel, powder coated |
| Panels | 1.2 mm steel, removable side and rear panels, front door with lock |
| Drip tray | 1.5 mm 316 stainless, full internal footprint, 40 mm deep, welded corners, drain fitting at the lowest point |
| Drip shield | Sloped stainless sheet above the wet zone at 805–830 mm, draining to the rear into the tray |
| Rear panel | Four 1 in. sanitary clamp ferrules at 560–640 mm height; external hose support bracket rated 200 N |
| Castors | At least 600 N each |
| Stability | No tipping at 10° tilt in any direction with the door open (IEC 61010-1 cl. 7.3); layout check predicts at least 26° |
| Drawings | Fabricator produces shop drawings from [cad/](cad/) for approval |

## RFQ-09 — Hose kit and bay manifold

| Requirement | Value |
|---|---|
| Hoses | Two pairs, 1 in. ID, 3 m, EPDM-lined, rated at least 10 bar at 60 °C, 1 in. sanitary clamp ends at the CDU |
| Manifold | 316, four branches, each with an isolation valve and the servers' own quick-disconnect type |
| Quick disconnects | Dry-break, rated for at least 5,000 connection cycles, spill under 0.1 mL per disconnection (test FT-11 checks this), EPDM seals |
| Hose-end tray | Stainless tray under the manifold, with spot leak sensor LDS-302 |
