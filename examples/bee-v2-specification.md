# Bee v2 — Hardware Design Specification

## Overview

Wearable BLE device for ambient conversation transcription and emotion detection with biometric sensing (PPG + EDA). Spiritual successor to the Bee Pioneer with added health monitoring and dual-microphone array.

**Form factor:** 75mm x 18mm rigid PCB (elongated to accommodate 55mm mic spacing)
**Layers:** 2-layer, 1.6mm FR-4
**Target fab:** JLCPCB standard 2-layer process

---

## Block Diagram

```
                          ┌──────────────────────────────────────────────────┐
                          │                   75mm x 18mm PCB                │
                          │                                                  │
  ┌─────┐   ┌────────┐   │  ┌──────────┐   ┌──────────┐   ┌──────────┐     │  ┌─────┐
  │USB-C├───┤MCP73831├───┼──┤nRF54LM20B├───┤ MAX86178 ├───┤DRV2605L ├──┐  │  │MIC2 │
  │     │   │Charger │   │  │   SoC    │   │ PPG+EDA  │   │ Haptic  │  │  │  │(R)  │
  └──┬──┘   └───┬────┘   │  └────┬─────┘   └────┬─────┘   └────┬────┘  │  │  └──┬──┘
     │          │        │       │              │              │      │  │     │
  ┌──┴──┐   ┌──┴──┐     │  ┌────┴────┐    ┌───┴───┐    ┌────┴───┐  │  │     │
  │ESD  │   │300mA│     │  │I2S Bus  │    │SPI Bus│    │LRA     │  │  │     │
  │TVS  │   │LiPo │     │  │        │    │       │    │Motor   │  │  │     │
  └─────┘   └─────┘     │  │        │    │       │    └────────┘  │  │     │
                         │  ┌┴┐    ┌─┴┐   ┌┴──┐┌──┴┐              │  │     │
  ┌─────┐                │  │M│    │Btn│  │LED││PD │              │  │     │
  │MIC1 ├────────────────┼──┤I│    └───┘  │   ││   │              │  │     │
  │(L)  │                │  │C│           └───┘└───┘              │  │     │
  └─────┘                │  │1│                                    │  │     │
                          │  └─┘         ┌─────┐                   │  │     │
                          │              │1.8V │                   │  │     │
                          │              │LDO  │                   │  │     │
                          │              └─────┘                   │  │     │
                          └──────────────────────────────────────────────────┘
                          ←── 55mm mic spacing ────────────────────────────→
```

---

## Component Specification

### U1: nRF54LM20B — Main SoC

| Parameter | Value |
|---|---|
| Package | QFN52 (6x6mm) |
| Core | Cortex-M33 @ 128MHz + RISC-V coprocessor |
| NPU | Axon NPU @ 128MHz (edge AI inference) |
| Memory | 2MB NVM, 512KB RAM |
| Radio | BLE 5.4, Thread, Zigbee, 2.4GHz proprietary |
| Supply | 1.7V-3.6V (internal DC-DC converter) |
| Key peripherals used | I2S (mics), SPI (MAX86178), I2C (DRV2605L), USB, GPIO |

**Pin assignments (functional):**

| Function | nRF Pin | Connects To |
|---|---|---|
| I2S_SCK | P0.12 | MIC1.SCK, MIC2.SCK |
| I2S_LRCK | P0.13 | MIC1.WS, MIC2.WS |
| I2S_SDIN | P0.14 | MIC1.SD, MIC2.SD (L/R muxed) |
| SPI_SCK | P0.15 | U2.SCLK |
| SPI_MOSI | P0.16 | U2.SDI |
| SPI_MISO | P0.17 | U2.SDO |
| SPI_CS | P0.18 | U2.CSB |
| I2C_SDA | P0.19 | U3.SDA |
| I2C_SCL | P0.20 | U3.SCL |
| GPIO_INT_AFE | P0.21 | U2.INTB (active low) |
| GPIO_EN_HAPTIC | P0.22 | U3.EN |
| GPIO_BTN | P0.23 | SW1 (active low, internal pull-up) |
| GPIO_LED | P0.24 | R_LED -> LED1 |
| GPIO_CHRG_STAT | P0.25 | U4.STAT |
| USB_DP | USB_D+ | J1.DP |
| USB_DN | USB_D- | J1.DN |
| XC1, XC2 | Crystal | Y1 (32MHz) |
| XL1, XL2 | Crystal | Y2 (32.768kHz) |
| ANT | RF output | Pi-match -> wire antenna |
| DCC | DC-DC | L1 (10uH) -> C4 |
| VDD, VDDH, VSS | Power | Battery via charger |

**External components required by nRF:**
- 32MHz crystal (Y1) + 2x 12pF load caps
- 32.768kHz crystal (Y2) + 2x 15pF load caps
- 10uH DC-DC inductor (L1) + 1uF filter cap
- 4.7uF + 2x 100nF decoupling caps
- Antenna pi-match: 3.9nH inductor, 1.5pF + 1pF caps

---

### U2: MAX86178 — PPG + EDA Analog Front End

| Parameter | Value |
|---|---|
| Package | WLP49 (2.77 x 2.57mm, 0.4mm pitch) |
| Supply | 1.71V-1.98V (1.8V from LDO) |
| Interface | SPI (up to 12MHz) |
| PPG channels | 2 optical readout, 6 LED drivers, 4 PD inputs |
| ECG | 1 single-lead channel (not used in this design) |
| BioZ | Tetrapolar/bipolar, used for EDA measurement |
| ADC | 19-bit for PPG, 18-bit for ECG/BioZ |

**NOTE:** Full pinout requires NDA from Analog Devices. WLP49 footprint not in standard libraries — requires custom footprint creation from datasheet bump map.

**Connections:**

| MAX86178 Pin | Function | Connects To |
|---|---|---|
| SCLK | SPI clock | nRF P0.15 |
| SDI | SPI data in | nRF P0.16 |
| SDO | SPI data out | nRF P0.17 |
| CSB | SPI chip select | nRF P0.18 |
| INTB | Interrupt | nRF P0.21 |
| LED_DRV1 | Green LED drive 1 | LED_PPG1 anode |
| LED_DRV2 | Green LED drive 2 | LED_PPG2 anode |
| PD_INP/INN | Photodiode input | PD1 |
| BIP/BIN | BioZ drive | EDA electrode pads (bottom) |
| VDD18 | 1.8V supply | U5.VOUT |
| VSS | Ground | Common ground |

**External optical components:**
- 2x green LEDs (0603) — wavelength ~530nm for PPG heart rate
- 1x photodiode (0805) — VEMD5010X01 or equivalent, 540nm peak
- Components mounted on bottom (skin-facing) side

**EDA electrodes:**
- 2x exposed copper pads on bottom side of PCB
- Spacing: ~15mm apart
- Connected to BioZ BIP/BIN through vias
- Gold plating (ENIG) recommended for skin contact

---

### U3: DRV2605L — Haptic Motor Driver

| Parameter | Value |
|---|---|
| Package | DGS (VSSOP-10, 3x3mm) |
| Supply | 2.0V-5.2V (powered from VBAT) |
| Interface | I2C (address 0x5A fixed) |
| Output | Differential, up to 300mA peak |
| Library | 123 built-in haptic effects |
| Features | Auto-resonance tracking for LRA |

| DRV2605L Pin | Function | Connects To |
|---|---|---|
| VDD (6,10) | Supply | VBAT |
| GND (8) | Ground | Common ground |
| SCL (2) | I2C clock | nRF P0.20 |
| SDA (3) | I2C data | nRF P0.19 |
| EN (5) | Enable | nRF P0.22 |
| IN/TRIG (4) | Input | Tied to GND (I2C mode) |
| REG (1) | 1.8V out | 1uF cap to GND |
| OUT+ (7) | Motor+ | M1 positive |
| OUT- (9) | Motor- | M1 negative |

**Motor:** 8mm coin-type LRA (Linear Resonant Actuator), ~170Hz resonance

---

### U4: MCP73831 — LiPo Charge Controller

| Parameter | Value |
|---|---|
| Package | SOT-23-5 |
| Input | 4.35-6V (USB VBUS, 5V) |
| Charge voltage | 4.2V (Li-Ion/LiPo) |
| Charge current | 500mA (R_PROG = 2kOhm) |

| MCP73831 Pin | Function | Connects To |
|---|---|---|
| VDD (4) | USB power input | J1.VBUS + 4.7uF cap |
| VSS (2) | Ground | Common ground |
| VBAT (3) | Battery output | BAT1+ + 4.7uF cap |
| STAT (1) | Charge status | nRF P0.25 (tri-state) |
| PROG (5) | Current program | 2kOhm to GND (=500mA) |

---

### U5: AP2112K-1.8 — 1.8V LDO

| Parameter | Value |
|---|---|
| Package | SOT-23-5 |
| Input | 2.5-6V (from VBAT) |
| Output | 1.8V, 600mA max |
| Dropout | 250mV @ 600mA |
| Quiescent | 55uA |

Supplies clean 1.8V to MAX86178. Input and output: 1uF ceramic caps each.

---

### MIC1, MIC2: ICS-43434 — Digital MEMS Microphones

| Parameter | Value |
|---|---|
| Package | LGA (3.50 x 2.65 x 0.98mm), bottom port |
| Interface | I2S (24-bit, not PDM) |
| SNR | 65 dBA |
| AOP | 120 dB SPL |
| Sensitivity | -26 dBFS +/-1dB |
| Current | 490uA normal, 230uA low-power |
| Sample rate | 23-51.6 kHz |
| L/R select | Pin 3: Low=Left, High=Right |

**Placement:**
- MIC1 at x=-25mm (left end, near USB-C), LR_SEL = GND (Left)
- MIC2 at x=+30mm (right end), LR_SEL = VDD via 10k pullup (Right)
- Spacing: ~55mm (within 5-7cm requirement)
- Both share single I2S bus (SCK, WS, SD) — data is time-multiplexed L/R
- Bottom-port: acoustic hole in PCB required under each mic
- 100nF decoupling cap within 1mm of VDD pin on each

---

### J1: USB Type-C Connector

6-pin mid-mount USB-C (simplified, power + USB 2.0 data):

| Pin | Function | Connection |
|---|---|---|
| GND | Ground | Common ground |
| VBUS | 5V USB power | U4.VDD (charge IC input) |
| CC1 | Configuration channel 1 | 5.1k to GND |
| CC2 | Configuration channel 2 | 5.1k to GND |
| D+ | USB data positive | nRF USB_DP |
| D- | USB data negative | nRF USB_DN |

- TVS diode (SOT-23) on USB data lines for ESD protection
- 5.1k CC resistors identify device as UFP (sink), requesting default 5V/500mA

---

### Passive Components

| Ref | Value | Package | Purpose |
|---|---|---|---|
| R_CC1, R_CC2 | 5.1kOhm | 0402 | USB-C CC pull-down |
| R_PROG | 2kOhm | 0402 | MCP73831 charge current (500mA) |
| R_LED | 330Ohm | 0402 | Status LED current limit (~5mA @ 1.8V) |
| R_LR1 | 0Ohm | 0402 | MIC1 LR select = GND (jumper) |
| R_LR2 | 10kOhm | 0402 | MIC2 LR select = VDD |
| C1, C2 | 100nF | 0402 | nRF VDD decoupling |
| C3 | 4.7uF | 0402 | nRF VDDH decoupling |
| C4 | 1uF | 0402 | nRF DC-DC filter |
| C5 | 100nF | 0402 | MAX86178 decoupling |
| C6 | 1uF | 0402 | MAX86178 bulk decoupling |
| C7 | 1uF | 0402 | DRV2605L VDD decoupling |
| C8 | 1uF | 0402 | DRV2605L REG output |
| C9 | 4.7uF | 0805 | MCP73831 input cap |
| C10 | 4.7uF | 0805 | MCP73831 output (battery) cap |
| C11 | 1uF | 0402 | LDO input cap |
| C12 | 1uF | 0402 | LDO output cap |
| C13, C14 | 100nF | 0402 | MIC1/MIC2 decoupling |
| C15, C16 | 12pF | 0402 | 32MHz crystal load caps |
| C17, C18 | 15pF | 0402 | 32.768kHz crystal load caps |
| C_ANT1 | 1.5pF | 0402 | Antenna match (shunt to GND) |
| C_ANT2 | 1pF | 0402 | Antenna match (shunt to GND) |
| L_ANT | 3.9nH | 0402 | Antenna match (series) |
| L1 | 10uH | 0402 | nRF DC-DC inductor |
| D_ESD | TVS | SOT-23 | USB ESD protection |
| Y1 | 32MHz | 2.0x1.6mm | nRF main clock crystal |
| Y2 | 32.768kHz | 1.6x1.0mm | nRF RTC crystal |

**Total unique parts:** ~30
**Total component count:** 46

---

## Power Architecture

```
USB VBUS (5V)
    │
    ├──► MCP73831 ──► VBAT (3.7-4.2V, 300mAh LiPo)
    │                    │
    │                    ├──► nRF54LM20B VDDH (internal DC-DC → 1.8V core)
    │                    ├──► DRV2605L VDD (2-5.2V direct)
    │                    └──► AP2112K-1.8 LDO ──► 1.8V ──► MAX86178
    │
    └──► nRF USB_DP/DN (data only, powered from VBAT)
```

**Estimated power budget:**

| Subsystem | Active | Sleep |
|---|---|---|
| nRF54LM20B (BLE TX) | 4.8mA | 0.8uA |
| nRF54LM20B (CPU+NPU) | ~15mA | — |
| MAX86178 (PPG+BioZ) | ~1mA | 0.7uA |
| ICS-43434 x2 | ~1mA | 0.5uA |
| DRV2605L (idle) | ~0.3mA | — |
| DRV2605L (haptic burst) | ~300mA peak | — |
| LDO quiescent | 0.055mA | — |
| **Total active** | **~22mA** | **~2uA** |

At 22mA average, 300mAh battery = ~13 hours active. With duty cycling (mic on, sensor sampling every few seconds, BLE periodic advertising), realistic battery life: **24-48 hours**.

---

## PCB Layout Guidelines

### Board Dimensions
- 75mm x 18mm, 2-layer, 1.6mm FR-4
- Rounded corners (2mm radius) for wearable comfort

### Component Placement (top view, left to right)

```
[USB-C][ESD][CHG][BAT_PADS] [MIC1] [XTAL][nRF54LM20B][LDO][MAX86178][DRV2605][BTN][LED] [MIC2]
 x=-33  -31  -25   -30       -25    -10      -5         0      5       15      -15  -12    30
```

### Bottom Side (skin-facing)
- PPG optical window: 2x green LEDs + photodiode at center (x=3-7mm)
- EDA electrodes: 2x exposed copper pads (ENIG), ~15mm spacing
- Acoustic ports: holes under MIC1 and MIC2

### Critical Layout Rules

1. **Antenna keepout:** No copper (any layer) within 5mm of wire antenna connection point. Ground plane cutout on bottom layer under antenna area.

2. **Crystal placement:** Both crystals within 3mm of nRF QFN. Load cap ground returns directly to nRF VSS pad. No signal traces between crystal and nRF.

3. **MAX86178 WLP routing:** 0.4mm pitch WLP requires 75um traces and spaces. Verify fab capability — JLCPCB standard process supports 0.1mm (100um) minimum, so this is marginal. Consider JLCPCB special process or use the MAX86176 (QFN package) as a safer alternative.

4. **Microphone acoustic ports:** 1mm diameter hole through PCB under each mic. No copper within 0.5mm of hole edge. Seal with gasket material in final assembly.

5. **EDA electrode isolation:** BioZ drive/sense traces should be guarded (ground traces on both sides) to minimize capacitive coupling and noise.

6. **USB-C:** Route D+/D- as differential pair, 90 ohm impedance. Keep traces short (<20mm) and length-matched within 0.15mm.

7. **Power routing:** VBAT traces minimum 0.3mm width. GND pour on bottom layer.

8. **I2S bus to MIC2:** This trace runs ~55mm across the board. Use controlled impedance if possible, add series termination (33 ohm) at nRF end for signal integrity at higher sample rates.

---

## Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| MAX86178 WLP49 routing on 2-layer | High | Consider MAX86176 (QFN) as backup. Or use JLCPCB advanced process. |
| Antenna matching without VNA | Medium | Use Nordic reference design values. Tune in production with VNA. |
| nRF54LM20B not yet generally available | Medium | Pin-compatible with nRF54LM20A (same package, no NPU). Design for both. |
| EDA signal quality | Medium | Proper electrode surface finish (ENIG), guarded traces, BioZ calibration in firmware. |
| I2S signal integrity over 55mm | Low | 33 ohm series resistor, ground return path underneath. Works at I2S rates. |
| Thermal: MCP73831 @ 500mA | Low | Adequate copper pour. Consider reducing to 250mA (R_PROG=4k) if thermal issues. |

---

## Production Notes

- **Fab:** JLCPCB 2-layer, 1.6mm FR-4, ENIG finish (required for EDA electrodes and WLP)
- **Assembly:** JLCPCB SMT assembly for standard parts. MAX86178 WLP may require specialized placement.
- **Battery:** Solder LiPo pouch cell to pads. Alternatively use 2-pin JST connector (adds height).
- **Antenna:** Solder 30mm wire to antenna pad post-assembly.
- **LRA motor:** Attach with adhesive, solder leads to M1 pads.
- **Enclosure:** Design for skin contact on bottom side. Acoustic ports for mics. Button/LED access on top.

---

## Files Generated by MCP Server

| File | Content |
|---|---|
| `circuit.json` | Full Circuit JSON (1313 elements) — importable to tscircuit viewer |
| `circuit.tsx` | tscircuit TSX source (160 lines) — editable and re-renderable |
| `bom.csv` | Bill of Materials (46 entries) |
| `bom.json` | BOM in JSON format |
| `gerbers/` | 11 Gerber + drill files (board outline, copper, mask, silk, paste, drills) |
| `board.svg` | SVG board preview |
| `netlist.spice` | SPICE netlist |
| `pick-and-place.csv` | Component placement data |
| `design-state.json` | Full design state for resuming in MCP server |

**Routing status:** 0% (autorouter cannot handle 46 components / 110 nets on 2 layers). Board requires manual routing in KiCad or use of Freerouting. The netlist, BOM, and component placement are correct and usable as a starting point.
