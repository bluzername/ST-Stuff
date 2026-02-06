import { describe, it, expect, beforeEach } from "vitest";
import { CircuitManager } from "../../src/engine/circuit-manager.js";

describe("CircuitManager - Design Tools", () => {
  let manager: CircuitManager;

  beforeEach(() => {
    manager = new CircuitManager();
  });

  it("should create a project", () => {
    const result = manager.createProject("test", 50, 30, 2, "Test project");
    expect(result.success).toBe(true);
    expect(result.data.name).toBe("test");
    expect(manager.isProjectInitialized()).toBe(true);
  });

  it("should add a component", () => {
    manager.createProject("test", 50, 30, 2);
    const result = manager.addComponent("resistor", "R1", { resistance: "10k" }, "0805", 5, 0);
    expect(result.success).toBe(true);
    expect(result.data.component.name).toBe("R1");
    expect(result.data.total_components).toBe(1);
  });

  it("should reject duplicate component names", () => {
    manager.createProject("test", 50, 30, 2);
    manager.addComponent("resistor", "R1", { resistance: "10k" }, "0805");
    const result = manager.addComponent("resistor", "R1", { resistance: "4.7k" }, "0402");
    expect(result.success).toBe(false);
    expect(result.errors![0]).toContain("already exists");
  });

  it("should modify a component", () => {
    manager.createProject("test", 50, 30, 2);
    manager.addComponent("resistor", "R1", { resistance: "10k" }, "0805");
    const result = manager.modifyComponent("R1", { pcb_x_mm: 10, resistance: "4.7k" });
    expect(result.success).toBe(true);
  });

  it("should fail to modify non-existent component", () => {
    manager.createProject("test", 50, 30, 2);
    const result = manager.modifyComponent("R999", { pcb_x_mm: 10 });
    expect(result.success).toBe(false);
  });

  it("should remove a component and connected traces", () => {
    manager.createProject("test", 50, 30, 2);
    manager.addComponent("resistor", "R1", { resistance: "10k" }, "0805");
    manager.addComponent("capacitor", "C1", { capacitance: "100nF" }, "0402");
    manager.addTrace(".R1 > .pin1", ".C1 > .pin1");
    const result = manager.removeComponent("R1");
    expect(result.success).toBe(true);
    expect(result.data.message).toContain("1 connected traces");
  });

  it("should add traces", () => {
    manager.createProject("test", 50, 30, 2);
    manager.addComponent("resistor", "R1", { resistance: "10k" }, "0805");
    manager.addComponent("capacitor", "C1", { capacitance: "100nF" }, "0402");
    const result = manager.addTrace(".R1 > .pin1", ".C1 > .pin1");
    expect(result.success).toBe(true);
    expect(result.data.trace.from).toBe(".R1 > .pin1");
  });

  it("should add nets", () => {
    manager.createProject("test", 50, 30, 2);
    const result = manager.addNet("VCC", [".R1 > .pin1", ".C1 > .pin1"]);
    expect(result.success).toBe(true);
    expect(result.data.net.connections.length).toBe(2);
  });

  it("should add groups", () => {
    manager.createProject("test", 50, 30, 2);
    manager.addComponent("resistor", "R1", { resistance: "10k" }, "0805");
    manager.addComponent("capacitor", "C1", { capacitance: "100nF" }, "0402");
    const result = manager.addGroup("power", ["R1", "C1"]);
    expect(result.success).toBe(true);
  });

  it("should fail to add group with missing components", () => {
    manager.createProject("test", 50, 30, 2);
    const result = manager.addGroup("power", ["R1", "C1"]);
    expect(result.success).toBe(false);
  });

  it("should set board outline", () => {
    manager.createProject("test", 50, 30, 2);
    const result = manager.setBoardOutline(80, 60, "rounded_rect", 2);
    expect(result.success).toBe(true);
    expect(result.data.board.width_mm).toBe(80);
  });

  it("should set design rules", () => {
    manager.createProject("test", 50, 30, 2);
    const result = manager.setDesignRules({ min_trace_width_mm: 0.2 });
    expect(result.success).toBe(true);
    expect(result.data.design_rules.min_trace_width_mm).toBe(0.2);
  });

  it("should auto-place components in grid", () => {
    manager.createProject("test", 50, 30, 2);
    manager.addComponent("resistor", "R1", { resistance: "10k" }, "0805");
    manager.addComponent("capacitor", "C1", { capacitance: "100nF" }, "0402");
    manager.addComponent("led", "LED1", {}, "0805");
    const result = manager.autoPlace("grid");
    expect(result.success).toBe(true);
    expect(result.data.components_placed).toBe(3);
  });

  it("should return full circuit state", () => {
    manager.createProject("test", 50, 30, 2, "desc");
    manager.addComponent("resistor", "R1", { resistance: "10k" }, "0805");
    const state = manager.getState();
    expect(state.project_name).toBe("test");
    expect(state.components.length).toBe(1);
    expect(state.board.width_mm).toBe(50);
  });
});

describe("CircuitManager - Rendering", () => {
  it("should render a simple circuit", async () => {
    const manager = new CircuitManager();
    manager.createProject("test", 30, 20, 2);
    manager.addComponent("resistor", "R1", { resistance: "10k" }, "0805", 5, 0);
    manager.addComponent("capacitor", "C1", { capacitance: "100nF" }, "0402", -5, 0);
    manager.addTrace(".R1 > .pin1", ".C1 > .pin1");

    const result = await manager.render();
    expect(result.success).toBe(true);
    expect(result.data.element_count).toBeGreaterThan(0);

    const json = manager.getCircuitJson();
    expect(json.length).toBeGreaterThan(0);

    const tsx = manager.getTsxSource();
    expect(tsx).toContain("board");
    expect(tsx).toContain("R1");
    expect(tsx).toContain("C1");
  });

  it("should render from custom TSX", async () => {
    const manager = new CircuitManager();
    const tsx = `
circuit.add(
  <board width="20mm" height="20mm">
    <resistor name="R1" resistance="1k" footprint="0805" />
  </board>
)`;
    const result = await manager.renderFromTsx(tsx);
    expect(result.success).toBe(true);
    expect(result.data.element_count).toBeGreaterThan(0);
  });
});
