import { describe, it, expect } from "vitest";
import { CircuitManager } from "../../src/engine/circuit-manager.js";
import {
  exportGerbers,
  exportBomCsv,
  exportSvg,
  exportSpiceNetlist,
  exportPickAndPlaceCsv,
  exportCircuitJson,
} from "../../src/engine/export-pipeline.js";
import { calculateBoardStats, runBasicDrc } from "../../src/engine/circuit-json-utils.js";

describe("End-to-end: Simple RC circuit", () => {
  it("should design, render, and export a complete circuit", async () => {
    const manager = new CircuitManager();

    // Create project
    manager.createProject("rc-test", 25, 15, 2, "Simple RC test");

    // Add components
    manager.addComponent("resistor", "R1", { resistance: "10k" }, "0805", 3, 0);
    manager.addComponent("capacitor", "C1", { capacitance: "100nF" }, "0805", -3, 0);

    // Add trace
    manager.addTrace(".R1 > .pin1", ".C1 > .pin1");

    // Render
    const renderResult = await manager.render();
    expect(renderResult.success).toBe(true);

    const cj = manager.getCircuitJson();
    expect(cj.length).toBeGreaterThan(0);

    // Stats
    const stats = calculateBoardStats(cj);
    expect(stats.component_count).toBe(2);
    expect(stats.board_area_mm2).toBe(375);

    // DRC
    const drc = runBasicDrc(cj, 0.15, 0.15);
    expect(Array.isArray(drc)).toBe(true);

    // Gerber export
    const gerbers = exportGerbers(cj);
    expect(gerbers.file_count).toBeGreaterThan(0);
    expect(Object.keys(gerbers.layers).length).toBeGreaterThan(0);
    // Verify gerber content is not empty
    for (const [, content] of Object.entries(gerbers.layers)) {
      expect(content.length).toBeGreaterThan(0);
    }

    // BOM
    const bom = exportBomCsv(cj);
    expect(bom).toContain("Reference");
    expect(bom.split("\n").length).toBeGreaterThan(1);

    // SVG
    const svg = exportSvg(cj);
    expect(svg).toContain("<svg");
    expect(svg).toContain("</svg>");

    // SPICE
    const spice = exportSpiceNetlist(cj);
    expect(spice).toContain("SPICE");
    expect(spice).toContain(".end");

    // Pick and place
    const pnp = exportPickAndPlaceCsv(cj);
    expect(pnp).toContain("Reference");

    // Circuit JSON
    const jsonStr = exportCircuitJson(cj);
    const parsed = JSON.parse(jsonStr);
    expect(Array.isArray(parsed)).toBe(true);
    expect(parsed.length).toBe(cj.length);
  });
});

describe("End-to-end: Multi-component circuit", () => {
  it("should handle a more complex design", async () => {
    const manager = new CircuitManager();
    manager.createProject("complex-test", 40, 30, 2);

    // Add several components
    manager.addComponent("chip", "U1", {
      pinLabels: JSON.stringify({ pin1: "VCC", pin2: "GND", pin3: "OUT", pin4: "IN" }),
      schematicSymbolName: "box",
    }, "soic8", 0, 0);

    manager.addComponent("resistor", "R1", { resistance: "10k" }, "0805", -8, -5);
    manager.addComponent("resistor", "R2", { resistance: "4.7k" }, "0805", 8, -5);
    manager.addComponent("capacitor", "C1", { capacitance: "100nF" }, "0402", -4, 5);
    manager.addComponent("capacitor", "C2", { capacitance: "10uF" }, "0805", 4, 5);
    manager.addComponent("led", "LED1", {}, "0805", 12, 0);

    // Connect
    manager.addTrace(".U1 > .OUT", ".R2 > .pin1");
    manager.addTrace(".R2 > .pin2", ".LED1 > .pin1");
    manager.addTrace(".U1 > .IN", ".R1 > .pin1");
    manager.addTrace(".U1 > .VCC", ".C1 > .pin1");
    manager.addTrace(".U1 > .VCC", ".C2 > .pin1");

    // Render
    const result = await manager.render();
    expect(result.success).toBe(true);

    const cj = manager.getCircuitJson();
    const stats = calculateBoardStats(cj);
    expect(stats.component_count).toBe(6);

    // All export formats should work
    const gerbers = exportGerbers(cj);
    expect(gerbers.file_count).toBeGreaterThan(0);

    const bom = exportBomCsv(cj);
    expect(bom.split("\n").length).toBeGreaterThanOrEqual(7); // header + 6 components

    const svg = exportSvg(cj);
    expect(svg).toContain("R1");
  });
});
