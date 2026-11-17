# 06 — Bill of materials and cost estimate (Rev B)

**These are my engineering estimates in US dollars, not quotations.** Expect ±40 % until quotes arrive. The only price I found published is the ifm SM7000 flow meter, listed by RS at about €929 including tax.

## Parts

| Group | Items | Estimate |
|---|---|---:|
| Pump | Grundfos CME 1-3, 316 stainless, with drive | $3,000 |
| Spare pump | Same, kept on the shelf | $3,000 |
| Heat exchanger | SWEP B25T × 30 or equal, with insulation kit | $900 |
| Filter and strainer | 316 housing, two 50 µm cartridges, Y-strainer | $900 |
| Expansion, relief, venting | 8 L tank, two relief valves, air vent | $600 |
| Manual valves | Ball valves, balancing valve, sample and drain valves | $1,200 |
| Actuated valves | Control valve with actuator; fail-closed shut-off valve | $900 |
| Flow meters | Two magnetic-inductive meters | $2,100 |
| Pressure and temperature | Five pressure transmitters, one differential, four 4-wire Pt100 as matched pairs with wells | $2,300 |
| Leak and room sensing | Leak rope and controller, spot sensor, temperature/humidity transmitter | $700 |
| Controls | PLC with I/O (spares per 09-electrical.md), touchscreen, 24 V supply and buffer, watchdog and permit relays, SPD, Ethernet switch, breakers, enclosure, wiring | $5,200 |
| Pipework | 316L tube, fittings, unions, sanitary ferrules, supports, insulation | $2,200 |
| Cabinet | Frame, panels, door, stainless drip tray and shield, castors; 1200 mm high | $2,900 |
| Hose kit | Two 3 m hoses, bay manifold, dry-break couplings | $1,800 |
| Coolant | 40 L of PG25 and sample kits | $400 |
| **Parts total** | | **$28,100** |
| Without spare pump | | $25,100 |

## Build and approval

| Item | Estimate |
|---|---:|
| Mechanical assembly and pipe fitting, about 90 hours (taller cabinet, front valve bank) | $9,000 |
| Panel build and wiring to UL 508A, about 60 hours | $6,000 |
| PLC commissioning on the target, HMI screens, logic test CT-13, about 50 hours (program already written) | $6,000 |
| Factory tests, including hire of a 10 kW liquid load bank | $6,000 |
| NRTL field evaluation | $6,000 |
| Shipping, site tie-in and commissioning support | $5,000 |
| **Build and approval total** | **$38,000** |

## Totals

| | Estimate |
|---|---:|
| Parts with spare pump | $28,100 |
| Build and approval | $38,000 |
| **Prototype total** | **about $66,000** |
| Range at ±40 % on parts and ±25 % on labour | $50,000–80,000 |

Design engineering hours are not included.

## Lead times

My expectation, to be confirmed with quotes: pump 4–8 weeks, exchanger 2–6 weeks, instruments 1–3 weeks, cabinet fabrication 3–4 weeks. The pump is the long-lead item and is ordered first.

## Comparison with buying

A commercial lab-grade liquid-to-liquid cooler would avoid most of the $40,000 build and approval cost. If one meets every line of the interface tables in [02-design-basis.md](02-design-basis.md), it is the cheaper route. This design is justified where none does, in particular on differential-pressure control, the hardwired load permit, dew-point tracking and front service.
