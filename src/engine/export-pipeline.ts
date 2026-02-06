/**
 * Export pipeline: Converts Circuit JSON to various output formats.
 *
 * Gerber: Uses circuit-json-to-gerber for manufacturing files
 * BOM: Extracts source_component elements
 * SVG: Generates basic SVG from pcb elements
 * Pick & Place: Generates CSV for automated assembly
 * SPICE: Generates basic SPICE netlist
 */

import {
  convertSoupToGerberCommands,
  stringifyGerberCommandLayers,
  convertSoupToExcellonDrillCommands,
  stringifyExcellonDrill,
} from "circuit-json-to-gerber";
import type { CircuitElement } from "./circuit-json-utils.js";
import {
  generateBom,
  generatePickAndPlace,
  getSourceComponents,
  getSourceTraces,
  getSourcePorts,
  getPcbComponents,
  getPcbSmtPads,
  getPcbTraces,
  getPcbBoard,
  getPcbPorts,
} from "./circuit-json-utils.js";
import * as fs from "node:fs";
import * as path from "node:path";

export interface GerberExportResult {
  layers: Record<string, string>; // layer name -> gerber file content
  drills: {
    plated: string;
    unplated: string;
  };
  file_count: number;
}

export function exportGerbers(circuitJson: CircuitElement[]): GerberExportResult {
  // circuit-json-to-gerber functions take the soup array directly
  const gerberCommands = convertSoupToGerberCommands(circuitJson as any);

  const layers = stringifyGerberCommandLayers(gerberCommands);

  const drillCommands = convertSoupToExcellonDrillCommands({
    circuitJson: circuitJson as any,
    is_plated: true,
  });
  const platedDrill = stringifyExcellonDrill(drillCommands);

  const unplatedDrillCommands = convertSoupToExcellonDrillCommands({
    circuitJson: circuitJson as any,
    is_plated: false,
  });
  const unplatedDrill = stringifyExcellonDrill(unplatedDrillCommands);

  return {
    layers,
    drills: {
      plated: platedDrill,
      unplated: unplatedDrill,
    },
    file_count: Object.keys(layers).length + 2,
  };
}

export function writeGerberZip(
  gerberResult: GerberExportResult,
  outputPath: string
): string {
  // Since we don't have a zip library, write individual files to a directory
  const dir = outputPath.replace(/\.zip$/, "");
  fs.mkdirSync(dir, { recursive: true });

  for (const [layerName, content] of Object.entries(gerberResult.layers)) {
    const filename = `${layerName}.gbr`;
    fs.writeFileSync(path.join(dir, filename), content);
  }

  fs.writeFileSync(path.join(dir, "plated.drl"), gerberResult.drills.plated);
  fs.writeFileSync(path.join(dir, "unplated.drl"), gerberResult.drills.unplated);

  return dir;
}

export function exportBomCsv(circuitJson: CircuitElement[]): string {
  const bom = generateBom(circuitJson);
  const lines = ["Reference,Type,Value,Footprint,Quantity"];
  for (const entry of bom) {
    lines.push(
      `"${entry.reference}","${entry.type}","${entry.value}","${entry.footprint}",${entry.quantity}`
    );
  }
  return lines.join("\n");
}

export function exportBomJson(circuitJson: CircuitElement[]): string {
  const bom = generateBom(circuitJson);
  return JSON.stringify(bom, null, 2);
}

export function exportPickAndPlaceCsv(circuitJson: CircuitElement[]): string {
  const pnp = generatePickAndPlace(circuitJson);
  const lines = ["Reference,X_mm,Y_mm,Rotation_deg,Layer,Footprint"];
  for (const entry of pnp) {
    lines.push(
      `"${entry.reference}",${entry.x_mm.toFixed(3)},${entry.y_mm.toFixed(3)},${entry.rotation_deg},"${entry.layer}","${entry.footprint}"`
    );
  }
  return lines.join("\n");
}

export function exportSvg(
  circuitJson: CircuitElement[],
  view: "pcb" | "schematic" = "pcb"
): string {
  const board = getPcbBoard(circuitJson);
  const boardW = board?.width ?? 50;
  const boardH = board?.height ?? 50;

  // Scale: 1mm = 10px
  const scale = 10;
  const svgW = boardW * scale + 40;
  const svgH = boardH * scale + 40;
  const offsetX = svgW / 2;
  const offsetY = svgH / 2;

  const lines: string[] = [];
  lines.push(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${svgW} ${svgH}" width="${svgW}" height="${svgH}">`
  );
  lines.push(`<style>`);
  lines.push(`  .board { fill: #1a5c1a; stroke: #333; stroke-width: 1; }`);
  lines.push(`  .pad { fill: #c0a000; stroke: #907000; stroke-width: 0.5; }`);
  lines.push(`  .trace { stroke: #c0a000; stroke-linecap: round; fill: none; }`);
  lines.push(`  .silkscreen { fill: none; stroke: white; stroke-width: 0.5; }`);
  lines.push(`  .component-label { font-family: monospace; font-size: 4px; fill: white; text-anchor: middle; }`);
  lines.push(`</style>`);

  // Board outline
  lines.push(
    `<rect class="board" x="${offsetX - (boardW * scale) / 2}" y="${offsetY - (boardH * scale) / 2}" width="${boardW * scale}" height="${boardH * scale}" rx="2" />`
  );

  if (view === "pcb") {
    // PCB pads
    const pads = getPcbSmtPads(circuitJson);
    for (const pad of pads) {
      const x = offsetX + (pad.x ?? 0) * scale;
      const y = offsetY - (pad.y ?? 0) * scale; // SVG Y is inverted
      const w = (pad.width ?? 1) * scale;
      const h = (pad.height ?? 1) * scale;
      if (pad.shape === "circle" || pad.shape === "circle_with_rounded_rect") {
        const r = Math.max(w, h) / 2;
        lines.push(`<circle class="pad" cx="${x}" cy="${y}" r="${r}" />`);
      } else {
        lines.push(
          `<rect class="pad" x="${x - w / 2}" y="${y - h / 2}" width="${w}" height="${h}" rx="0.5" />`
        );
      }
    }

    // PCB traces
    const traces = getPcbTraces(circuitJson);
    for (const trace of traces) {
      if (trace.route && trace.route.length >= 2) {
        const points = trace.route
          .filter((p: any) => p.x !== undefined && p.y !== undefined)
          .map((p: any) => `${offsetX + p.x * scale},${offsetY - p.y * scale}`)
          .join(" ");
        const width = (trace.route[0]?.width ?? 0.15) * scale;
        if (points) {
          lines.push(
            `<polyline class="trace" points="${points}" stroke-width="${width}" />`
          );
        }
      }
    }

    // Component labels
    const pcbComps = getPcbComponents(circuitJson);
    const sourceComps = getSourceComponents(circuitJson);
    for (const pcbComp of pcbComps) {
      const sc = sourceComps.find(
        (s) => s.source_component_id === pcbComp.source_component_id
      );
      if (sc?.name) {
        const x = offsetX + (pcbComp.center?.x ?? 0) * scale;
        const y = offsetY - (pcbComp.center?.y ?? 0) * scale;
        lines.push(
          `<text class="component-label" x="${x}" y="${y + 1}">${sc.name}</text>`
        );
      }
    }
  }

  lines.push(`</svg>`);
  return lines.join("\n");
}

export function exportSpiceNetlist(circuitJson: CircuitElement[]): string {
  const components = getSourceComponents(circuitJson);
  const traces = getSourceTraces(circuitJson);
  const ports = getSourcePorts(circuitJson);

  const lines: string[] = [];
  lines.push("* SPICE netlist generated by pcb-mcp-server");
  lines.push(`* Components: ${components.length}`);
  lines.push("");

  // Build port-to-node mapping
  const portToNode = new Map<string, string>();
  let nodeCounter = 1;

  // Map trace connections to nodes
  for (const trace of traces) {
    const connectedPorts = trace.connected_source_port_ids || [];
    const nodeName = `N${nodeCounter++}`;
    for (const portId of connectedPorts) {
      portToNode.set(portId, nodeName);
    }
  }

  // Generate component instances
  for (const comp of components) {
    const name = comp.name || comp.source_component_id || "?";
    const compPorts = ports.filter(
      (p) => p.source_component_id === comp.source_component_id
    );

    const nodeNames = compPorts.map(
      (p) => portToNode.get(p.source_port_id) || "0"
    );

    if (comp.resistance) {
      lines.push(`R_${name} ${nodeNames[0] || "0"} ${nodeNames[1] || "0"} ${comp.resistance}`);
    } else if (comp.capacitance) {
      lines.push(`C_${name} ${nodeNames[0] || "0"} ${nodeNames[1] || "0"} ${comp.capacitance}`);
    } else if (comp.inductance) {
      lines.push(`L_${name} ${nodeNames[0] || "0"} ${nodeNames[1] || "0"} ${comp.inductance}`);
    } else {
      lines.push(`* ${name}: ${comp.ftype || "unknown"} (${nodeNames.join(", ")})`);
    }
  }

  lines.push("");
  lines.push(".end");
  return lines.join("\n");
}

export function exportCircuitJson(circuitJson: CircuitElement[]): string {
  return JSON.stringify(circuitJson, null, 2);
}
