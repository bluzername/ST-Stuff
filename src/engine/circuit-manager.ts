/**
 * CircuitManager: Stateful circuit session manager.
 *
 * Maintains the full circuit state (components, traces, nets, board config)
 * and handles the render cycle:
 *   modify state → generate TSX → evaluate with CircuitRunner → extract Circuit JSON
 *
 * Uses @tscircuit/eval's CircuitRunner which accepts raw TSX strings and
 * manages the React/tscircuit runtime internally, avoiding the need for
 * a JSX bundler in our Node.js environment.
 */

import { CircuitRunner } from "@tscircuit/eval";
import type {
  CircuitState,
  ComponentDef,
  TraceDef,
  NetDef,
  GroupDef,
  BoardConfig,
  MountingHoleDef,
  DesignRules,
  ToolResult,
} from "../types/index.js";
import { DEFAULT_DESIGN_RULES } from "../types/index.js";
import { generateFullTsx } from "./tsx-generator.js";
import type { CircuitElement } from "./circuit-json-utils.js";

export class CircuitManager {
  private state: CircuitState;
  private circuitJson: CircuitElement[] = [];
  private tsxSource: string = "";
  private traceIdCounter: number = 0;
  private renderDirty: boolean = true;

  constructor() {
    this.state = {
      project_name: "",
      description: "",
      board: {
        width_mm: 50,
        height_mm: 50,
        layers: 2,
        shape: "rectangular",
        corner_radius_mm: 0,
      },
      components: new Map(),
      traces: [],
      nets: [],
      groups: [],
      mounting_holes: [],
      design_rules: { ...DEFAULT_DESIGN_RULES },
    };
  }

  // --- Project management ---

  createProject(
    name: string,
    width_mm: number,
    height_mm: number,
    layer_count: number,
    description?: string,
    form_factor?: string
  ): ToolResult {
    this.state.project_name = name;
    this.state.description = description || "";
    this.state.board.width_mm = width_mm;
    this.state.board.height_mm = height_mm;
    this.state.board.layers = layer_count;
    this.state.components = new Map();
    this.state.traces = [];
    this.state.nets = [];
    this.state.groups = [];
    this.state.mounting_holes = [];
    this.circuitJson = [];
    this.traceIdCounter = 0;
    this.renderDirty = true;

    // Apply form factor defaults
    if (form_factor === "arduino_shield") {
      this.state.board.width_mm = width_mm || 68.6;
      this.state.board.height_mm = height_mm || 53.3;
    } else if (form_factor === "raspberry_pi_hat") {
      this.state.board.width_mm = width_mm || 65;
      this.state.board.height_mm = height_mm || 56.5;
    }

    return {
      success: true,
      data: {
        name,
        board: this.state.board,
        message: `Project "${name}" created with ${width_mm}mm x ${height_mm}mm board, ${layer_count} layers`,
      },
    };
  }

  // --- Component management ---

  addComponent(
    type: string,
    name: string,
    properties: Record<string, string>,
    footprint: string,
    pcb_x_mm?: number,
    pcb_y_mm?: number,
    rotation_deg?: number,
    layer?: "top" | "bottom"
  ): ToolResult {
    if (this.state.components.has(name)) {
      return {
        success: false,
        errors: [
          `Component '${name}' already exists. Use pcb_modify_component to update it, or pcb_remove_component to remove it first.`,
        ],
      };
    }

    const comp: ComponentDef = {
      name,
      type,
      properties: { ...properties },
      footprint,
      pcb_x_mm: pcb_x_mm ?? 0,
      pcb_y_mm: pcb_y_mm ?? 0,
      rotation_deg: rotation_deg ?? 0,
      layer: layer ?? "top",
    };

    this.state.components.set(name, comp);
    this.renderDirty = true;

    return {
      success: true,
      data: {
        component: comp,
        message: `Added ${type} '${name}' with footprint ${footprint}`,
        total_components: this.state.components.size,
      },
    };
  }

  modifyComponent(name: string, updates: Record<string, any>): ToolResult {
    const comp = this.state.components.get(name);
    if (!comp) {
      return {
        success: false,
        errors: [
          `Component '${name}' not found. Available components: ${[...this.state.components.keys()].join(", ") || "none"}`,
        ],
      };
    }

    for (const [key, val] of Object.entries(updates)) {
      switch (key) {
        case "pcb_x_mm":
          comp.pcb_x_mm = val;
          break;
        case "pcb_y_mm":
          comp.pcb_y_mm = val;
          break;
        case "rotation_deg":
          comp.rotation_deg = val;
          break;
        case "layer":
          comp.layer = val;
          break;
        case "footprint":
          comp.footprint = val;
          break;
        default:
          comp.properties[key] = String(val);
          break;
      }
    }

    this.renderDirty = true;
    return {
      success: true,
      data: {
        component: comp,
        message: `Updated component '${name}'`,
      },
    };
  }

  removeComponent(name: string): ToolResult {
    if (!this.state.components.has(name)) {
      return {
        success: false,
        errors: [
          `Component '${name}' not found. Available components: ${[...this.state.components.keys()].join(", ") || "none"}`,
        ],
      };
    }

    this.state.components.delete(name);

    // Remove traces connected to this component
    const removedTraces = this.state.traces.filter(
      (t) => t.from.includes(`.${name}`) || t.to.includes(`.${name}`)
    );
    this.state.traces = this.state.traces.filter(
      (t) => !t.from.includes(`.${name}`) && !t.to.includes(`.${name}`)
    );

    // Remove from nets
    for (const net of this.state.nets) {
      net.connections = net.connections.filter(
        (c) => !c.includes(`.${name}`)
      );
    }

    // Remove from groups
    for (const group of this.state.groups) {
      group.components = group.components.filter((c) => c !== name);
    }

    this.renderDirty = true;
    return {
      success: true,
      data: {
        message: `Removed component '${name}' and ${removedTraces.length} connected traces`,
      },
    };
  }

  // --- Trace management ---

  addTrace(from: string, to: string, width_mm?: number): ToolResult {
    const id = `T${++this.traceIdCounter}`;
    const trace: TraceDef = { id, from, to, width_mm };
    this.state.traces.push(trace);
    this.renderDirty = true;

    return {
      success: true,
      data: {
        trace,
        message: `Added trace from ${from} to ${to}`,
        total_traces: this.state.traces.length,
      },
    };
  }

  // --- Net management ---

  addNet(name: string, connections: string[]): ToolResult {
    // Check if net already exists
    const existing = this.state.nets.find((n) => n.name === name);
    if (existing) {
      // Merge connections
      const newConns = connections.filter(
        (c) => !existing.connections.includes(c)
      );
      existing.connections.push(...newConns);
      this.renderDirty = true;
      return {
        success: true,
        data: {
          net: existing,
          message: `Updated net '${name}' with ${newConns.length} new connections`,
        },
      };
    }

    const net: NetDef = { name, connections };
    this.state.nets.push(net);
    this.renderDirty = true;

    return {
      success: true,
      data: {
        net,
        message: `Created net '${name}' with ${connections.length} connections`,
      },
    };
  }

  // --- Group management ---

  addGroup(
    name: string,
    components: string[],
    pcb_x_mm?: number,
    pcb_y_mm?: number
  ): ToolResult {
    // Verify all components exist
    const missing = components.filter((c) => !this.state.components.has(c));
    if (missing.length > 0) {
      return {
        success: false,
        errors: [
          `Components not found: ${missing.join(", ")}. Add them first with pcb_add_component.`,
        ],
      };
    }

    const group: GroupDef = { name, components, pcb_x_mm, pcb_y_mm };
    this.state.groups.push(group);
    this.renderDirty = true;

    return {
      success: true,
      data: {
        group,
        message: `Created group '${name}' with ${components.length} components`,
      },
    };
  }

  // --- Board configuration ---

  setBoardOutline(
    width_mm: number,
    height_mm: number,
    shape?: "rectangular" | "rounded_rect",
    corner_radius_mm?: number
  ): ToolResult {
    this.state.board.width_mm = width_mm;
    this.state.board.height_mm = height_mm;
    if (shape) this.state.board.shape = shape;
    if (corner_radius_mm !== undefined) this.state.board.corner_radius_mm = corner_radius_mm;
    this.renderDirty = true;

    return {
      success: true,
      data: {
        board: this.state.board,
        message: `Board updated: ${width_mm}mm x ${height_mm}mm`,
      },
    };
  }

  addMountingHole(
    x_mm: number,
    y_mm: number,
    diameter_mm: number,
    name?: string
  ): ToolResult {
    const holeName = name || `MH${this.state.mounting_holes.length + 1}`;
    const hole: MountingHoleDef = {
      name: holeName,
      x_mm,
      y_mm,
      diameter_mm,
    };
    this.state.mounting_holes.push(hole);
    this.renderDirty = true;

    return {
      success: true,
      data: {
        hole,
        message: `Added mounting hole '${holeName}' at (${x_mm}, ${y_mm})`,
      },
    };
  }

  setDesignRules(rules: Partial<DesignRules>): ToolResult {
    Object.assign(this.state.design_rules, rules);
    return {
      success: true,
      data: {
        design_rules: this.state.design_rules,
        message: `Design rules updated`,
      },
    };
  }

  // --- Auto placement ---

  autoPlace(strategy: string = "grid"): ToolResult {
    const components = [...this.state.components.values()];
    if (components.length === 0) {
      return {
        success: false,
        errors: ["No components to place. Add components first."],
      };
    }

    const boardW = this.state.board.width_mm;
    const boardH = this.state.board.height_mm;
    const margin = 3; // mm from board edge
    const usableW = boardW - 2 * margin;
    const usableH = boardH - 2 * margin;

    if (strategy === "grid") {
      const cols = Math.ceil(Math.sqrt(components.length));
      const rows = Math.ceil(components.length / cols);
      const spacingX = usableW / (cols + 1);
      const spacingY = usableH / (rows + 1);

      components.forEach((comp, idx) => {
        const col = idx % cols;
        const row = Math.floor(idx / cols);
        comp.pcb_x_mm = -usableW / 2 + spacingX * (col + 1);
        comp.pcb_y_mm = -usableH / 2 + spacingY * (row + 1);
      });
    } else if (strategy === "clustered" || strategy === "minimal_crossings") {
      // Simple connectivity-based clustering: place connected components close together
      const connectionMap = new Map<string, Set<string>>();
      for (const trace of this.state.traces) {
        const fromComp = trace.from.split(" > ")[0].replace(".", "");
        const toComp = trace.to.split(" > ")[0].replace(".", "");
        if (!connectionMap.has(fromComp)) connectionMap.set(fromComp, new Set());
        if (!connectionMap.has(toComp)) connectionMap.set(toComp, new Set());
        connectionMap.get(fromComp)!.add(toComp);
        connectionMap.get(toComp)!.add(fromComp);
      }

      // Place in a grid but sort by connectivity
      const placed = new Set<string>();
      const order: ComponentDef[] = [];

      // Start with most connected component
      const sortedByConnections = components.sort((a, b) => {
        const aConns = connectionMap.get(a.name)?.size ?? 0;
        const bConns = connectionMap.get(b.name)?.size ?? 0;
        return bConns - aConns;
      });

      // BFS from most connected
      const queue = [sortedByConnections[0]];
      placed.add(sortedByConnections[0].name);
      while (queue.length > 0) {
        const current = queue.shift()!;
        order.push(current);
        const neighbors = connectionMap.get(current.name) || new Set();
        for (const neighborName of neighbors) {
          if (!placed.has(neighborName)) {
            const neighbor = this.state.components.get(neighborName);
            if (neighbor) {
              queue.push(neighbor);
              placed.add(neighborName);
            }
          }
        }
      }
      // Add remaining unconnected components
      for (const comp of components) {
        if (!placed.has(comp.name)) {
          order.push(comp);
        }
      }

      const cols = Math.ceil(Math.sqrt(order.length));
      const rows = Math.ceil(order.length / cols);
      const spacingX = usableW / (cols + 1);
      const spacingY = usableH / (rows + 1);

      order.forEach((comp, idx) => {
        const col = idx % cols;
        const row = Math.floor(idx / cols);
        comp.pcb_x_mm = -usableW / 2 + spacingX * (col + 1);
        comp.pcb_y_mm = -usableH / 2 + spacingY * (row + 1);
      });
    }

    this.renderDirty = true;
    return {
      success: true,
      data: {
        strategy,
        components_placed: components.length,
        message: `Auto-placed ${components.length} components using '${strategy}' strategy`,
      },
    };
  }

  // --- Rendering ---

  async render(): Promise<ToolResult> {
    if (this.state.components.size === 0) {
      this.circuitJson = [];
      this.tsxSource = "";
      return {
        success: true,
        data: { message: "No components to render" },
      };
    }

    try {
      this.tsxSource = generateFullTsx(
        this.state.board,
        this.state.components,
        this.state.traces,
        this.state.nets,
        this.state.groups,
        this.state.mounting_holes
      );

      const runner = new CircuitRunner();
      await runner.execute(this.tsxSource);
      await runner.renderUntilSettled();
      this.circuitJson = (await runner.getCircuitJson()) as CircuitElement[];
      this.renderDirty = false;

      const errors = this.circuitJson.filter((el) => el.type.includes("error"));
      const warnings = this.circuitJson.filter((el) => el.type.includes("warning"));

      return {
        success: true,
        data: {
          element_count: this.circuitJson.length,
          error_count: errors.length,
          warning_count: warnings.length,
          errors: errors.map((e) => e.message || e.type),
          warnings: warnings.map((w) => w.message || w.type),
        },
      };
    } catch (error: any) {
      return {
        success: false,
        errors: [
          `Render failed: ${error.message}`,
          `TSX source:\n${this.tsxSource}`,
        ],
      };
    }
  }

  async ensureRendered(): Promise<ToolResult> {
    if (this.renderDirty) {
      return await this.render();
    }
    return { success: true, data: { message: "Already rendered" } };
  }

  // --- State queries ---

  getCircuitJson(): CircuitElement[] {
    return this.circuitJson;
  }

  getTsxSource(): string {
    return this.tsxSource;
  }

  setTsxSource(tsx: string): void {
    this.tsxSource = tsx;
    this.renderDirty = true;
  }

  async renderFromTsx(tsx: string): Promise<ToolResult> {
    try {
      const runner = new CircuitRunner();
      await runner.execute(tsx);
      await runner.renderUntilSettled();
      this.circuitJson = (await runner.getCircuitJson()) as CircuitElement[];
      this.tsxSource = tsx;
      this.renderDirty = false;

      return {
        success: true,
        data: {
          element_count: this.circuitJson.length,
          message: "Circuit rendered from custom TSX",
        },
      };
    } catch (error: any) {
      return {
        success: false,
        errors: [`Render from TSX failed: ${error.message}`],
      };
    }
  }

  getState(): {
    project_name: string;
    description: string;
    board: BoardConfig;
    components: Array<ComponentDef>;
    traces: TraceDef[];
    nets: NetDef[];
    groups: GroupDef[];
    mounting_holes: MountingHoleDef[];
    design_rules: DesignRules;
    render_dirty: boolean;
    circuit_json_elements: number;
  } {
    return {
      project_name: this.state.project_name,
      description: this.state.description,
      board: this.state.board,
      components: [...this.state.components.values()],
      traces: this.state.traces,
      nets: this.state.nets,
      groups: this.state.groups,
      mounting_holes: this.state.mounting_holes,
      design_rules: this.state.design_rules,
      render_dirty: this.renderDirty,
      circuit_json_elements: this.circuitJson.length,
    };
  }

  getDesignRules(): DesignRules {
    return { ...this.state.design_rules };
  }

  isProjectInitialized(): boolean {
    return this.state.project_name !== "";
  }
}
