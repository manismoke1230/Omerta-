# 09 — Electrical and controls hardware

## Power supply

| Item | Decision |
|---|---|
| Supply | 208–240 V single-phase, 60 Hz, through an IEC 60320 C20 inlet (16 A). The cord to the site is a C19 to a PDU outlet or an L6-20 whip, to suit the bay. |
| Main isolation | Lockable rotary disconnect on the cabinet side, outside the door |
| Earthing | Frame, door, drip tray, pipework and panel back-plate bonded to PE with 6 mm² green/yellow leads. Pump and actuators earthed through their cords. |
| Earth leakage | Drive leakage current to be confirmed with Grundfos (HP-02). If the site requires ground-fault protection on the bay supply, use a type suitable for drives (type B or F) to avoid nuisance trips. |
| Short-circuit rating | Panel SCCR 5 kA (UL 508A default for these components); confirm the site's available fault current at the receptacle is lower |
| Surge protection | Type 2 SPD on the incoming supply |

## Load schedule

| Load | Running | Maximum | Notes |
|---|---:|---:|---|
| Pump motor and built-in drive | 220 W | 1,000 W | Running value from the simulation at 10 kW (76 W hydraulic at 35 % wire-to-water); maximum is the assumed motor rating, confirm at HP-02 |
| 24 V DC system (PLC, HMI, transmitters, flow meters, actuators, relays) | 45 W | 70 W | From the 24 V budget below |
| 24 V power supply losses | 8 W | 12 W | 90 % efficiency |
| **Total** | **about 275 W** | **about 1,080 W** | 5.2 A at 208 V maximum |
| Heat released into the room | about 200 W | | Motor and drive losses plus controls; the hydraulic power ends up in the coolant |

## 24 V DC budget

| Consumer | Quantity | Each | Total |
|---|---:|---:|---:|
| PLC CPU with I/O modules | 1 | 15 W | 15 W |
| Touchscreen HMI, 7 in. | 1 | 10 W | 10 W |
| Magnetic flow meters | 2 | 3 W | 6 W |
| Pressure transmitters (loop powered, 20 mA worst case) | 6 | 0.5 W | 3 W |
| Room temperature and humidity transmitter | 1 | 1 W | 1 W |
| Leak detection controller | 1 | 3 W | 3 W |
| Control valve actuator (running / holding) | 1 | 2.5 / 1 W | 2.5 W |
| Shut-off valve actuator, spring return (running / holding) | 1 | 8 / 4 W | 8 W |
| Relays (permit, watchdog, interposing) | 5 | 0.5 W | 2.5 W |
| Ethernet switch, 5 port | 1 | 3 W | 3 W |
| Spare | | | 16 W |
| **Total** | | | **70 W** |

24 V supply: 5 A (120 W) DIN-rail unit with a capacitor buffer module giving 2 s ride-through at full load. The buffer lets the PLC log a power loss and set the outputs to a defined state.

## I/O list

| Type | Signal | Tag | Range / note |
|---|---|---|---|
| RTD | Server supply temperature | TT-101 | Pt100 class A, 4-wire, matched pair with TT-102 |
| RTD | Server return temperature | TT-102 | Pt100 class A, 4-wire |
| RTD | Facility supply temperature | TT-201 | Pt100 class A, 4-wire, matched pair with TT-202 |
| RTD | Facility return temperature | TT-202 | Pt100 class A, 4-wire |
| AI 4–20 mA | Static pressure | PT-101 | 0–6 bar g |
| AI 4–20 mA | Pump discharge pressure | PT-102 | 0–6 bar g |
| AI 4–20 mA | Server supply pressure | PT-103 | 0–6 bar g |
| AI 4–20 mA | Filter differential | PDT-101 | 0–100 kPa |
| AI 4–20 mA | Facility supply pressure | PT-201 | 0–16 bar g |
| AI 4–20 mA | Facility return pressure | PT-202 | 0–16 bar g |
| AI 4–20 mA | Server-loop flow | FT-101 | 0–50 L/min |
| AI 4–20 mA | Facility flow | FT-201 | 0–50 L/min |
| AI 4–20 mA | Room temperature | AT-301T | 0–50 °C |
| AI 4–20 mA | Room humidity | AT-301H | 0–100 % |
| AI 0–10 V | Control valve position feedback | ZT-201 | 2–10 V = 0–100 % |
| AI 0–10 V | Pump speed feedback | ST-101 | from drive analogue output |
| AO 0–10 V | Pump speed command | SC-101 | 0–10 V = 0–100 % |
| AO 0–10 V | Control valve command | TCV-201 | 2–10 V = 0–100 % |
| DI | Drip-tray leak | LDS-301 | from leak controller relay |
| DI | Hose-end leak | LDS-302 | spot sensor relay |
| DI | Remote stop | HS-301 | normally closed, wire break = stop |
| DI | Drive fault | P-101F | from drive relay |
| DI | Drive running | P-101R | from drive relay |
| DI | Shut-off valve open | ZSO-201 | actuator auxiliary switch |
| DI | Shut-off valve closed | ZSC-201 | actuator auxiliary switch |
| DI | Watchdog healthy | WD-301 | watchdog relay contact |
| DI | 24 V buffer / mains failure | PSU-301 | buffer module contact |
| DI | Door open | ZS-301 | for maintenance logging |
| DO | Pump run enable | P-101E | to drive start input |
| DO | Shut-off valve open | XV-201 | energise to open; spring closes |
| DO | Load permit | XS-301 | to permit relay coil, in series with the watchdog contact |
| DO | Watchdog heartbeat | WD-301H | 1 Hz pulse |
| DO | Beacon and horn | XA-301 | on any alarm or trip |

**Counts:** 4 RTD, 12 AI, 2 AO, 10 DI, 5 DO. Hardware selected with at least 20 % spare in each class: 4 RTD, 16 AI, 4 AO, 16 DI, 8 DO.

## Power distribution

```
C20 inlet ── rotary disconnect (lockable) ── Type 2 SPD
                     │
                     ├── MCB 10 A (C curve) ── pump P-101 (built-in drive)
                     ├── MCB 2 A ── 24 V DC PSU 5 A ── buffer module ── 24 V distribution
                     │                                         ├── F1 2 A  PLC CPU and I/O
                     │                                         ├── F2 1 A  HMI and Ethernet switch
                     │                                         ├── F3 1 A  field transmitters and flow meters
                     │                                         ├── F4 2 A  actuators (TCV-201, XV-201)
                     │                                         └── F5 1 A  leak controller, relays, beacon
                     └── MCB 2 A ── service socket inside the panel (for a laptop)

Load permit chain (to the bay's power distribution or server management interlock):
  PLC DO XS-301 ── watchdog relay contact (opens if the 1 Hz heartbeat stops for 500 ms)
              ── permit relay coil K1 ── K1 NO contact to the bay interface terminals
```

## Panel construction

| Item | Decision |
|---|---|
| Standard | UL 508A industrial control panel, built by a UL 508A listed shop. The complete CDU then gets an NRTL field evaluation (decision D-22). |
| Enclosure | Steel, IP54 / NEMA 12, about 520 W × 320 H × 220 D mm, in the dry zone above the drip shield |
| Back-plate layout | Two DIN rails with wiring duct; power at the top left, 24 V distribution top right, PLC and I/O on the lower rail |
| Cable entry | From the top through cable glands. Field cables from the wet zone rise behind the drip shield with a drip loop below each gland. |
| Wiring | 24 V DC blue, AC black / white, PE green/yellow, 4–20 mA shielded twisted pair with the shield earthed at the panel only |
| Field connections | M12 connectors on transmitters and flow meters so each can be replaced without rewiring |
| Segregation | Mains and drive cables in separate duct from signal cables; at least 100 mm separation where they run in parallel |
| Labels | Every wire numbered at both ends; every device tagged to match the P&ID |

## Controller selection

A compact PLC that runs CODESYS 3.5 (for example WAGO PFC200 or Beckhoff CX series, or equal). It needs:

- Modbus TCP server
- RTD inputs with 4-wire capability and 0.1 K resolution or better
- 100 ms cyclic task
- Retained parameter memory
- A 7 in. touchscreen web HMI or panel

The program is written to that dialect (see [plc/](plc/)).

## Network and cybersecurity

- One Ethernet port to the site monitoring network, on a VLAN the site assigns.
- Modbus TCP is read-only by default. Writes are enabled only from the HMI, with a password, and then only for the setpoints listed in [plc/README.md](plc/README.md).
- Start, stop, reset and inventory zero are local-only.
- All default passwords are changed at commissioning. Unused services (FTP, Telnet, web configuration) are disabled.
- The unit keeps operating with the network disconnected (simulated and tested as FT-10).
