/**
 * Example: 555 Timer LED Blinker
 *
 * A classic astable 555 timer circuit that blinks an LED.
 * Demonstrates basic component addition, traces, and export.
 */

import { CircuitManager } from "../src/engine/circuit-manager.js";
import { exportGerbers, writeGerberZip, exportBomCsv, exportSvg } from "../src/engine/export-pipeline.js";
import { calculateBoardStats } from "../src/engine/circuit-json-utils.js";

async function main() {
  const manager = new CircuitManager();

  // Create project
  manager.createProject("555-timer-blinker", 30, 25, 2, "Classic 555 timer LED blinker");

  // 555 Timer IC (DIP-8)
  manager.addComponent("chip", "U1", {
    pinLabels: JSON.stringify({
      pin1: "GND",
      pin2: "TRIG",
      pin3: "OUT",
      pin4: "RST",
      pin5: "CTRL",
      pin6: "THR",
      pin7: "DIS",
      pin8: "VCC",
    }),
    schematicSymbolName: "box",
  }, "dip8", 0, 0);

  // Timing resistors
  manager.addComponent("resistor", "R1", { resistance: "1k" }, "0805", -8, -5);
  manager.addComponent("resistor", "R2", { resistance: "100k" }, "0805", -8, 5);

  // Timing capacitor
  manager.addComponent("capacitor", "C1", { capacitance: "10uF" }, "0805", 0, -8);

  // Bypass/filter capacitor
  manager.addComponent("capacitor", "C2", { capacitance: "10nF" }, "0402", 5, -5);

  // LED and current limiting resistor
  manager.addComponent("led", "LED1", { color: "red" }, "0805", 10, 0);
  manager.addComponent("resistor", "R3", { resistance: "330" }, "0805", 10, -5);

  // Power header
  manager.addComponent("chip", "J1", {
    pinLabels: JSON.stringify({ pin1: "VCC", pin2: "GND" }),
    schematicSymbolName: "box",
  }, "pinrow2", -12, 0);

  // Decoupling cap
  manager.addComponent("capacitor", "C3", { capacitance: "100nF" }, "0402", -4, -5);

  // --- Traces ---
  // Power
  manager.addTrace(".J1 > .VCC", ".U1 > .VCC");
  manager.addTrace(".J1 > .VCC", ".U1 > .RST"); // RST tied to VCC
  manager.addTrace(".J1 > .GND", ".U1 > .GND");

  // Timing network
  manager.addTrace(".U1 > .DIS", ".R1 > .pin1");
  manager.addTrace(".R1 > .pin2", ".R2 > .pin1");
  manager.addTrace(".R2 > .pin2", ".U1 > .THR");
  manager.addTrace(".U1 > .THR", ".U1 > .TRIG"); // THR and TRIG tied
  manager.addTrace(".U1 > .TRIG", ".C1 > .pin1");
  manager.addTrace(".C1 > .pin2", ".U1 > .GND");

  // Control voltage bypass
  manager.addTrace(".U1 > .CTRL", ".C2 > .pin1");
  manager.addTrace(".C2 > .pin2", ".U1 > .GND");

  // LED output
  manager.addTrace(".U1 > .OUT", ".R3 > .pin1");
  manager.addTrace(".R3 > .pin2", ".LED1 > .pin1");
  manager.addTrace(".LED1 > .pin2", ".U1 > .GND");

  // Decoupling
  manager.addTrace(".C3 > .pin1", ".U1 > .VCC");
  manager.addTrace(".C3 > .pin2", ".U1 > .GND");

  // Render
  console.log("Rendering 555 timer circuit...");
  const result = await manager.render();
  console.log(`Render: ${result.success ? "OK" : "FAIL"}`);

  const cj = manager.getCircuitJson();
  const stats = calculateBoardStats(cj);
  console.log(`Components: ${stats.component_count}`);
  console.log(`Routing: ${stats.routing_completion_pct}%`);
  console.log(`Board area: ${stats.board_area_mm2} mm²`);

  // Export
  const gerbers = exportGerbers(cj);
  writeGerberZip(gerbers, "/tmp/pcb-exports/555-timer");
  console.log(`Gerbers: ${gerbers.file_count} files exported`);

  const bom = exportBomCsv(cj);
  console.log(`BOM:\n${bom}`);

  const svg = exportSvg(cj);
  console.log(`SVG: ${svg.length} bytes`);

  console.log("\nTSX source:");
  console.log(manager.getTsxSource());
}

main().catch(console.error);
