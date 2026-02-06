// Shared TypeScript types for the PCB MCP Server

export interface BoardConfig {
  width_mm: number;
  height_mm: number;
  layers: number;
  shape: "rectangular" | "rounded_rect";
  corner_radius_mm: number;
}

export interface DesignRules {
  min_trace_width_mm: number;
  min_clearance_mm: number;
  min_via_diameter_mm: number;
  min_via_drill_mm: number;
  preset: string;
}

export interface ComponentDef {
  name: string;
  type: string;
  properties: Record<string, string>;
  footprint: string;
  pcb_x_mm: number;
  pcb_y_mm: number;
  rotation_deg: number;
  layer: "top" | "bottom";
}

export interface TraceDef {
  id: string;
  from: string;
  to: string;
  width_mm?: number;
}

export interface NetDef {
  name: string;
  connections: string[];
}

export interface GroupDef {
  name: string;
  components: string[];
  pcb_x_mm?: number;
  pcb_y_mm?: number;
}

export interface MountingHoleDef {
  name: string;
  x_mm: number;
  y_mm: number;
  diameter_mm: number;
}

export interface CircuitState {
  project_name: string;
  description: string;
  board: BoardConfig;
  components: Map<string, ComponentDef>;
  traces: TraceDef[];
  nets: NetDef[];
  groups: GroupDef[];
  mounting_holes: MountingHoleDef[];
  design_rules: DesignRules;
}

export interface ToolResult {
  success: boolean;
  data?: any;
  errors?: string[];
}

export type ComponentType =
  | "resistor"
  | "capacitor"
  | "inductor"
  | "led"
  | "diode"
  | "chip"
  | "crystal"
  | "connector"
  | "button"
  | "voltage_regulator"
  | "usb_c"
  | "transistor"
  | "fuse"
  | "switch"
  | "header"
  | "mounting_hole";

export const DEFAULT_DESIGN_RULES: DesignRules = {
  min_trace_width_mm: 0.15,
  min_clearance_mm: 0.15,
  min_via_diameter_mm: 0.6,
  min_via_drill_mm: 0.3,
  preset: "jlcpcb_2layer",
};

export const FAB_PRESETS: Record<string, Partial<DesignRules>> = {
  jlcpcb_2layer: {
    min_trace_width_mm: 0.127,
    min_clearance_mm: 0.127,
    min_via_diameter_mm: 0.5,
    min_via_drill_mm: 0.3,
  },
  jlcpcb_4layer: {
    min_trace_width_mm: 0.09,
    min_clearance_mm: 0.09,
    min_via_diameter_mm: 0.45,
    min_via_drill_mm: 0.2,
  },
  pcbway_standard: {
    min_trace_width_mm: 0.1,
    min_clearance_mm: 0.1,
    min_via_diameter_mm: 0.5,
    min_via_drill_mm: 0.2,
  },
  oshpark: {
    min_trace_width_mm: 0.152,
    min_clearance_mm: 0.152,
    min_via_diameter_mm: 0.508,
    min_via_drill_mm: 0.254,
  },
};
