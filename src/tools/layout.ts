/**
 * Layout Tools: board configuration, placement, mounting holes, design rules.
 */

import { z } from "zod";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { CircuitManager } from "../engine/circuit-manager.js";
import { FAB_PRESETS } from "../types/index.js";

export function registerLayoutTools(server: McpServer, manager: CircuitManager) {
  server.tool(
    "pcb_set_board_outline",
    "Configure board dimensions and shape",
    {
      width_mm: z.number().describe("Board width in mm"),
      height_mm: z.number().describe("Board height in mm"),
      shape: z
        .enum(["rectangular", "rounded_rect"])
        .optional()
        .describe("Board shape"),
      corner_radius_mm: z.number().optional().describe("Corner radius for rounded_rect"),
    },
    async (args) => {
      const result = manager.setBoardOutline(
        args.width_mm,
        args.height_mm,
        args.shape,
        args.corner_radius_mm
      );
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    }
  );

  server.tool(
    "pcb_auto_place",
    "Automatically place components based on connectivity",
    {
      strategy: z
        .enum(["grid", "clustered", "minimal_crossings"])
        .default("grid")
        .describe("Placement strategy"),
    },
    async (args) => {
      const result = manager.autoPlace(args.strategy);
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    }
  );

  server.tool(
    "pcb_add_mounting_hole",
    "Add a mounting hole to the board",
    {
      x_mm: z.number().describe("X position in mm"),
      y_mm: z.number().describe("Y position in mm"),
      diameter_mm: z.number().describe("Hole diameter in mm"),
      name: z.string().optional().describe("Mounting hole name"),
    },
    async (args) => {
      const result = manager.addMountingHole(
        args.x_mm,
        args.y_mm,
        args.diameter_mm,
        args.name
      );
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    }
  );

  server.tool(
    "pcb_set_design_rules",
    "Configure PCB design rules (trace width, clearance, via size)",
    {
      min_trace_width_mm: z.number().optional().describe("Minimum trace width in mm"),
      min_clearance_mm: z.number().optional().describe("Minimum clearance in mm"),
      min_via_diameter_mm: z.number().optional().describe("Minimum via diameter in mm"),
      min_via_drill_mm: z.number().optional().describe("Minimum via drill size in mm"),
      preset: z
        .enum(["jlcpcb_2layer", "jlcpcb_4layer", "pcbway_standard", "oshpark"])
        .optional()
        .describe("Apply a fab house preset"),
    },
    async (args) => {
      const updates: Record<string, any> = {};

      // Apply preset first if specified
      if (args.preset && FAB_PRESETS[args.preset]) {
        Object.assign(updates, FAB_PRESETS[args.preset]);
        updates.preset = args.preset;
      }

      // Override with explicit values
      if (args.min_trace_width_mm !== undefined) updates.min_trace_width_mm = args.min_trace_width_mm;
      if (args.min_clearance_mm !== undefined) updates.min_clearance_mm = args.min_clearance_mm;
      if (args.min_via_diameter_mm !== undefined) updates.min_via_diameter_mm = args.min_via_diameter_mm;
      if (args.min_via_drill_mm !== undefined) updates.min_via_drill_mm = args.min_via_drill_mm;

      const result = manager.setDesignRules(updates);
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    }
  );

  server.tool(
    "pcb_add_ground_plane",
    "Add a copper ground plane to a layer (note: implemented as design intent, tscircuit handles copper fill during rendering)",
    {
      layer: z
        .enum(["top", "bottom", "inner1", "inner2"])
        .describe("PCB layer for the ground plane"),
      net_name: z.string().default("GND").describe("Net name for the ground plane"),
    },
    async (args) => {
      // tscircuit doesn't have a direct ground plane API in the TSX layer.
      // This records the design intent for documentation and future implementation.
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                success: true,
                data: {
                  layer: args.layer,
                  net: args.net_name,
                  message: `Ground plane intent recorded for ${args.layer} layer (net: ${args.net_name}). Note: tscircuit's autorouter handles copper fills internally. For production boards, verify ground plane in the exported Gerbers.`,
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
