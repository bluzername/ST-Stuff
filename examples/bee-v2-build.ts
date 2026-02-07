/**
 * Bee v2: BLE Wearable with PPG+EDA, Dual Mics, Vibration Motor
 *
 * Board: 75mm x 18mm, 2-layer
 * SoC: nRF54LM20B (QFN52, 6x6mm) — BLE + NPU for on-device inference
 * Sensor AFE: MAX86178 (WLP49) — PPG + BioZ (EDA)
 * Microphones: 2x ICS-43434 (I2S) — placed 55-60mm apart for beamforming
 * Haptics: DRV2605L + LRA motor
 * Power: MCP73831 LiPo charger + 300mAh battery via USB-C
 *
 * This script builds the design using the pcb-mcp-server CircuitManager
 * to generate the netlist, BOM, layout, and all export artifacts.
 */

import { CircuitManager } from "../src/engine/circuit-manager.js";
import {
  exportGerbers,
  writeGerberZip,
  exportBomCsv,
  exportBomJson,
  exportSvg,
  exportSpiceNetlist,
  exportPickAndPlaceCsv,
  exportCircuitJson,
} from "../src/engine/export-pipeline.js";
import {
  calculateBoardStats,
  runBasicDrc,
} from "../src/engine/circuit-json-utils.js";
import * as fs from "node:fs";

async function main() {
  const m = new CircuitManager();

  // =========================================================================
  //  PROJECT SETUP
  // =========================================================================
  m.createProject("bee-v2", 75, 18, 2,
    "BLE wearable: PPG+EDA sensor, dual mics for ambient transcription, haptic feedback");

  m.setDesignRules({
    min_trace_width_mm: 0.127,
    min_clearance_mm: 0.127,
    min_via_diameter_mm: 0.5,
    min_via_drill_mm: 0.3,
    preset: "jlcpcb_2layer",
  });

  // =========================================================================
  //  COMPONENT PLACEMENT
  //  Board layout (top view, 75mm x 18mm):
  //  [USB-C][Charge][MIC1]---[nRF54LM20B][MAX86178][DRV2605]---[MIC2]
  //   Left end                    Center                      Right end
  //  Mic spacing: ~55mm (MIC1 at x=-25, MIC2 at x=+30)
  // =========================================================================

  // --- nRF54LM20B: Main SoC (QFN52, 6x6mm) ---
  // Center of board, offset slightly left to balance routing
  m.addComponent("chip", "U1", {
    pinLabels: JSON.stringify({
      // Power
      pin1: "VDD", pin2: "VSS", pin3: "DCC", pin4: "VDDH",
      // Radio
      pin5: "ANT", pin6: "XC1", pin7: "XC2",
      // Low-frequency crystal
      pin8: "XL1", pin9: "XL2",
      // USB
      pin10: "USB_DP", pin11: "USB_DN",
      // I2S bus (shared by both mics)
      pin12: "I2S_SCK", pin13: "I2S_LRCK", pin14: "I2S_SDIN",
      // SPI to MAX86178
      pin15: "SPI_SCK", pin16: "SPI_MOSI", pin17: "SPI_MISO", pin18: "SPI_CS",
      // I2C bus (shared: DRV2605L)
      pin19: "I2C_SDA", pin20: "I2C_SCL",
      // GPIO
      pin21: "GPIO_INT_AFE",   // MAX86178 interrupt
      pin22: "GPIO_EN_HAPTIC", // DRV2605L enable
      pin23: "GPIO_BTN",       // User button
      pin24: "GPIO_LED",       // Status LED
      pin25: "GPIO_CHRG_STAT", // MCP73831 charge status
      // Additional power/ground
      pin26: "VDD2", pin27: "VSS2", pin28: "VSS3",
      // Remaining GPIOs for expansion
      pin29: "IO0", pin30: "IO1", pin31: "IO2", pin32: "IO3",
    }),
    schematicSymbolName: "box",
  }, "qfp32", -5, 0);

  // --- MAX86178: PPG + ECG + BioZ AFE (represented as generic IC) ---
  // The actual WLP49 (2.77x2.57mm) is not in tscircuit's library.
  // Using a generic chip representation with key interface pins.
  m.addComponent("chip", "U2", {
    pinLabels: JSON.stringify({
      pin1: "VDD18",     // 1.8V power
      pin2: "VSS",       // Ground
      pin3: "SCLK",      // SPI clock
      pin4: "SDI",       // SPI data in (MOSI)
      pin5: "SDO",       // SPI data out (MISO)
      pin6: "CSB",       // SPI chip select (active low)
      pin7: "INTB",      // Interrupt output (active low)
      pin8: "LED_DRV1",  // LED driver 1 (green LED for PPG)
      pin9: "LED_DRV2",  // LED driver 2 (green LED for PPG)
      pin10: "PD_INP",   // Photodiode input positive
      pin11: "PD_INN",   // Photodiode input negative
      pin12: "BIP",      // BioZ drive positive (EDA electrode)
      pin13: "BIN",      // BioZ drive negative (EDA electrode)
      pin14: "BIOZ_OUT", // BioZ sense output
    }),
    schematicSymbolName: "box",
  }, "soic14", 5, 0);

  // --- DRV2605L: Haptic Driver (VSSOP-10 represented as generic) ---
  m.addComponent("chip", "U3", {
    pinLabels: JSON.stringify({
      pin1: "REG",      // 1.8V regulator output (cap needed)
      pin2: "SCL",      // I2C clock
      pin3: "SDA",      // I2C data
      pin4: "IN_TRIG",  // PWM/analog/trigger input
      pin5: "EN",       // Enable (active high)
      pin6: "VDD",      // Power supply (2-5.2V)
      pin7: "OUTP",     // Motor output positive
      pin8: "GND",      // Ground
      pin9: "OUTN",     // Motor output negative
      pin10: "VDD2",    // Power supply
    }),
    schematicSymbolName: "box",
  }, "soic8", 15, 0);

  // --- MCP73831: LiPo Charge Controller (SOT-23-5) ---
  m.addComponent("chip", "U4", {
    pinLabels: JSON.stringify({
      pin1: "STAT",  // Charge status output
      pin2: "VSS",   // Ground
      pin3: "VBAT",  // Battery positive
      pin4: "VDD",   // USB VBUS input
      pin5: "PROG",  // Charge current programming
    }),
    schematicSymbolName: "box",
  }, "sot23", -25, 4);

  // --- AP2112K-1.8: 1.8V LDO for MAX86178 (SOT-23-5) ---
  m.addComponent("chip", "U5", {
    pinLabels: JSON.stringify({
      pin1: "VIN",  // Input (from VBAT)
      pin2: "GND",  // Ground
      pin3: "EN",   // Enable
      pin4: "NC",   // No connect
      pin5: "VOUT", // 1.8V output
    }),
    schematicSymbolName: "box",
  }, "sot23", 0, -5);

  // --- USB-C Connector (6-pin simplified) ---
  m.addComponent("chip", "J1", {
    pinLabels: JSON.stringify({
      pin1: "GND",
      pin2: "VBUS",
      pin3: "CC1",
      pin4: "CC2",
      pin5: "DP",
      pin6: "DN",
    }),
    schematicSymbolName: "box",
  }, "pinrow6", -33, 0);

  // --- Microphone 1 (left end, near USB-C) ---
  // ICS-43434: I2S digital MEMS mic, bottom port
  m.addComponent("chip", "MIC1", {
    pinLabels: JSON.stringify({
      pin1: "VDD",
      pin2: "GND",
      pin3: "LR_SEL",  // Low = Left channel
      pin4: "SCK",      // I2S bit clock
      pin5: "WS",       // I2S word select (LRCK)
      pin6: "SD",       // I2S data output
    }),
    schematicSymbolName: "box",
  }, "sot23", -25, -4);

  // --- Microphone 2 (right end, ~55mm from MIC1) ---
  m.addComponent("chip", "MIC2", {
    pinLabels: JSON.stringify({
      pin1: "VDD",
      pin2: "GND",
      pin3: "LR_SEL",  // High = Right channel
      pin4: "SCK",      // I2S bit clock
      pin5: "WS",       // I2S word select (LRCK)
      pin6: "SD",       // I2S data output
    }),
    schematicSymbolName: "box",
  }, "sot23", 30, -4);

  // --- PPG Optical Components (bottom side, skin-facing) ---
  // Green LEDs driven by MAX86178
  m.addComponent("led", "LED_PPG1", { color: "green" }, "0603", 3, 5);
  m.addComponent("led", "LED_PPG2", { color: "green" }, "0603", 7, 5);

  // --- Photodiode for PPG ---
  m.addComponent("diode", "PD1", {}, "0805", 5, 7);

  // --- LRA Vibration Motor (external, pads on board) ---
  m.addComponent("chip", "M1", {
    pinLabels: JSON.stringify({ pin1: "PLUS", pin2: "MINUS" }),
    schematicSymbolName: "box",
  }, "pinrow2", 20, 5);

  // --- User Button ---
  m.addComponent("chip", "SW1", {
    pinLabels: JSON.stringify({ pin1: "A", pin2: "B" }),
    schematicSymbolName: "box",
  }, "pinrow2", -15, 6);

  // --- Status LED ---
  m.addComponent("led", "LED1", { color: "blue" }, "0402", -12, 6);
  m.addComponent("resistor", "R_LED", { resistance: "330" }, "0402", -10, 6);

  // --- Battery Pads ---
  m.addComponent("chip", "BAT1", {
    pinLabels: JSON.stringify({ pin1: "VBAT", pin2: "GND" }),
    schematicSymbolName: "box",
  }, "pinrow2", -30, -6);

  // --- 32 MHz Crystal (for nRF) ---
  m.addComponent("crystal", "Y1", { frequency: "32MHz", loadCapacitance: "12pF" }, "0805", -10, -5);

  // --- 32.768 kHz Crystal (for RTC) ---
  m.addComponent("crystal", "Y2", { frequency: "32.768kHz", loadCapacitance: "15pF" }, "0603", -8, -5);

  // =========================================================================
  //  PASSIVE COMPONENTS
  // =========================================================================

  // USB-C CC pull-down resistors (5.1k each)
  m.addComponent("resistor", "R_CC1", { resistance: "5.1k" }, "0402", -30, 4);
  m.addComponent("resistor", "R_CC2", { resistance: "5.1k" }, "0402", -30, -4);

  // Charge current programming resistor (2k = 500mA charge)
  m.addComponent("resistor", "R_PROG", { resistance: "2k" }, "0402", -23, 7);

  // nRF decoupling caps
  m.addComponent("capacitor", "C1", { capacitance: "100nF" }, "0402", -8, 3);
  m.addComponent("capacitor", "C2", { capacitance: "100nF" }, "0402", -3, 3);
  m.addComponent("capacitor", "C3", { capacitance: "4.7uF" }, "0402", -5, -3);
  // DC-DC inductor filter cap
  m.addComponent("capacitor", "C4", { capacitance: "1uF" }, "0402", -2, -3);

  // MAX86178 decoupling
  m.addComponent("capacitor", "C5", { capacitance: "100nF" }, "0402", 3, -3);
  m.addComponent("capacitor", "C6", { capacitance: "1uF" }, "0402", 7, -3);

  // DRV2605L decoupling + regulator cap
  m.addComponent("capacitor", "C7", { capacitance: "1uF" }, "0402", 13, 3);
  m.addComponent("capacitor", "C8", { capacitance: "1uF" }, "0402", 17, 3);

  // MCP73831 input/output caps
  m.addComponent("capacitor", "C9", { capacitance: "4.7uF" }, "0805", -27, 7);
  m.addComponent("capacitor", "C10", { capacitance: "4.7uF" }, "0805", -22, 7);

  // LDO input/output caps
  m.addComponent("capacitor", "C11", { capacitance: "1uF" }, "0402", -2, -7);
  m.addComponent("capacitor", "C12", { capacitance: "1uF" }, "0402", 2, -7);

  // Mic decoupling
  m.addComponent("capacitor", "C13", { capacitance: "100nF" }, "0402", -23, -4);
  m.addComponent("capacitor", "C14", { capacitance: "100nF" }, "0402", 28, -4);

  // Crystal load caps (32MHz)
  m.addComponent("capacitor", "C15", { capacitance: "12pF" }, "0402", -12, -7);
  m.addComponent("capacitor", "C16", { capacitance: "12pF" }, "0402", -8, -7);

  // Crystal load caps (32.768kHz)
  m.addComponent("capacitor", "C17", { capacitance: "15pF" }, "0402", -7, -7);
  m.addComponent("capacitor", "C18", { capacitance: "15pF" }, "0402", -9, -7);

  // USB ESD protection
  m.addComponent("diode", "D_ESD", {}, "sot23", -31, -3);

  // Antenna matching network (pi-match for 2.4GHz)
  m.addComponent("inductor", "L_ANT", { inductance: "3.9nH" }, "0402", -13, 0);
  m.addComponent("capacitor", "C_ANT1", { capacitance: "1.5pF" }, "0402", -15, -2);
  m.addComponent("capacitor", "C_ANT2", { capacitance: "1pF" }, "0402", -11, -2);

  // DC-DC inductor for nRF
  m.addComponent("inductor", "L1", { inductance: "10uH" }, "0402", -4, -5);

  // Mic LR select pull-down/pull-up
  m.addComponent("resistor", "R_LR1", { resistance: "0" }, "0402", -24, -6); // MIC1 = Low (left)
  m.addComponent("resistor", "R_LR2", { resistance: "10k" }, "0402", 29, -6); // MIC2 = High (right)

  // =========================================================================
  //  TRACE CONNECTIONS (ELECTRICAL NETLIST)
  // =========================================================================

  // --- USB-C Power Path ---
  m.addTrace(".J1 > .VBUS", ".U4 > .VDD");       // USB VBUS to charger input
  m.addTrace(".J1 > .GND", ".U4 > .VSS");         // USB GND
  m.addTrace(".J1 > .CC1", ".R_CC1 > .pin1");     // CC1 pull-down
  m.addTrace(".R_CC1 > .pin2", ".U4 > .VSS");
  m.addTrace(".J1 > .CC2", ".R_CC2 > .pin1");     // CC2 pull-down
  m.addTrace(".R_CC2 > .pin2", ".U4 > .VSS");

  // USB data to nRF
  m.addTrace(".J1 > .DP", ".U1 > .USB_DP");
  m.addTrace(".J1 > .DN", ".U1 > .USB_DN");

  // USB ESD protection
  m.addTrace(".J1 > .DP", ".D_ESD > .pin1");
  m.addTrace(".D_ESD > .pin2", ".U4 > .VSS");

  // Charger input/output caps
  m.addTrace(".U4 > .VDD", ".C9 > .pin1");
  m.addTrace(".C9 > .pin2", ".U4 > .VSS");
  m.addTrace(".U4 > .VBAT", ".C10 > .pin1");
  m.addTrace(".C10 > .pin2", ".U4 > .VSS");

  // Charge current programming
  m.addTrace(".U4 > .PROG", ".R_PROG > .pin1");
  m.addTrace(".R_PROG > .pin2", ".U4 > .VSS");

  // Charge status to nRF
  m.addTrace(".U4 > .STAT", ".U1 > .GPIO_CHRG_STAT");

  // --- Battery ---
  m.addTrace(".BAT1 > .VBAT", ".U4 > .VBAT");
  m.addTrace(".BAT1 > .GND", ".U4 > .VSS");

  // --- Power Distribution: VBAT to nRF ---
  m.addTrace(".U4 > .VBAT", ".U1 > .VDDH");   // Battery voltage to nRF high-voltage input
  m.addTrace(".U1 > .VSS", ".U4 > .VSS");       // GND

  // nRF decoupling
  m.addTrace(".U1 > .VDD", ".C1 > .pin1");
  m.addTrace(".C1 > .pin2", ".U1 > .VSS");
  m.addTrace(".U1 > .VDD2", ".C2 > .pin1");
  m.addTrace(".C2 > .pin2", ".U1 > .VSS2");
  m.addTrace(".U1 > .VDDH", ".C3 > .pin1");
  m.addTrace(".C3 > .pin2", ".U1 > .VSS");

  // DC-DC converter inductor
  m.addTrace(".U1 > .DCC", ".L1 > .pin1");
  m.addTrace(".L1 > .pin2", ".C4 > .pin1");
  m.addTrace(".C4 > .pin2", ".U1 > .VSS");

  // --- 1.8V LDO for MAX86178 ---
  m.addTrace(".U4 > .VBAT", ".U5 > .VIN");     // LDO input from battery
  m.addTrace(".U5 > .VIN", ".U5 > .EN");        // Enable tied to VIN (always on)
  m.addTrace(".U5 > .GND", ".U4 > .VSS");
  m.addTrace(".U5 > .VOUT", ".U2 > .VDD18");   // 1.8V to MAX86178
  // LDO decoupling
  m.addTrace(".U5 > .VIN", ".C11 > .pin1");
  m.addTrace(".C11 > .pin2", ".U5 > .GND");
  m.addTrace(".U5 > .VOUT", ".C12 > .pin1");
  m.addTrace(".C12 > .pin2", ".U5 > .GND");

  // --- MAX86178 Connections ---
  m.addTrace(".U2 > .VSS", ".U4 > .VSS");       // GND
  // MAX86178 decoupling
  m.addTrace(".U2 > .VDD18", ".C5 > .pin1");
  m.addTrace(".C5 > .pin2", ".U2 > .VSS");
  m.addTrace(".U2 > .VDD18", ".C6 > .pin1");
  m.addTrace(".C6 > .pin2", ".U2 > .VSS");

  // SPI bus: nRF <-> MAX86178
  m.addTrace(".U1 > .SPI_SCK", ".U2 > .SCLK");
  m.addTrace(".U1 > .SPI_MOSI", ".U2 > .SDI");
  m.addTrace(".U1 > .SPI_MISO", ".U2 > .SDO");
  m.addTrace(".U1 > .SPI_CS", ".U2 > .CSB");
  m.addTrace(".U2 > .INTB", ".U1 > .GPIO_INT_AFE");

  // PPG LEDs driven by MAX86178
  m.addTrace(".U2 > .LED_DRV1", ".LED_PPG1 > .pin1");
  m.addTrace(".LED_PPG1 > .pin2", ".U2 > .VSS");
  m.addTrace(".U2 > .LED_DRV2", ".LED_PPG2 > .pin1");
  m.addTrace(".LED_PPG2 > .pin2", ".U2 > .VSS");

  // Photodiode
  m.addTrace(".PD1 > .pin1", ".U2 > .PD_INP");
  m.addTrace(".PD1 > .pin2", ".U2 > .PD_INN");

  // EDA electrodes (BioZ) — exposed copper pads on bottom side
  // These connect to board-edge pads, represented here as traces to the AFE
  // In actual design: copper pads on bottom layer, vias to top layer traces

  // --- DRV2605L Haptic Driver ---
  m.addTrace(".U4 > .VBAT", ".U3 > .VDD");      // Power from battery
  m.addTrace(".U3 > .GND", ".U4 > .VSS");
  m.addTrace(".U3 > .VDD2", ".U3 > .VDD");       // Tie VDD pins
  m.addTrace(".U1 > .I2C_SCL", ".U3 > .SCL");    // I2C
  m.addTrace(".U1 > .I2C_SDA", ".U3 > .SDA");
  m.addTrace(".U1 > .GPIO_EN_HAPTIC", ".U3 > .EN");
  m.addTrace(".U3 > .IN_TRIG", ".U3 > .GND");    // Unused, tie to GND

  // DRV2605L decoupling
  m.addTrace(".U3 > .VDD", ".C7 > .pin1");
  m.addTrace(".C7 > .pin2", ".U3 > .GND");
  m.addTrace(".U3 > .REG", ".C8 > .pin1");        // 1.8V regulator output cap
  m.addTrace(".C8 > .pin2", ".U3 > .GND");

  // LRA motor
  m.addTrace(".U3 > .OUTP", ".M1 > .PLUS");
  m.addTrace(".U3 > .OUTN", ".M1 > .MINUS");

  // --- Microphone 1 (Left, I2S) ---
  m.addTrace(".U1 > .VDD", ".MIC1 > .VDD");
  m.addTrace(".MIC1 > .GND", ".U4 > .VSS");
  m.addTrace(".U1 > .I2S_SCK", ".MIC1 > .SCK");
  m.addTrace(".U1 > .I2S_LRCK", ".MIC1 > .WS");
  m.addTrace(".MIC1 > .SD", ".U1 > .I2S_SDIN");
  m.addTrace(".MIC1 > .LR_SEL", ".R_LR1 > .pin1");  // Pull low = left channel
  m.addTrace(".R_LR1 > .pin2", ".MIC1 > .GND");
  // Mic1 decoupling
  m.addTrace(".MIC1 > .VDD", ".C13 > .pin1");
  m.addTrace(".C13 > .pin2", ".MIC1 > .GND");

  // --- Microphone 2 (Right, I2S — shared bus) ---
  m.addTrace(".U1 > .VDD", ".MIC2 > .VDD");
  m.addTrace(".MIC2 > .GND", ".U4 > .VSS");
  m.addTrace(".U1 > .I2S_SCK", ".MIC2 > .SCK");
  m.addTrace(".U1 > .I2S_LRCK", ".MIC2 > .WS");
  m.addTrace(".MIC2 > .SD", ".U1 > .I2S_SDIN");    // Both mics share SDIN (L+R muxed)
  m.addTrace(".MIC2 > .LR_SEL", ".R_LR2 > .pin1"); // Pull high = right channel
  m.addTrace(".R_LR2 > .pin2", ".MIC2 > .VDD");
  // Mic2 decoupling
  m.addTrace(".MIC2 > .VDD", ".C14 > .pin1");
  m.addTrace(".C14 > .pin2", ".MIC2 > .GND");

  // --- 32 MHz Crystal ---
  m.addTrace(".Y1 > .pin1", ".U1 > .XC1");
  m.addTrace(".Y1 > .pin2", ".U1 > .XC2");
  m.addTrace(".Y1 > .pin1", ".C15 > .pin1");
  m.addTrace(".C15 > .pin2", ".U1 > .VSS");
  m.addTrace(".Y1 > .pin2", ".C16 > .pin1");
  m.addTrace(".C16 > .pin2", ".U1 > .VSS");

  // --- 32.768 kHz Crystal ---
  m.addTrace(".Y2 > .pin1", ".U1 > .XL1");
  m.addTrace(".Y2 > .pin2", ".U1 > .XL2");
  m.addTrace(".Y2 > .pin1", ".C17 > .pin1");
  m.addTrace(".C17 > .pin2", ".U1 > .VSS");
  m.addTrace(".Y2 > .pin2", ".C18 > .pin1");
  m.addTrace(".C18 > .pin2", ".U1 > .VSS");

  // --- Antenna Matching Network (Pi-match) ---
  m.addTrace(".U1 > .ANT", ".C_ANT1 > .pin1");
  m.addTrace(".C_ANT1 > .pin2", ".U1 > .VSS");
  m.addTrace(".U1 > .ANT", ".L_ANT > .pin1");
  m.addTrace(".L_ANT > .pin2", ".C_ANT2 > .pin1");
  m.addTrace(".C_ANT2 > .pin2", ".U1 > .VSS");
  // Wire antenna connects to L_ANT output node

  // --- User Button ---
  m.addTrace(".SW1 > .A", ".U1 > .GPIO_BTN");
  m.addTrace(".SW1 > .B", ".U1 > .VSS");

  // --- Status LED ---
  m.addTrace(".U1 > .GPIO_LED", ".R_LED > .pin1");
  m.addTrace(".R_LED > .pin2", ".LED1 > .pin1");
  m.addTrace(".LED1 > .pin2", ".U1 > .VSS");

  // --- Master GND connections ---
  m.addTrace(".U1 > .VSS2", ".U1 > .VSS");
  m.addTrace(".U1 > .VSS3", ".U1 > .VSS");
  m.addTrace(".U3 > .GND", ".U1 > .VSS");

  // =========================================================================
  //  RENDER & EXPORT
  // =========================================================================

  console.log("=== Bee v2 Design Build ===\n");
  console.log("Rendering circuit...");
  const renderResult = await m.render();
  console.log(`Render: ${renderResult.success ? "OK" : "FAIL"}`);
  if (renderResult.errors) {
    const nonSupplierErrors = renderResult.errors.filter(
      (e: string) => !e.includes("fetch") && !e.includes("supplier")
    );
    if (nonSupplierErrors.length > 0) {
      console.log(`Real errors: ${nonSupplierErrors.length}`);
      for (const e of nonSupplierErrors) console.log(`  - ${e}`);
    }
  }

  const cj = m.getCircuitJson();
  const stats = calculateBoardStats(cj);
  const drc = runBasicDrc(cj, 0.127, 0.127);
  const realDrcErrors = drc.filter(v => v.severity === "error");
  const drcWarnings = drc.filter(v => v.severity === "warning");

  console.log(`\n--- Board Statistics ---`);
  console.log(`Components: ${stats.component_count}`);
  console.log(`Nets/Traces: ${stats.net_count}`);
  console.log(`PCB Traces routed: ${stats.trace_count}`);
  console.log(`Routing completion: ${stats.routing_completion_pct}%`);
  console.log(`Board area: ${stats.board_area_mm2} mm² (75x18mm)`);
  console.log(`DRC errors: ${realDrcErrors.length}`);
  console.log(`DRC warnings: ${drcWarnings.length}`);
  console.log(`Circuit JSON elements: ${stats.element_count || cj.length}`);

  // Export directory
  const outDir = "/tmp/pcb-exports/bee-v2";
  fs.mkdirSync(outDir, { recursive: true });

  // Gerbers
  console.log(`\n--- Exporting ---`);
  try {
    const gerbers = exportGerbers(cj);
    writeGerberZip(gerbers, `${outDir}/gerbers`);
    console.log(`Gerbers: ${gerbers.file_count} files → ${outDir}/gerbers/`);
  } catch (e: any) {
    console.log(`Gerbers: FAILED (${e.message})`);
  }

  // BOM
  const bomCsv = exportBomCsv(cj);
  fs.writeFileSync(`${outDir}/bom.csv`, bomCsv);
  console.log(`BOM CSV: ${bomCsv.split("\n").length - 1} entries → ${outDir}/bom.csv`);

  const bomJson = exportBomJson(cj);
  fs.writeFileSync(`${outDir}/bom.json`, bomJson);
  console.log(`BOM JSON: → ${outDir}/bom.json`);

  // SVG
  const svg = exportSvg(cj);
  fs.writeFileSync(`${outDir}/board.svg`, svg);
  console.log(`SVG: ${svg.length} bytes → ${outDir}/board.svg`);

  // SPICE
  const spice = exportSpiceNetlist(cj);
  fs.writeFileSync(`${outDir}/netlist.spice`, spice);
  console.log(`SPICE netlist: → ${outDir}/netlist.spice`);

  // Pick and Place
  const pnp = exportPickAndPlaceCsv(cj);
  fs.writeFileSync(`${outDir}/pick-and-place.csv`, pnp);
  console.log(`Pick & Place: → ${outDir}/pick-and-place.csv`);

  // Circuit JSON
  const circuitJsonStr = exportCircuitJson(cj);
  fs.writeFileSync(`${outDir}/circuit.json`, circuitJsonStr);
  console.log(`Circuit JSON: ${cj.length} elements → ${outDir}/circuit.json`);

  // TSX source
  const tsx = m.getTsxSource();
  fs.writeFileSync(`${outDir}/circuit.tsx`, tsx);
  console.log(`TSX source: ${tsx.split("\n").length} lines → ${outDir}/circuit.tsx`);

  // Full state
  const state = m.getState();
  fs.writeFileSync(`${outDir}/design-state.json`, JSON.stringify(state, null, 2));
  console.log(`Design state: → ${outDir}/design-state.json`);

  // BOM summary
  console.log(`\n--- BOM Summary ---`);
  console.log(bomCsv);

  console.log(`\n--- DRC Summary ---`);
  for (const v of realDrcErrors.slice(0, 10)) {
    console.log(`  [ERROR] ${v.type}: ${v.message}`);
  }
  for (const v of drcWarnings.slice(0, 5)) {
    console.log(`  [WARN] ${v.type}: ${v.message}`);
  }
  if (realDrcErrors.length > 10) {
    console.log(`  ... and ${realDrcErrors.length - 10} more errors`);
  }

  console.log(`\n=== Build Complete ===`);
  console.log(`All artifacts exported to: ${outDir}/`);
}

main().catch((err) => {
  console.error("Build failed:", err);
  process.exit(1);
});
