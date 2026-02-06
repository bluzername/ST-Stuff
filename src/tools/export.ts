/**
 * Export Tools: Gerber, BOM, SVG, Circuit JSON, 3D, Pick & Place, SPICE.
 */

import { z } from "zod";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { CircuitManager } from "../engine/circuit-manager.js";
import {
  exportGerbers,
  writeGerberZip,
  exportBomCsv,
  exportBomJson,
  exportSvg,
  exportCircuitJson,
  exportPickAndPlaceCsv,
  exportSpiceNetlist,
} from "../engine/export-pipeline.js";
import * as fs from "node:fs";
import * as path from "node:path";

const DEFAULT_OUTPUT_DIR = "/tmp/pcb-exports";

function ensureOutputDir(dir: string): void {
  fs.mkdirSync(dir, { recursive: true });
}

export function registerExportTools(server: McpServer, manager: CircuitManager) {
  server.tool(
    "pcb_export_gerbers",
    "Generate Gerber + Excellon drill files for PCB manufacturing",
    {
      output_path: z
        .string()
        .optional()
        .describe("Output directory path (default: /tmp/pcb-exports/gerbers)"),
    },
    async (args) => {
      const renderResult = await manager.ensureRendered();
      if (!renderResult.success) {
        return {
          content: [{ type: "text", text: JSON.stringify(renderResult, null, 2) }],
        };
      }

      const circuitJson = manager.getCircuitJson();
      if (circuitJson.length === 0) {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                success: false,
                errors: ["No circuit to export. Create a project and add components first."],
              }),
            },
          ],
        };
      }

      try {
        const gerberResult = exportGerbers(circuitJson);
        const outputDir = args.output_path || path.join(DEFAULT_OUTPUT_DIR, "gerbers");
        const resultPath = writeGerberZip(gerberResult, outputDir);

        const files = fs.readdirSync(resultPath);

        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(
                {
                  success: true,
                  data: {
                    output_path: resultPath,
                    file_count: gerberResult.file_count,
                    files,
                    layer_names: Object.keys(gerberResult.layers),
                    message: `Exported ${files.length} Gerber/drill files to ${resultPath}`,
                  },
                },
                null,
                2
              ),
            },
          ],
        };
      } catch (error: any) {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                success: false,
                errors: [`Gerber export failed: ${error.message}`],
              }),
            },
          ],
        };
      }
    }
  );

  server.tool(
    "pcb_export_bom",
    "Generate Bill of Materials",
    {
      format: z.enum(["csv", "json"]).default("csv").describe("Output format"),
      output_path: z.string().optional().describe("Output file path"),
    },
    async (args) => {
      const renderResult = await manager.ensureRendered();
      if (!renderResult.success) {
        return {
          content: [{ type: "text", text: JSON.stringify(renderResult, null, 2) }],
        };
      }

      const circuitJson = manager.getCircuitJson();
      const content =
        args.format === "csv"
          ? exportBomCsv(circuitJson)
          : exportBomJson(circuitJson);

      if (args.output_path) {
        ensureOutputDir(path.dirname(args.output_path));
        fs.writeFileSync(args.output_path, content);
      }

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                success: true,
                data: {
                  format: args.format,
                  output_path: args.output_path || null,
                  content,
                },
              },
              null,
              2
            ),
          },
        ],
      };
    }
  );

  server.tool(
    "pcb_export_svg",
    "Export board as SVG for visual review",
    {
      view: z
        .enum(["pcb", "schematic", "both"])
        .default("pcb")
        .describe("View type"),
      output_path: z.string().optional().describe("Output file path"),
    },
    async (args) => {
      const renderResult = await manager.ensureRendered();
      if (!renderResult.success) {
        return {
          content: [{ type: "text", text: JSON.stringify(renderResult, null, 2) }],
        };
      }

      const circuitJson = manager.getCircuitJson();
      const viewType = args.view === "both" ? "pcb" : args.view;
      const svgContent = exportSvg(circuitJson, viewType as "pcb" | "schematic");

      if (args.output_path) {
        ensureOutputDir(path.dirname(args.output_path));
        fs.writeFileSync(args.output_path, svgContent);
      }

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                success: true,
                data: {
                  view: args.view,
                  output_path: args.output_path || null,
                  svg_length: svgContent.length,
                  svg: args.output_path ? "(written to file)" : svgContent,
                },
              },
              null,
              2
            ),
          },
        ],
      };
    }
  );

  server.tool(
    "pcb_export_circuit_json",
    "Export raw Circuit JSON array",
    {
      output_path: z.string().optional().describe("Output file path"),
    },
    async (args) => {
      const renderResult = await manager.ensureRendered();
      if (!renderResult.success) {
        return {
          content: [{ type: "text", text: JSON.stringify(renderResult, null, 2) }],
        };
      }

      const circuitJson = manager.getCircuitJson();
      const content = exportCircuitJson(circuitJson);

      if (args.output_path) {
        ensureOutputDir(path.dirname(args.output_path));
        fs.writeFileSync(args.output_path, content);
      }

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                success: true,
                data: {
                  element_count: circuitJson.length,
                  output_path: args.output_path || null,
                  content: args.output_path ? "(written to file)" : JSON.parse(content),
                },
              },
              null,
              2
            ),
          },
        ],
      };
    }
  );

  server.tool(
    "pcb_export_3d_model",
    "Export 3D model of the board (requires @tscircuit/circuit-json-to-gltf)",
    {
      format: z.enum(["gltf", "glb"]).default("gltf").describe("3D format"),
    },
    async (args) => {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                success: false,
                errors: [
                  "3D model export requires @tscircuit/circuit-json-to-gltf which is not currently installed. " +
                  "This is a stretch goal feature. Use pcb_export_svg for visual preview instead.",
                ],
              },
              null,
              2
            ),
          },
        ],
      };
    }
  );

  server.tool(
    "pcb_export_pick_and_place",
    "Generate pick-and-place CSV for automated assembly",
    {
      format: z.enum(["csv"]).default("csv").describe("Output format"),
      output_path: z.string().optional().describe("Output file path"),
    },
    async (args) => {
      const renderResult = await manager.ensureRendered();
      if (!renderResult.success) {
        return {
          content: [{ type: "text", text: JSON.stringify(renderResult, null, 2) }],
        };
      }

      const circuitJson = manager.getCircuitJson();
      const content = exportPickAndPlaceCsv(circuitJson);

      if (args.output_path) {
        ensureOutputDir(path.dirname(args.output_path));
        fs.writeFileSync(args.output_path, content);
      }

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                success: true,
                data: {
                  format: args.format,
                  output_path: args.output_path || null,
                  content,
                },
              },
              null,
              2
            ),
          },
        ],
      };
    }
  );

  server.tool(
    "pcb_export_spice_netlist",
    "Generate SPICE netlist for simulation",
    {
      output_path: z.string().optional().describe("Output file path"),
    },
    async (args) => {
      const renderResult = await manager.ensureRendered();
      if (!renderResult.success) {
        return {
          content: [{ type: "text", text: JSON.stringify(renderResult, null, 2) }],
        };
      }

      const circuitJson = manager.getCircuitJson();
      const content = exportSpiceNetlist(circuitJson);

      if (args.output_path) {
        ensureOutputDir(path.dirname(args.output_path));
        fs.writeFileSync(args.output_path, content);
      }

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                success: true,
                data: {
                  output_path: args.output_path || null,
                  content,
                },
              },
              null,
              2
            ),
          },
        ],
      };
    }
  );
}
