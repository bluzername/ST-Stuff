/**
 * Benchmark Runner: Executes all three test cases and generates a comparison report.
 */

import { CircuitManager } from "../../src/engine/circuit-manager.js";
import {
  exportGerbers,
  writeGerberZip,
  exportBomCsv,
  exportSvg,
} from "../../src/engine/export-pipeline.js";
import {
  calculateBoardStats,
  runBasicDrc,
} from "../../src/engine/circuit-json-utils.js";
import * as fs from "node:fs";
import * as path from "node:path";

interface BenchmarkResult {
  name: string;
  components_added: number;
  traces_added: number;
  tool_calls: number;
  render_success: boolean;
  render_errors: string[];
  drc_violations: number;
  drc_errors: number;
  drc_warnings: number;
  routing_completion_pct: number;
  board_area_mm2: number;
  gerber_export_success: boolean;
  gerber_file_count: number;
  bom_entries: number;
  svg_generated: boolean;
  circuit_json_elements: number;
  elapsed_ms: number;
}

async function runTestCase1(): Promise<BenchmarkResult> {
  const start = Date.now();
  const m = new CircuitManager();
  let toolCalls = 0;

  // Create project: LED Blinker with ATtiny85
  m.createProject("led-blinker", 25, 20, 2, "ATtiny85 LED blinker circuit");
  toolCalls++;

  // ATtiny85 in DIP-8
  m.addComponent(
    "chip",
    "U1",
    {
      pinLabels: JSON.stringify({
        pin1: "RST",
        pin2: "PB3",
        pin3: "PB4",
        pin4: "GND",
        pin5: "PB0",
        pin6: "PB1",
        pin7: "PB2",
        pin8: "VCC",
      }),
      schematicSymbolName: "box",
    },
    "dip8",
    0,
    0
  );
  toolCalls++;

  // LED (0805 red)
  m.addComponent("led", "LED1", { color: "red" }, "0805", 8, 0);
  toolCalls++;

  // 330 ohm resistor for LED
  m.addComponent("resistor", "R1", { resistance: "330" }, "0805", 5, 3);
  toolCalls++;

  // 100nF decoupling cap
  m.addComponent("capacitor", "C1", { capacitance: "100nF" }, "0402", -3, -3);
  toolCalls++;

  // 2-pin power header
  m.addComponent(
    "chip",
    "J1",
    {
      pinLabels: JSON.stringify({ pin1: "VCC", pin2: "GND" }),
      schematicSymbolName: "box",
    },
    "pinrow2",
    -8,
    0
  );
  toolCalls++;

  // Traces
  // Power: J1.VCC -> U1.VCC, J1.GND -> U1.GND
  m.addTrace(".J1 > .VCC", ".U1 > .VCC");
  toolCalls++;
  m.addTrace(".J1 > .GND", ".U1 > .GND");
  toolCalls++;

  // Decoupling: C1 across power
  m.addTrace(".C1 > .pin1", ".U1 > .VCC");
  toolCalls++;
  m.addTrace(".C1 > .pin2", ".U1 > .GND");
  toolCalls++;

  // LED circuit: U1.PB0 -> R1 -> LED -> GND
  m.addTrace(".U1 > .PB0", ".R1 > .pin1");
  toolCalls++;
  m.addTrace(".R1 > .pin2", ".LED1 > .pin1");
  toolCalls++;
  m.addTrace(".LED1 > .pin2", ".U1 > .GND");
  toolCalls++;

  // Render and collect results
  const renderResult = await m.render();
  toolCalls++;

  const cj = m.getCircuitJson();
  const stats = calculateBoardStats(cj);
  const drc = runBasicDrc(cj, 0.15, 0.15);

  let gerberSuccess = false;
  let gerberFiles = 0;
  try {
    const gerbers = exportGerbers(cj);
    const outDir = "/tmp/pcb-exports/benchmark-led-blinker";
    writeGerberZip(gerbers, outDir);
    gerberFiles = gerbers.file_count;
    gerberSuccess = true;
  } catch {}

  const bom = exportBomCsv(cj);
  let svgOk = false;
  try {
    exportSvg(cj);
    svgOk = true;
  } catch {}

  return {
    name: "LED Blinker (ATtiny85)",
    components_added: 5,
    traces_added: 7,
    tool_calls: toolCalls,
    render_success: renderResult.success,
    render_errors: renderResult.errors || [],
    drc_violations: drc.length,
    drc_errors: drc.filter((v) => v.severity === "error").length,
    drc_warnings: drc.filter((v) => v.severity === "warning").length,
    routing_completion_pct: stats.routing_completion_pct,
    board_area_mm2: stats.board_area_mm2,
    gerber_export_success: gerberSuccess,
    gerber_file_count: gerberFiles,
    bom_entries: bom.split("\n").length - 1,
    svg_generated: svgOk,
    circuit_json_elements: cj.length,
    elapsed_ms: Date.now() - start,
  };
}

async function runTestCase2(): Promise<BenchmarkResult> {
  const start = Date.now();
  const m = new CircuitManager();
  let toolCalls = 0;

  m.createProject("usb-c-power", 40, 25, 2, "USB-C power board with 3.3V regulator");
  toolCalls++;

  // USB-C connector (simplified as 16-pin chip)
  m.addComponent(
    "chip",
    "J1",
    {
      pinLabels: JSON.stringify({
        pin1: "GND1",
        pin2: "TX1P",
        pin3: "TX1N",
        pin4: "VBUS1",
        pin5: "CC1",
        pin6: "DP1",
        pin7: "DN1",
        pin8: "SBU1",
        pin9: "VBUS2",
        pin10: "SBU2",
        pin11: "DN2",
        pin12: "DP2",
        pin13: "CC2",
        pin14: "VBUS3",
        pin15: "TX2P",
        pin16: "TX2N",
      }),
      schematicSymbolName: "box",
    },
    "soic16",
    -14,
    0
  );
  toolCalls++;

  // AMS1117-3.3 voltage regulator (SOT-223: GND, VOUT, VIN)
  m.addComponent(
    "chip",
    "U1",
    {
      pinLabels: JSON.stringify({ pin1: "GND", pin2: "VOUT", pin3: "VIN" }),
      schematicSymbolName: "box",
    },
    "sot223",
    0,
    0
  );
  toolCalls++;

  // Input bulk cap 10uF
  m.addComponent("capacitor", "C1", { capacitance: "10uF" }, "0805", -5, -5);
  toolCalls++;

  // Output bulk cap 10uF
  m.addComponent("capacitor", "C2", { capacitance: "10uF" }, "0805", 5, -5);
  toolCalls++;

  // 4x 100nF decoupling caps
  m.addComponent("capacitor", "C3", { capacitance: "100nF" }, "0402", -3, 5);
  toolCalls++;
  m.addComponent("capacitor", "C4", { capacitance: "100nF" }, "0402", 3, 5);
  toolCalls++;
  m.addComponent("capacitor", "C5", { capacitance: "100nF" }, "0402", -8, 5);
  toolCalls++;
  m.addComponent("capacitor", "C6", { capacitance: "100nF" }, "0402", 8, 5);
  toolCalls++;

  // Power LED + resistor
  m.addComponent("led", "LED1", { color: "green" }, "0805", 12, 3);
  toolCalls++;
  m.addComponent("resistor", "R1", { resistance: "1k" }, "0805", 12, -3);
  toolCalls++;

  // CC pull-down resistors
  m.addComponent("resistor", "R2", { resistance: "5.1k" }, "0402", -10, -5);
  toolCalls++;
  m.addComponent("resistor", "R3", { resistance: "5.1k" }, "0402", -10, 5);
  toolCalls++;

  // TVS diode for ESD
  m.addComponent("diode", "D1", {}, "sot23", -14, -8);
  toolCalls++;

  // Output header (6-pin)
  m.addComponent(
    "chip",
    "J2",
    {
      pinLabels: JSON.stringify({
        pin1: "3V3",
        pin2: "3V3",
        pin3: "GND",
        pin4: "GND",
        pin5: "5V",
        pin6: "5V",
      }),
      schematicSymbolName: "box",
    },
    "pinrow6",
    16,
    0
  );
  toolCalls++;

  // Key traces
  // USB VBUS -> TVS -> input cap -> regulator VIN
  m.addTrace(".J1 > .VBUS1", ".D1 > .pin1");
  toolCalls++;
  m.addTrace(".D1 > .pin2", ".U1 > .VIN");
  toolCalls++;
  m.addTrace(".U1 > .VIN", ".C1 > .pin1");
  toolCalls++;

  // Regulator output
  m.addTrace(".U1 > .VOUT", ".C2 > .pin1");
  toolCalls++;
  m.addTrace(".U1 > .VOUT", ".J2 > .3V3");
  toolCalls++;

  // USB VBUS to 5V output
  m.addTrace(".J1 > .VBUS2", ".J2 > .5V");
  toolCalls++;

  // CC resistors
  m.addTrace(".J1 > .CC1", ".R2 > .pin1");
  toolCalls++;
  m.addTrace(".J1 > .CC2", ".R3 > .pin1");
  toolCalls++;

  // Power LED
  m.addTrace(".U1 > .VOUT", ".R1 > .pin1");
  toolCalls++;
  m.addTrace(".R1 > .pin2", ".LED1 > .pin1");
  toolCalls++;

  // GND connections
  m.addTrace(".U1 > .GND", ".C1 > .pin2");
  toolCalls++;
  m.addTrace(".U1 > .GND", ".C2 > .pin2");
  toolCalls++;
  m.addTrace(".U1 > .GND", ".J2 > .GND");
  toolCalls++;
  m.addTrace(".R2 > .pin2", ".U1 > .GND");
  toolCalls++;
  m.addTrace(".R3 > .pin2", ".U1 > .GND");
  toolCalls++;
  m.addTrace(".LED1 > .pin2", ".U1 > .GND");
  toolCalls++;
  m.addTrace(".J1 > .GND1", ".U1 > .GND");
  toolCalls++;

  const renderResult = await m.render();
  toolCalls++;

  const cj = m.getCircuitJson();
  const stats = calculateBoardStats(cj);
  const drc = runBasicDrc(cj, 0.127, 0.127);

  let gerberSuccess = false;
  let gerberFiles = 0;
  try {
    const gerbers = exportGerbers(cj);
    writeGerberZip(gerbers, "/tmp/pcb-exports/benchmark-usb-c-power");
    gerberFiles = gerbers.file_count;
    gerberSuccess = true;
  } catch {}

  const bom = exportBomCsv(cj);
  let svgOk = false;
  try {
    exportSvg(cj);
    svgOk = true;
  } catch {}

  return {
    name: "USB-C Power Board",
    components_added: 14,
    traces_added: 17,
    tool_calls: toolCalls,
    render_success: renderResult.success,
    render_errors: renderResult.errors || [],
    drc_violations: drc.length,
    drc_errors: drc.filter((v) => v.severity === "error").length,
    drc_warnings: drc.filter((v) => v.severity === "warning").length,
    routing_completion_pct: stats.routing_completion_pct,
    board_area_mm2: stats.board_area_mm2,
    gerber_export_success: gerberSuccess,
    gerber_file_count: gerberFiles,
    bom_entries: bom.split("\n").length - 1,
    svg_generated: svgOk,
    circuit_json_elements: cj.length,
    elapsed_ms: Date.now() - start,
  };
}

async function runTestCase3(): Promise<BenchmarkResult> {
  const start = Date.now();
  const m = new CircuitManager();
  let toolCalls = 0;

  m.createProject("esp32-sensor-node", 50, 35, 2, "ESP32 sensor node with BME280");
  toolCalls++;

  // ESP32-WROOM-32 module (simplified)
  m.addComponent(
    "chip",
    "U1",
    {
      pinLabels: JSON.stringify({
        pin1: "GND",
        pin2: "3V3",
        pin3: "EN",
        pin4: "IO36",
        pin5: "IO39",
        pin6: "IO34",
        pin7: "IO35",
        pin8: "IO32",
        pin9: "IO33",
        pin10: "IO25",
        pin11: "IO26",
        pin12: "IO27",
        pin13: "IO14",
        pin14: "IO12",
        pin15: "IO13",
        pin16: "IO15",
        pin17: "IO2",
        pin18: "IO0",
        pin19: "IO4",
        pin20: "IO16",
        pin21: "IO17",
        pin22: "IO5",
        pin23: "IO18",
        pin24: "IO19",
        pin25: "IO21",
        pin26: "RXD0",
        pin27: "TXD0",
        pin28: "IO22",
        pin29: "IO23",
      }),
      schematicSymbolName: "box",
    },
    "qfp32",
    0,
    0
  );
  toolCalls++;

  // CP2102N USB-UART bridge
  m.addComponent(
    "chip",
    "U2",
    {
      pinLabels: JSON.stringify({
        pin1: "DP",
        pin2: "DN",
        pin3: "GND",
        pin4: "VDD",
        pin5: "REGIN",
        pin6: "VBUS",
        pin7: "RST",
        pin8: "NC",
        pin9: "SUSPEND",
        pin10: "TXD",
        pin11: "RXD",
        pin12: "DTR",
        pin13: "RTS",
      }),
      schematicSymbolName: "box",
    },
    "qfn16",
    -18,
    0
  );
  toolCalls++;

  // AMS1117-3.3 regulator
  m.addComponent(
    "chip",
    "U3",
    {
      pinLabels: JSON.stringify({ pin1: "GND", pin2: "VOUT", pin3: "VIN" }),
      schematicSymbolName: "box",
    },
    "sot223",
    -18,
    -10
  );
  toolCalls++;

  // BME280 sensor
  m.addComponent(
    "chip",
    "U4",
    {
      pinLabels: JSON.stringify({
        pin1: "GND",
        pin2: "CSB",
        pin3: "SDI",
        pin4: "SCK",
        pin5: "SDO",
        pin6: "VDDIO",
        pin7: "GND2",
        pin8: "VDD",
      }),
      schematicSymbolName: "box",
    },
    "soic8",
    18,
    -5
  );
  toolCalls++;

  // USB-C connector
  m.addComponent(
    "chip",
    "J1",
    {
      pinLabels: JSON.stringify({
        pin1: "GND",
        pin2: "VBUS",
        pin3: "CC1",
        pin4: "CC2",
        pin5: "DP",
        pin6: "DN",
      }),
      schematicSymbolName: "box",
    },
    "pinrow6",
    -22,
    10
  );
  toolCalls++;

  // Boot/Reset buttons
  m.addComponent(
    "chip",
    "SW1",
    {
      pinLabels: JSON.stringify({ pin1: "A", pin2: "B" }),
      schematicSymbolName: "box",
    },
    "pinrow2",
    10,
    12
  );
  toolCalls++;
  m.addComponent(
    "chip",
    "SW2",
    {
      pinLabels: JSON.stringify({ pin1: "A", pin2: "B" }),
      schematicSymbolName: "box",
    },
    "pinrow2",
    15,
    12
  );
  toolCalls++;

  // Capacitors
  m.addComponent("capacitor", "C1", { capacitance: "10uF" }, "0805", -15, -13);
  toolCalls++;
  m.addComponent("capacitor", "C2", { capacitance: "10uF" }, "0805", -12, -13);
  toolCalls++;
  m.addComponent("capacitor", "C3", { capacitance: "100nF" }, "0402", -5, -8);
  toolCalls++;
  m.addComponent("capacitor", "C4", { capacitance: "100nF" }, "0402", 5, -8);
  toolCalls++;
  m.addComponent("capacitor", "C5", { capacitance: "100nF" }, "0402", -18, 5);
  toolCalls++;
  m.addComponent("capacitor", "C6", { capacitance: "100nF" }, "0402", 20, -8);
  toolCalls++;

  // Resistors
  m.addComponent("resistor", "R1", { resistance: "10k" }, "0402", 5, 10);
  toolCalls++;
  m.addComponent("resistor", "R2", { resistance: "10k" }, "0402", 8, 10);
  toolCalls++;
  m.addComponent("resistor", "R3", { resistance: "4.7k" }, "0402", 15, -10);
  toolCalls++;
  m.addComponent("resistor", "R4", { resistance: "4.7k" }, "0402", 18, -10);
  toolCalls++;
  m.addComponent("resistor", "R5", { resistance: "5.1k" }, "0402", -20, 5);
  toolCalls++;
  m.addComponent("resistor", "R6", { resistance: "5.1k" }, "0402", -20, 8);
  toolCalls++;

  // RGB LED (WS2812B simplified)
  m.addComponent("led", "LED1", { color: "rgb" }, "0805", 0, 12);
  toolCalls++;

  // 2x20 header breakout
  m.addComponent(
    "chip",
    "J2",
    {
      pinLabels: JSON.stringify({
        pin1: "3V3",
        pin2: "GND",
        pin3: "IO32",
        pin4: "IO33",
        pin5: "IO25",
        pin6: "IO26",
      }),
      schematicSymbolName: "box",
    },
    "pinrow6",
    22,
    5
  );
  toolCalls++;

  // Key connections
  // USB to UART bridge
  m.addTrace(".J1 > .DP", ".U2 > .DP");
  toolCalls++;
  m.addTrace(".J1 > .DN", ".U2 > .DN");
  toolCalls++;
  m.addTrace(".U2 > .TXD", ".U1 > .RXD0");
  toolCalls++;
  m.addTrace(".U2 > .RXD", ".U1 > .TXD0");
  toolCalls++;

  // Power chain
  m.addTrace(".J1 > .VBUS", ".U3 > .VIN");
  toolCalls++;
  m.addTrace(".U3 > .VOUT", ".U1 > .3V3");
  toolCalls++;
  m.addTrace(".U3 > .VOUT", ".U4 > .VDD");
  toolCalls++;
  m.addTrace(".U3 > .VOUT", ".U4 > .VDDIO");
  toolCalls++;

  // Decoupling
  m.addTrace(".U3 > .VIN", ".C1 > .pin1");
  toolCalls++;
  m.addTrace(".U3 > .VOUT", ".C2 > .pin1");
  toolCalls++;
  m.addTrace(".C1 > .pin2", ".U3 > .GND");
  toolCalls++;
  m.addTrace(".C2 > .pin2", ".U3 > .GND");
  toolCalls++;
  m.addTrace(".U1 > .3V3", ".C3 > .pin1");
  toolCalls++;
  m.addTrace(".C3 > .pin2", ".U1 > .GND");
  toolCalls++;

  // I2C to BME280
  m.addTrace(".U1 > .IO21", ".U4 > .SDI");
  toolCalls++;
  m.addTrace(".U1 > .IO22", ".U4 > .SCK");
  toolCalls++;

  // I2C pull-ups
  m.addTrace(".R3 > .pin1", ".U1 > .3V3");
  toolCalls++;
  m.addTrace(".R3 > .pin2", ".U1 > .IO21");
  toolCalls++;
  m.addTrace(".R4 > .pin1", ".U1 > .3V3");
  toolCalls++;
  m.addTrace(".R4 > .pin2", ".U1 > .IO22");
  toolCalls++;

  // Boot/Reset buttons
  m.addTrace(".SW1 > .A", ".U1 > .EN");
  toolCalls++;
  m.addTrace(".SW1 > .B", ".U1 > .GND");
  toolCalls++;
  m.addTrace(".SW2 > .A", ".U1 > .IO0");
  toolCalls++;
  m.addTrace(".SW2 > .B", ".U1 > .GND");
  toolCalls++;

  // Pull-up resistors for EN and IO0
  m.addTrace(".R1 > .pin1", ".U1 > .3V3");
  toolCalls++;
  m.addTrace(".R1 > .pin2", ".U1 > .EN");
  toolCalls++;
  m.addTrace(".R2 > .pin1", ".U1 > .3V3");
  toolCalls++;
  m.addTrace(".R2 > .pin2", ".U1 > .IO0");
  toolCalls++;

  // CC resistors
  m.addTrace(".J1 > .CC1", ".R5 > .pin1");
  toolCalls++;
  m.addTrace(".R5 > .pin2", ".U3 > .GND");
  toolCalls++;
  m.addTrace(".J1 > .CC2", ".R6 > .pin1");
  toolCalls++;
  m.addTrace(".R6 > .pin2", ".U3 > .GND");
  toolCalls++;

  // GND connections
  m.addTrace(".U1 > .GND", ".U3 > .GND");
  toolCalls++;
  m.addTrace(".U4 > .GND", ".U3 > .GND");
  toolCalls++;
  m.addTrace(".U2 > .GND", ".U3 > .GND");
  toolCalls++;
  m.addTrace(".J1 > .GND", ".U3 > .GND");
  toolCalls++;

  const renderResult = await m.render();
  toolCalls++;

  const cj = m.getCircuitJson();
  const stats = calculateBoardStats(cj);
  const drc = runBasicDrc(cj, 0.127, 0.127);

  let gerberSuccess = false;
  let gerberFiles = 0;
  try {
    const gerbers = exportGerbers(cj);
    writeGerberZip(gerbers, "/tmp/pcb-exports/benchmark-esp32-sensor");
    gerberFiles = gerbers.file_count;
    gerberSuccess = true;
  } catch {}

  const bom = exportBomCsv(cj);
  let svgOk = false;
  try {
    exportSvg(cj);
    svgOk = true;
  } catch {}

  return {
    name: "ESP32 Sensor Node",
    components_added: 22,
    traces_added: 34,
    tool_calls: toolCalls,
    render_success: renderResult.success,
    render_errors: renderResult.errors || [],
    drc_violations: drc.length,
    drc_errors: drc.filter((v) => v.severity === "error").length,
    drc_warnings: drc.filter((v) => v.severity === "warning").length,
    routing_completion_pct: stats.routing_completion_pct,
    board_area_mm2: stats.board_area_mm2,
    gerber_export_success: gerberSuccess,
    gerber_file_count: gerberFiles,
    bom_entries: bom.split("\n").length - 1,
    svg_generated: svgOk,
    circuit_json_elements: cj.length,
    elapsed_ms: Date.now() - start,
  };
}

async function main() {
  console.log("=== PCB MCP Server Benchmark Suite ===\n");
  console.log("Running 3 test cases...\n");

  const results: BenchmarkResult[] = [];

  console.log("--- Test Case 1: LED Blinker ---");
  const r1 = await runTestCase1();
  results.push(r1);
  console.log(`  Render: ${r1.render_success ? "OK" : "FAIL"}`);
  console.log(`  Components: ${r1.components_added}, Traces: ${r1.traces_added}`);
  console.log(`  DRC: ${r1.drc_errors} errors, ${r1.drc_warnings} warnings`);
  console.log(`  Routing: ${r1.routing_completion_pct}%`);
  console.log(`  Gerbers: ${r1.gerber_export_success ? "OK" : "FAIL"} (${r1.gerber_file_count} files)`);
  console.log(`  Time: ${r1.elapsed_ms}ms\n`);

  console.log("--- Test Case 2: USB-C Power Board ---");
  const r2 = await runTestCase2();
  results.push(r2);
  console.log(`  Render: ${r2.render_success ? "OK" : "FAIL"}`);
  console.log(`  Components: ${r2.components_added}, Traces: ${r2.traces_added}`);
  console.log(`  DRC: ${r2.drc_errors} errors, ${r2.drc_warnings} warnings`);
  console.log(`  Routing: ${r2.routing_completion_pct}%`);
  console.log(`  Gerbers: ${r2.gerber_export_success ? "OK" : "FAIL"} (${r2.gerber_file_count} files)`);
  console.log(`  Time: ${r2.elapsed_ms}ms\n`);

  console.log("--- Test Case 3: ESP32 Sensor Node ---");
  const r3 = await runTestCase3();
  results.push(r3);
  console.log(`  Render: ${r3.render_success ? "OK" : "FAIL"}`);
  console.log(`  Components: ${r3.components_added}, Traces: ${r3.traces_added}`);
  console.log(`  DRC: ${r3.drc_errors} errors, ${r3.drc_warnings} warnings`);
  console.log(`  Routing: ${r3.routing_completion_pct}%`);
  console.log(`  Gerbers: ${r3.gerber_export_success ? "OK" : "FAIL"} (${r3.gerber_file_count} files)`);
  console.log(`  Time: ${r3.elapsed_ms}ms\n`);

  // Summary table
  console.log("=== BENCHMARK SUMMARY ===\n");
  console.log("| Metric | LED Blinker | USB-C Power | ESP32 Sensor |");
  console.log("|--------|------------|-------------|--------------|");
  console.log(
    `| Components | ${r1.components_added} | ${r2.components_added} | ${r3.components_added} |`
  );
  console.log(
    `| Traces | ${r1.traces_added} | ${r2.traces_added} | ${r3.traces_added} |`
  );
  console.log(
    `| Tool Calls | ${r1.tool_calls} | ${r2.tool_calls} | ${r3.tool_calls} |`
  );
  console.log(
    `| Render OK | ${r1.render_success} | ${r2.render_success} | ${r3.render_success} |`
  );
  console.log(
    `| DRC Errors | ${r1.drc_errors} | ${r2.drc_errors} | ${r3.drc_errors} |`
  );
  console.log(
    `| DRC Warnings | ${r1.drc_warnings} | ${r2.drc_warnings} | ${r3.drc_warnings} |`
  );
  console.log(
    `| Routing % | ${r1.routing_completion_pct}% | ${r2.routing_completion_pct}% | ${r3.routing_completion_pct}% |`
  );
  console.log(
    `| Board mm² | ${r1.board_area_mm2} | ${r2.board_area_mm2} | ${r3.board_area_mm2} |`
  );
  console.log(
    `| Gerber Export | ${r1.gerber_export_success} | ${r2.gerber_export_success} | ${r3.gerber_export_success} |`
  );
  console.log(
    `| Gerber Files | ${r1.gerber_file_count} | ${r2.gerber_file_count} | ${r3.gerber_file_count} |`
  );
  console.log(
    `| BOM Entries | ${r1.bom_entries} | ${r2.bom_entries} | ${r3.bom_entries} |`
  );
  console.log(
    `| SVG Export | ${r1.svg_generated} | ${r2.svg_generated} | ${r3.svg_generated} |`
  );
  console.log(
    `| JSON Elements | ${r1.circuit_json_elements} | ${r2.circuit_json_elements} | ${r3.circuit_json_elements} |`
  );
  console.log(
    `| Time (ms) | ${r1.elapsed_ms} | ${r2.elapsed_ms} | ${r3.elapsed_ms} |`
  );

  // Save results
  const resultsDir = "tests/benchmarks/results";
  fs.mkdirSync(resultsDir, { recursive: true });
  fs.writeFileSync(
    path.join(resultsDir, "benchmark-results.json"),
    JSON.stringify(results, null, 2)
  );
  console.log(`\nResults saved to ${resultsDir}/benchmark-results.json`);
}

main().catch((err) => {
  console.error("Benchmark failed:", err);
  process.exit(1);
});
