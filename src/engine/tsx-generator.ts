/**
 * TSX Generator: Converts structured circuit state into tscircuit TSX code.
 *
 * Design decision: We store circuit state as structured objects and serialize
 * to TSX for rendering via @tscircuit/eval's CircuitRunner. This avoids
 * brittle string manipulation and makes modifications (add/remove/update)
 * clean and predictable.
 */

import type {
  ComponentDef,
  TraceDef,
  NetDef,
  GroupDef,
  BoardConfig,
  MountingHoleDef,
} from "../types/index.js";

function escapeAttr(val: string): string {
  return val.replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function generateComponentTsx(comp: ComponentDef): string {
  const attrs: string[] = [`name="${escapeAttr(comp.name)}"`];

  // Type-specific primary property
  switch (comp.type) {
    case "resistor":
      if (comp.properties.resistance) attrs.push(`resistance="${comp.properties.resistance}"`);
      break;
    case "capacitor":
      if (comp.properties.capacitance) attrs.push(`capacitance="${comp.properties.capacitance}"`);
      break;
    case "inductor":
      if (comp.properties.inductance) attrs.push(`inductance="${comp.properties.inductance}"`);
      break;
    case "led":
    case "diode":
      if (comp.properties.color) attrs.push(`color="${comp.properties.color}"`);
      break;
    case "crystal":
      if (comp.properties.frequency) attrs.push(`frequency="${comp.properties.frequency}"`);
      break;
    default:
      break;
  }

  // Footprint
  attrs.push(`footprint="${escapeAttr(comp.footprint)}"`);

  // Position
  if (comp.pcb_x_mm !== 0 || comp.pcb_y_mm !== 0) {
    attrs.push(`pcbX={${comp.pcb_x_mm}}`);
    attrs.push(`pcbY={${comp.pcb_y_mm}}`);
  }

  if (comp.rotation_deg !== 0) {
    attrs.push(`pcbRotation={${comp.rotation_deg}}`);
  }

  if (comp.layer === "bottom") {
    attrs.push(`layer="bottom"`);
  }

  // For chip components, add pinLabels if provided
  if (comp.type === "chip" && comp.properties.pinLabels) {
    try {
      const pinLabels = JSON.parse(comp.properties.pinLabels);
      const pinLabelStr = Object.entries(pinLabels)
        .map(([k, v]) => `${k}: "${v}"`)
        .join(", ");
      attrs.push(`pinLabels={{ ${pinLabelStr} }}`);
    } catch {
      // If pinLabels isn't valid JSON, skip
    }
  }

  // schematicSymbolName for chips
  if (comp.properties.schematicSymbolName) {
    attrs.push(`schematicSymbolName="${comp.properties.schematicSymbolName}"`);
  }

  // Generic properties passed as supplierPartNumbers or other attributes
  for (const [key, val] of Object.entries(comp.properties)) {
    if (
      [
        "resistance",
        "capacitance",
        "inductance",
        "color",
        "frequency",
        "pinLabels",
        "schematicSymbolName",
      ].includes(key)
    ) {
      continue; // Already handled above
    }
    // Pass remaining properties as JSX attributes
    if (key === "pinCount") {
      attrs.push(`pinCount={${val}}`);
    }
  }

  // Determine element tag
  const tagMap: Record<string, string> = {
    resistor: "resistor",
    capacitor: "capacitor",
    inductor: "inductor",
    led: "led",
    diode: "diode",
    chip: "chip",
    crystal: "crystal",
    connector: "chip", // connectors use chip with pinLabels
    button: "chip",
    voltage_regulator: "chip",
    usb_c: "chip",
    transistor: "chip",
    fuse: "chip",
    switch: "chip",
    header: "chip",
  };

  const tag = tagMap[comp.type] || "chip";
  return `    <${tag} ${attrs.join(" ")} />`;
}

function generateTraceTsx(trace: TraceDef): string {
  const attrs = [`from="${escapeAttr(trace.from)}" to="${escapeAttr(trace.to)}"`];
  if (trace.width_mm) {
    attrs.push(`thickness={${trace.width_mm}}`);
  }
  return `    <trace ${attrs.join(" ")} />`;
}

function generateNetTsx(net: NetDef): string {
  // Nets in tscircuit are implemented as multiple traces connecting
  // all components to the same named net
  const lines: string[] = [];
  if (net.connections.length >= 2) {
    for (let i = 1; i < net.connections.length; i++) {
      lines.push(
        `    <trace from="${escapeAttr(net.connections[0])}" to="${escapeAttr(net.connections[i])}" />`
      );
    }
  }
  return lines.join("\n");
}

function generateMountingHoleTsx(hole: MountingHoleDef): string {
  return `    <chip name="${escapeAttr(hole.name)}" footprint="pinrow1" pcbX={${hole.x_mm}} pcbY={${hole.y_mm}} />`;
}

export function generateFullTsx(
  board: BoardConfig,
  components: Map<string, ComponentDef>,
  traces: TraceDef[],
  nets: NetDef[],
  groups: GroupDef[],
  mountingHoles: MountingHoleDef[]
): string {
  const lines: string[] = [];

  lines.push(`circuit.add(`);
  lines.push(`  <board width="${board.width_mm}mm" height="${board.height_mm}mm">`);

  // Add components (grouped and ungrouped)
  const groupedComponents = new Set<string>();
  for (const group of groups) {
    const groupAttrs: string[] = [`name="${escapeAttr(group.name)}"`];
    if (group.pcb_x_mm !== undefined) groupAttrs.push(`pcbX={${group.pcb_x_mm}}`);
    if (group.pcb_y_mm !== undefined) groupAttrs.push(`pcbY={${group.pcb_y_mm}}`);

    lines.push(`    <group ${groupAttrs.join(" ")}>`);
    for (const compName of group.components) {
      const comp = components.get(compName);
      if (comp) {
        lines.push(`  ${generateComponentTsx(comp)}`);
        groupedComponents.add(compName);
      }
    }
    lines.push(`    </group>`);
  }

  // Ungrouped components
  for (const [name, comp] of components) {
    if (!groupedComponents.has(name)) {
      lines.push(generateComponentTsx(comp));
    }
  }

  // Mounting holes
  for (const hole of mountingHoles) {
    lines.push(generateMountingHoleTsx(hole));
  }

  // Traces
  for (const trace of traces) {
    lines.push(generateTraceTsx(trace));
  }

  // Nets (expanded to traces)
  for (const net of nets) {
    const netTsx = generateNetTsx(net);
    if (netTsx) lines.push(netTsx);
  }

  lines.push(`  </board>`);
  lines.push(`)`);

  return lines.join("\n");
}
