/**
 * Example: ESP32 Sensor Board
 *
 * ESP32-WROOM-32 with BME280 I2C sensor, USB-C power.
 * Demonstrates a medium-complexity design with multiple ICs.
 */

import { CircuitManager } from "../src/engine/circuit-manager.js";
import { exportGerbers, writeGerberZip, exportBomCsv } from "../src/engine/export-pipeline.js";
import { calculateBoardStats, runBasicDrc } from "../src/engine/circuit-json-utils.js";

async function main() {
  const manager = new CircuitManager();

  manager.createProject("esp32-sensor", 50, 35, 2, "ESP32 with BME280 sensor");
  manager.setDesignRules({ preset: "jlcpcb_2layer" });

  // ESP32 module (simplified pinout)
  manager.addComponent("chip", "U1", {
    pinLabels: JSON.stringify({
      pin1: "GND", pin2: "3V3", pin3: "EN", pin4: "IO36",
      pin5: "IO39", pin6: "IO34", pin7: "IO35", pin8: "IO32",
      pin9: "IO33", pin10: "IO25", pin11: "IO26", pin12: "IO27",
      pin13: "IO14", pin14: "IO12", pin15: "IO13", pin16: "IO15",
      pin17: "IO2", pin18: "IO0", pin19: "IO4", pin20: "IO16",
      pin21: "IO17", pin22: "IO5", pin23: "IO18", pin24: "IO19",
      pin25: "IO21", pin26: "RXD0", pin27: "TXD0", pin28: "IO22",
      pin29: "IO23",
    }),
    schematicSymbolName: "box",
  }, "qfp32", 0, 0);

  // 3.3V regulator
  manager.addComponent("chip", "U2", {
    pinLabels: JSON.stringify({ pin1: "GND", pin2: "VOUT", pin3: "VIN" }),
    schematicSymbolName: "box",
  }, "sot223", -18, 0);

  // BME280 sensor
  manager.addComponent("chip", "U3", {
    pinLabels: JSON.stringify({
      pin1: "GND", pin2: "CSB", pin3: "SDI", pin4: "SCK",
      pin5: "SDO", pin6: "VDDIO", pin7: "GND2", pin8: "VDD",
    }),
    schematicSymbolName: "box",
  }, "soic8", 18, -5);

  // Caps
  manager.addComponent("capacitor", "C1", { capacitance: "10uF" }, "0805", -15, -8);
  manager.addComponent("capacitor", "C2", { capacitance: "10uF" }, "0805", -12, -8);
  manager.addComponent("capacitor", "C3", { capacitance: "100nF" }, "0402", -5, -8);
  manager.addComponent("capacitor", "C4", { capacitance: "100nF" }, "0402", 20, -10);

  // I2C pull-ups
  manager.addComponent("resistor", "R1", { resistance: "4.7k" }, "0402", 12, -8);
  manager.addComponent("resistor", "R2", { resistance: "4.7k" }, "0402", 14, -8);

  // Reset/Boot pull-ups
  manager.addComponent("resistor", "R3", { resistance: "10k" }, "0402", 5, 10);
  manager.addComponent("resistor", "R4", { resistance: "10k" }, "0402", 8, 10);

  // Power header
  manager.addComponent("chip", "J1", {
    pinLabels: JSON.stringify({ pin1: "5V", pin2: "GND" }),
    schematicSymbolName: "box",
  }, "pinrow2", -22, 0);

  // Breakout header
  manager.addComponent("chip", "J2", {
    pinLabels: JSON.stringify({
      pin1: "3V3", pin2: "GND", pin3: "IO32", pin4: "IO33",
      pin5: "IO25", pin6: "IO26",
    }),
    schematicSymbolName: "box",
  }, "pinrow6", 22, 5);

  // Power chain
  manager.addTrace(".J1 > .5V", ".U2 > .VIN");
  manager.addTrace(".U2 > .VOUT", ".U1 > .3V3");
  manager.addTrace(".U2 > .VOUT", ".U3 > .VDD");
  manager.addTrace(".U2 > .VOUT", ".U3 > .VDDIO");
  manager.addTrace(".U2 > .VOUT", ".J2 > .3V3");

  // Decoupling
  manager.addTrace(".U2 > .VIN", ".C1 > .pin1");
  manager.addTrace(".C1 > .pin2", ".U2 > .GND");
  manager.addTrace(".U2 > .VOUT", ".C2 > .pin1");
  manager.addTrace(".C2 > .pin2", ".U2 > .GND");
  manager.addTrace(".U1 > .3V3", ".C3 > .pin1");
  manager.addTrace(".C3 > .pin2", ".U1 > .GND");

  // I2C bus
  manager.addTrace(".U1 > .IO21", ".U3 > .SDI");
  manager.addTrace(".U1 > .IO22", ".U3 > .SCK");
  manager.addTrace(".R1 > .pin1", ".U1 > .3V3");
  manager.addTrace(".R1 > .pin2", ".U1 > .IO21");
  manager.addTrace(".R2 > .pin1", ".U1 > .3V3");
  manager.addTrace(".R2 > .pin2", ".U1 > .IO22");

  // Pull-ups
  manager.addTrace(".R3 > .pin1", ".U1 > .3V3");
  manager.addTrace(".R3 > .pin2", ".U1 > .EN");
  manager.addTrace(".R4 > .pin1", ".U1 > .3V3");
  manager.addTrace(".R4 > .pin2", ".U1 > .IO0");

  // GND connections
  manager.addTrace(".U1 > .GND", ".U2 > .GND");
  manager.addTrace(".U3 > .GND", ".U2 > .GND");
  manager.addTrace(".J1 > .GND", ".U2 > .GND");
  manager.addTrace(".J2 > .GND", ".U2 > .GND");

  console.log("Rendering ESP32 sensor board...");
  const result = await manager.render();
  console.log(`Render: ${result.success ? "OK" : "FAIL"}`);

  const cj = manager.getCircuitJson();
  const stats = calculateBoardStats(cj);
  const drc = runBasicDrc(cj, 0.127, 0.127);

  console.log(`Components: ${stats.component_count}`);
  console.log(`Traces: ${stats.trace_count}`);
  console.log(`Routing: ${stats.routing_completion_pct}%`);
  console.log(`DRC errors: ${drc.filter(v => v.severity === "error").length}`);
  console.log(`DRC warnings: ${drc.filter(v => v.severity === "warning").length}`);

  const gerbers = exportGerbers(cj);
  writeGerberZip(gerbers, "/tmp/pcb-exports/esp32-sensor");
  console.log(`Gerbers: ${gerbers.file_count} files exported`);

  console.log(`\nBOM:\n${exportBomCsv(cj)}`);
}

main().catch(console.error);
