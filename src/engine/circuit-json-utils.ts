/**
 * Circuit JSON query and manipulation helpers.
 *
 * Circuit JSON is an array of typed elements with prefixes:
 *   source_  - original circuit definition
 *   schematic_ - schematic visualization
 *   pcb_     - PCB physical data
 *   cad_     - external CAD data
 */

export interface CircuitElement {
  type: string;
  [key: string]: any;
}

export function filterByType(circuitJson: CircuitElement[], type: string): CircuitElement[] {
  return circuitJson.filter((el) => el.type === type);
}

export function filterByPrefix(circuitJson: CircuitElement[], prefix: string): CircuitElement[] {
  return circuitJson.filter((el) => el.type.startsWith(prefix));
}

export function getSourceComponents(circuitJson: CircuitElement[]): CircuitElement[] {
  return filterByType(circuitJson, "source_component");
}

export function getPcbComponents(circuitJson: CircuitElement[]): CircuitElement[] {
  return filterByType(circuitJson, "pcb_component");
}

export function getPcbTraces(circuitJson: CircuitElement[]): CircuitElement[] {
  return filterByType(circuitJson, "pcb_trace");
}

export function getPcbVias(circuitJson: CircuitElement[]): CircuitElement[] {
  return filterByType(circuitJson, "pcb_via");
}

export function getPcbSmtPads(circuitJson: CircuitElement[]): CircuitElement[] {
  return filterByType(circuitJson, "pcb_smtpad");
}

export function getPcbBoard(circuitJson: CircuitElement[]): CircuitElement | undefined {
  return circuitJson.find((el) => el.type === "pcb_board");
}

export function getSourceTraces(circuitJson: CircuitElement[]): CircuitElement[] {
  return filterByType(circuitJson, "source_trace");
}

export function getSourcePorts(circuitJson: CircuitElement[]): CircuitElement[] {
  return filterByType(circuitJson, "source_port");
}

export function getPcbPorts(circuitJson: CircuitElement[]): CircuitElement[] {
  return filterByType(circuitJson, "pcb_port");
}

export function getErrors(circuitJson: CircuitElement[]): CircuitElement[] {
  return circuitJson.filter(
    (el) => el.type.includes("error") || el.type.includes("warning")
  );
}

export function getPcbTraceErrors(circuitJson: CircuitElement[]): CircuitElement[] {
  return filterByType(circuitJson, "pcb_trace_error");
}

export function getSchematicComponents(circuitJson: CircuitElement[]): CircuitElement[] {
  return filterByType(circuitJson, "schematic_component");
}

export function getSchematicTraces(circuitJson: CircuitElement[]): CircuitElement[] {
  return filterByType(circuitJson, "schematic_trace");
}

export interface BoardStats {
  component_count: number;
  net_count: number;
  trace_count: number;
  via_count: number;
  pad_count: number;
  board_area_mm2: number;
  board_width_mm: number;
  board_height_mm: number;
  routing_completion_pct: number;
  error_count: number;
  warning_count: number;
  element_types: string[];
}

export function calculateBoardStats(circuitJson: CircuitElement[]): BoardStats {
  const sourceComponents = getSourceComponents(circuitJson);
  const sourceTraces = getSourceTraces(circuitJson);
  const pcbTraces = getPcbTraces(circuitJson);
  const pcbVias = getPcbVias(circuitJson);
  const pcbPads = getPcbSmtPads(circuitJson);
  const pcbBoard = getPcbBoard(circuitJson);
  const traceErrors = getPcbTraceErrors(circuitJson);
  const allErrors = getErrors(circuitJson);

  const boardWidth = pcbBoard?.width ?? 0;
  const boardHeight = pcbBoard?.height ?? 0;

  // Routing completion: compare successful pcb_traces to source_traces.
  // pcb_trace_errors include both unrouted traces AND overlap/clearance issues
  // on routed traces. A trace can be "routed" but have errors.
  // Best metric: pcb_trace count vs source_trace count.
  const totalSourceTraces = sourceTraces.length;
  const routedPcbTraces = pcbTraces.length;
  const routingPct =
    totalSourceTraces > 0
      ? Math.max(0, Math.min(100, Math.round((routedPcbTraces / totalSourceTraces) * 100)))
      : 100;

  const elementTypes = [...new Set(circuitJson.map((el) => el.type))];

  return {
    component_count: sourceComponents.length,
    net_count: sourceTraces.length,
    trace_count: pcbTraces.length,
    via_count: pcbVias.length,
    pad_count: pcbPads.length,
    board_area_mm2: boardWidth * boardHeight,
    board_width_mm: boardWidth,
    board_height_mm: boardHeight,
    routing_completion_pct: routingPct,
    error_count: allErrors.filter((e) => e.type.includes("error")).length,
    warning_count: allErrors.filter((e) => e.type.includes("warning")).length,
    element_types: elementTypes,
  };
}

export interface DrcViolation {
  type: string;
  severity: "error" | "warning";
  message: string;
  element_type: string;
  element_id?: string;
}

export function runBasicDrc(
  circuitJson: CircuitElement[],
  minTraceWidth: number,
  minClearance: number
): DrcViolation[] {
  const violations: DrcViolation[] = [];

  // Check for trace errors from tscircuit
  const traceErrors = getPcbTraceErrors(circuitJson);
  for (const err of traceErrors) {
    violations.push({
      type: "unrouted_trace",
      severity: "error",
      message: err.message || "Trace could not be routed",
      element_type: err.type,
      element_id: err.pcb_trace_error_id,
    });
  }

  // Check for generic errors (exclude supplier fetch errors which are environment-specific)
  const errors = circuitJson.filter(
    (el) =>
      el.type.includes("error") &&
      el.type !== "pcb_trace_error" &&
      el.type !== "unknown_error_finding_part"
  );
  for (const err of errors) {
    violations.push({
      type: err.type,
      severity: "error",
      message: err.message || `${err.type} detected`,
      element_type: err.type,
      element_id: err[`${err.type}_id`],
    });
  }

  // Check for warnings
  const warnings = circuitJson.filter((el) => el.type.includes("warning"));
  for (const warn of warnings) {
    violations.push({
      type: warn.type,
      severity: "warning",
      message: warn.message || `${warn.type} detected`,
      element_type: warn.type,
    });
  }

  // Check PCB trace widths against design rules
  const pcbTraces = getPcbTraces(circuitJson);
  for (const trace of pcbTraces) {
    if (trace.route) {
      for (const segment of trace.route) {
        if (segment.width !== undefined && segment.width < minTraceWidth) {
          violations.push({
            type: "min_trace_width",
            severity: "warning",
            message: `Trace width ${segment.width}mm is below minimum ${minTraceWidth}mm`,
            element_type: "pcb_trace",
            element_id: trace.pcb_trace_id,
          });
          break; // One violation per trace is enough
        }
      }
    }
  }

  return violations;
}

export function generateBom(circuitJson: CircuitElement[]): Array<{
  reference: string;
  type: string;
  value: string;
  footprint: string;
  quantity: number;
}> {
  const components = getSourceComponents(circuitJson);
  const bomEntries: Array<{
    reference: string;
    type: string;
    value: string;
    footprint: string;
    quantity: number;
  }> = [];

  for (const comp of components) {
    const entry = {
      reference: comp.name || comp.source_component_id || "?",
      type: comp.ftype || comp.component_type || "unknown",
      value:
        comp.resistance ||
        comp.capacitance ||
        comp.inductance ||
        comp.value ||
        "",
      footprint: comp.footprint || "",
      quantity: 1,
    };
    bomEntries.push(entry);
  }

  return bomEntries;
}

export function generatePickAndPlace(circuitJson: CircuitElement[]): Array<{
  reference: string;
  x_mm: number;
  y_mm: number;
  rotation_deg: number;
  layer: string;
  footprint: string;
}> {
  const pcbComponents = getPcbComponents(circuitJson);
  const sourceComponents = getSourceComponents(circuitJson);

  return pcbComponents.map((pcbComp) => {
    const sourceComp = sourceComponents.find(
      (sc) => sc.source_component_id === pcbComp.source_component_id
    );
    return {
      reference: sourceComp?.name || pcbComp.pcb_component_id || "?",
      x_mm: pcbComp.center?.x ?? 0,
      y_mm: pcbComp.center?.y ?? 0,
      rotation_deg: pcbComp.rotation ?? 0,
      layer: pcbComp.layer ?? "top",
      footprint: sourceComp?.footprint || "",
    };
  });
}
