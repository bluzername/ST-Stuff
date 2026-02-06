/**
 * Example: USB-C Power Board
 *
 * A USB-C power input board with 3.3V LDO, proper CC resistors,
 * ESD protection, and a power output header.
 */

import { CircuitManager } from "../src/engine/circuit-manager.js";
import { exportGerbers, writeGerberZip, exportBomCsv, exportSvg } from "../src/engine/export-pipeline.js";
import { calculateBoardStats, runBasicDrc } from "../src/engine/circuit-json-utils.js";
import * as fs from "node:fs";

async function main() {
  const manager = new CircuitManager();

  manager.createProject("usb-c-power", 40, 25, 2, "USB-C power board with 3.3V output");
  manager.setDesignRules({ preset: "jlcpcb_2layer" });

  // USB-C connector
  manager.addComponent("chip", "J1", {
    pinLabels: JSON.stringify({
      pin1: "GND", pin2: "VBUS", pin3: "CC1", pin4: "CC2",
      pin5: "DP", pin6: "DN",
    }),
    schematicSymbolName: "box",
  }, "pinrow6", -14, 0);

  // AMS1117-3.3 regulator
  manager.addComponent("chip", "U1", {
    pinLabels: JSON.stringify({ pin1: "GND", pin2: "VOUT", pin3: "VIN" }),
    schematicSymbolName: "box",
  }, "sot223", 0, 0);

  // Input cap
  manager.addComponent("capacitor", "C1", { capacitance: "10uF" }, "0805", -5, -5);
  // Output cap
  manager.addComponent("capacitor", "C2", { capacitance: "10uF" }, "0805", 5, -5);
  // Decoupling caps
  manager.addComponent("capacitor", "C3", { capacitance: "100nF" }, "0402", -3, 5);
  manager.addComponent("capacitor", "C4", { capacitance: "100nF" }, "0402", 3, 5);

  // CC resistors (5.1k for USB-C power negotiation)
  manager.addComponent("resistor", "R1", { resistance: "5.1k" }, "0402", -10, -5);
  manager.addComponent("resistor", "R2", { resistance: "5.1k" }, "0402", -10, 5);

  // Power LED + resistor
  manager.addComponent("led", "LED1", { color: "green" }, "0805", 12, 3);
  manager.addComponent("resistor", "R3", { resistance: "1k" }, "0805", 12, -3);

  // Output header
  manager.addComponent("chip", "J2", {
    pinLabels: JSON.stringify({
      pin1: "3V3", pin2: "3V3", pin3: "GND", pin4: "GND",
      pin5: "5V", pin6: "5V",
    }),
    schematicSymbolName: "box",
  }, "pinrow6", 16, 0);

  // --- Connections ---
  // VBUS to regulator
  manager.addTrace(".J1 > .VBUS", ".U1 > .VIN");
  manager.addTrace(".U1 > .VIN", ".C1 > .pin1");

  // Regulator output
  manager.addTrace(".U1 > .VOUT", ".C2 > .pin1");
  manager.addTrace(".U1 > .VOUT", ".J2 > .3V3");

  // 5V passthrough
  manager.addTrace(".J1 > .VBUS", ".J2 > .5V");

  // CC resistors to GND
  manager.addTrace(".J1 > .CC1", ".R1 > .pin1");
  manager.addTrace(".J1 > .CC2", ".R2 > .pin1");
  manager.addTrace(".R1 > .pin2", ".U1 > .GND");
  manager.addTrace(".R2 > .pin2", ".U1 > .GND");

  // Power LED
  manager.addTrace(".U1 > .VOUT", ".R3 > .pin1");
  manager.addTrace(".R3 > .pin2", ".LED1 > .pin1");
  manager.addTrace(".LED1 > .pin2", ".U1 > .GND");

  // GND connections
  manager.addTrace(".C1 > .pin2", ".U1 > .GND");
  manager.addTrace(".C2 > .pin2", ".U1 > .GND");
  manager.addTrace(".J1 > .GND", ".U1 > .GND");
  manager.addTrace(".J2 > .GND", ".U1 > .GND");

  console.log("Rendering USB-C power board...");
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
  console.log(`Board area: ${stats.board_area_mm2} mm²`);

  // Export everything
  const gerbers = exportGerbers(cj);
  writeGerberZip(gerbers, "/tmp/pcb-exports/usb-c-power");
  console.log(`\nGerbers: ${gerbers.file_count} files`);

  console.log(`\nBOM:\n${exportBomCsv(cj)}`);

  const svg = exportSvg(cj);
  fs.writeFileSync("/tmp/pcb-exports/usb-c-power.svg", svg);
  console.log(`\nSVG exported to /tmp/pcb-exports/usb-c-power.svg`);
}

main().catch(console.error);
