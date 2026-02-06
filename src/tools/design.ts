/**
 * Circuit Design Tools: create, modify, query circuit state.
 */

import { z } from "zod";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { CircuitManager } from "../engine/circuit-manager.js";

export function registerDesignTools(server: McpServer, manager: CircuitManager) {
  server.tool(
    "pcb_create_project",
    "Creates a new circuit project with board specs",
    {
      name: z.string().describe("Project name"),
      board_width_mm: z.number().describe("Board width in mm"),
      board_height_mm: z.number().describe("Board height in mm"),
      layer_count: z.number().default(2).describe("Number of PCB layers (2 or 4)"),
      description: z.string().optional().describe("Project description"),
      form_factor: z
        .enum(["custom", "arduino_shield", "raspberry_pi_hat"])
        .optional()
        .describe("Board form factor template"),
    },
    async (args) => {
      const result = manager.createProject(
        args.name,
        args.board_width_mm,
        args.board_height_mm,
        args.layer_count,
        args.description,
        args.form_factor
      );
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    }
  );

  server.tool(
    "pcb_add_component",
    "Adds an electronic component to the circuit",
    {
      component_type: z
        .enum([
          "resistor", "capacitor", "inductor", "led", "diode", "chip",
          "crystal", "connector", "button", "voltage_regulator", "usb_c",
          "transistor", "fuse", "switch", "header",
        ])
        .describe("Component type"),
      name: z.string().describe("Unique reference designator (e.g., R1, C1, U1)"),
      properties: z
        .record(z.string())
        .default({})
        .describe('Component properties (e.g., {"resistance": "10k"})'),
      footprint: z.string().describe('Footprint string (e.g., "0805", "soic8", "dip16")'),
      pcb_x_mm: z.number().optional().describe("X position on PCB in mm"),
      pcb_y_mm: z.number().optional().describe("Y position on PCB in mm"),
      rotation_deg: z.number().optional().describe("Rotation in degrees"),
      layer: z.enum(["top", "bottom"]).optional().describe("PCB layer"),
    },
    async (args) => {
      if (!manager.isProjectInitialized()) {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                success: false,
                errors: ["No project initialized. Call pcb_create_project first."],
              }),
            },
          ],
        };
      }
      const result = manager.addComponent(
        args.component_type,
        args.name,
        args.properties,
        args.footprint,
        args.pcb_x_mm,
        args.pcb_y_mm,
        args.rotation_deg,
        args.layer
      );
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    }
  );

  server.tool(
    "pcb_add_trace",
    "Connects two component pins with a trace",
    {
      from: z.string().describe('Source pin selector (e.g., ".R1 > .pin1", ".U1 > .VCC")'),
      to: z.string().describe('Destination pin selector'),
      width_mm: z.number().optional().describe("Trace width in mm"),
    },
    async (args) => {
      if (!manager.isProjectInitialized()) {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                success: false,
                errors: ["No project initialized. Call pcb_create_project first."],
              }),
            },
          ],
        };
      }
      const result = manager.addTrace(args.from, args.to, args.width_mm);
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    }
  );

  server.tool(
    "pcb_add_net",
    "Creates a named power net and connects components to it",
    {
      net_name: z.string().describe('Net name (e.g., "VCC", "GND", "3V3")'),
      connections: z
        .array(z.string())
        .describe('Pin selectors to connect (e.g., [".R1 > .pin1", ".C1 > .pos"])'),
    },
    async (args) => {
      const result = manager.addNet(args.net_name, args.connections);
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    }
  );

  server.tool(
    "pcb_add_group",
    "Groups components for layout organization",
    {
      name: z.string().describe("Group name"),
      components: z.array(z.string()).describe("Component names to include"),
      pcb_x_mm: z.number().optional().describe("Group X position"),
      pcb_y_mm: z.number().optional().describe("Group Y position"),
    },
    async (args) => {
      const result = manager.addGroup(
        args.name,
        args.components,
        args.pcb_x_mm,
        args.pcb_y_mm
      );
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    }
  );

  server.tool(
    "pcb_modify_component",
    "Updates an existing component's properties or position",
    {
      name: z.string().describe("Component reference designator"),
      updates: z
        .record(z.any())
        .describe('Properties to update (e.g., {"pcb_x_mm": 5, "resistance": "4.7k"})'),
    },
    async (args) => {
      const result = manager.modifyComponent(args.name, args.updates);
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    }
  );

  server.tool(
    "pcb_remove_component",
    "Removes a component and its connected traces",
    {
      name: z.string().describe("Component reference designator to remove"),
    },
    async (args) => {
      const result = manager.removeComponent(args.name);
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    }
  );

  server.tool(
    "pcb_get_circuit_state",
    "Returns the current circuit state: components, nets, traces, board info",
    {},
    async () => {
      const state = manager.getState();
      return {
        content: [{ type: "text", text: JSON.stringify(state, null, 2) }],
      };
    }
  );

  server.tool(
    "pcb_get_tsx_source",
    "Returns the current TSX source code of the circuit",
    {},
    async () => {
      await manager.ensureRendered();
      const tsx = manager.getTsxSource();
      return {
        content: [
          {
            type: "text",
            text: tsx || "No TSX source generated yet. Add components and traces first.",
          },
        ],
      };
    }
  );

  server.tool(
    "pcb_set_tsx_source",
    "Directly sets the TSX source code (for advanced users / AI-generated full circuits)",
    {
      tsx_code: z.string().describe("Complete tscircuit TSX code"),
    },
    async (args) => {
      const result = await manager.renderFromTsx(args.tsx_code);
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    }
  );
}
