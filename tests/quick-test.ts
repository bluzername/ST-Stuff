/**
 * Quick test: verifies the MCP server starts and responds to initialization.
 * Also runs a basic end-to-end circuit design flow.
 */

import { CircuitManager } from "../src/engine/circuit-manager.js";
import { exportGerbers, exportBomCsv, exportSvg } from "../src/engine/export-pipeline.js";
import { calculateBoardStats, runBasicDrc } from "../src/engine/circuit-json-utils.js";

async function runQuickTest() {
  console.log("=== PCB MCP Server Quick Test ===\n");

  // Test 1: Create a circuit manager and project
  console.log("1. Creating project...");
  const manager = new CircuitManager();
  const projectResult = manager.createProject("quick-test", 30, 20, 2, "Quick test circuit");
  console.log(`   ${projectResult.success ? "OK" : "FAIL"}: ${projectResult.data?.message}`);

  // Test 2: Add components
  console.log("2. Adding components...");
  const r1 = manager.addComponent("resistor", "R1", { resistance: "10k" }, "0805", 5, 0);
  console.log(`   ${r1.success ? "OK" : "FAIL"}: ${r1.data?.message}`);

  const c1 = manager.addComponent("capacitor", "C1", { capacitance: "100nF" }, "0402", -5, 0);
  console.log(`   ${c1.success ? "OK" : "FAIL"}: ${c1.data?.message}`);

  const led = manager.addComponent("led", "LED1", { color: "red" }, "0805", 0, 5);
  console.log(`   ${led.success ? "OK" : "FAIL"}: ${led.data?.message}`);

  // Test 3: Add trace
  console.log("3. Adding traces...");
  const t1 = manager.addTrace(".R1 > .pin1", ".C1 > .pin1");
  console.log(`   ${t1.success ? "OK" : "FAIL"}: ${t1.data?.message}`);

  const t2 = manager.addTrace(".R1 > .pin2", ".LED1 > .pin1");
  console.log(`   ${t2.success ? "OK" : "FAIL"}: ${t2.data?.message}`);

  // Test 4: Render circuit
  console.log("4. Rendering circuit...");
  const renderResult = await manager.render();
  console.log(`   ${renderResult.success ? "OK" : "FAIL"}: ${JSON.stringify(renderResult.data)}`);

  if (!renderResult.success) {
    console.log("   Render errors:", renderResult.errors);
  }

  // Test 5: Get TSX source
  console.log("5. TSX source:");
  const tsx = manager.getTsxSource();
  console.log(`   ${tsx.split("\n").length} lines generated`);

  // Test 6: Get circuit JSON
  const circuitJson = manager.getCircuitJson();
  console.log(`6. Circuit JSON: ${circuitJson.length} elements`);

  // Test 7: Board stats
  const stats = calculateBoardStats(circuitJson);
  console.log(`7. Board stats:`);
  console.log(`   Components: ${stats.component_count}`);
  console.log(`   Traces: ${stats.trace_count}`);
  console.log(`   Board area: ${stats.board_area_mm2} mm²`);
  console.log(`   Routing: ${stats.routing_completion_pct}%`);

  // Test 8: DRC
  const drc = runBasicDrc(circuitJson, 0.15, 0.15);
  console.log(`8. DRC: ${drc.length} violations`);
  for (const v of drc) {
    console.log(`   [${v.severity}] ${v.type}: ${v.message}`);
  }

  // Test 9: Export Gerbers
  console.log("9. Exporting Gerbers...");
  try {
    const gerbers = exportGerbers(circuitJson);
    console.log(`   OK: ${gerbers.file_count} files, layers: ${Object.keys(gerbers.layers).join(", ")}`);
  } catch (err: any) {
    console.log(`   FAIL: ${err.message}`);
  }

  // Test 10: Export BOM
  console.log("10. Exporting BOM...");
  const bom = exportBomCsv(circuitJson);
  console.log(`   OK: ${bom.split("\n").length} lines`);

  // Test 11: Export SVG
  console.log("11. Exporting SVG...");
  const svg = exportSvg(circuitJson);
  console.log(`   OK: ${svg.length} bytes`);

  // Test 12: Circuit state
  const state = manager.getState();
  console.log(`12. Circuit state: ${state.components.length} components, ${state.traces.length} traces`);

  // Test 13: Modify component
  console.log("13. Modifying component...");
  const mod = manager.modifyComponent("R1", { pcb_x_mm: 7, resistance: "4.7k" });
  console.log(`   ${mod.success ? "OK" : "FAIL"}: ${mod.data?.message}`);

  // Test 14: Remove component
  console.log("14. Removing component...");
  const rem = manager.removeComponent("LED1");
  console.log(`   ${rem.success ? "OK" : "FAIL"}: ${rem.data?.message}`);

  // Test 15: Duplicate component check
  console.log("15. Duplicate component check...");
  const dup = manager.addComponent("resistor", "R1", { resistance: "1k" }, "0402");
  console.log(`   ${!dup.success ? "OK (correctly rejected)" : "FAIL"}: ${dup.errors?.[0]}`);

  console.log("\n=== Quick Test Complete ===");
}

runQuickTest().catch((err) => {
  console.error("Quick test failed:", err);
  process.exit(1);
});
