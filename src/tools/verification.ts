/**
 * Verification Tools: DRC, ERC, manufacturability checks, board stats.
 */

import { z } from "zod";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { CircuitManager } from "../engine/circuit-manager.js";
import {
  runBasicDrc,
  calculateBoardStats,
  getErrors,
  getSourceComponents,
  getSourcePorts,
  getSourceTraces,
} from "../engine/circuit-json-utils.js";
import { FAB_PRESETS } from "../types/index.js";

export function registerVerificationTools(server: McpServer, manager: CircuitManager) {
  server.tool(
    "pcb_run_drc",
    "Run Design Rule Check on the current board",
    {},
    async () => {
      const renderResult = await manager.ensureRendered();
      if (!renderResult.success) {
        return {
          content: [{ type: "text", text: JSON.stringify(renderResult, null, 2) }],
        };
      }

      const circuitJson = manager.getCircuitJson();
      const rules = manager.getDesignRules();
      const violations = runBasicDrc(
        circuitJson,
        rules.min_trace_width_mm,
        rules.min_clearance_mm
      );

      const errorCount = violations.filter((v) => v.severity === "error").length;
      const warningCount = violations.filter((v) => v.severity === "warning").length;

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                success: true,
                data: {
                  total_violations: violations.length,
                  errors: errorCount,
                  warnings: warningCount,
                  violations,
                  design_rules: rules,
                  pass: errorCount === 0,
                  message: errorCount === 0
                    ? `DRC passed with ${warningCount} warning(s)`
                    : `DRC failed: ${errorCount} error(s), ${warningCount} warning(s)`,
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
    "pcb_run_erc",
    "Run Electrical Rules Check on the schematic",
    {},
    async () => {
      const renderResult = await manager.ensureRendered();
      if (!renderResult.success) {
        return {
          content: [{ type: "text", text: JSON.stringify(renderResult, null, 2) }],
        };
      }

      const circuitJson = manager.getCircuitJson();
      const sourceComponents = getSourceComponents(circuitJson);
      const sourcePorts = getSourcePorts(circuitJson);
      const sourceTraces = getSourceTraces(circuitJson);
      const errors = getErrors(circuitJson);

      // Check for unconnected pins
      const connectedPortIds = new Set<string>();
      for (const trace of sourceTraces) {
        const ports = trace.connected_source_port_ids || [];
        for (const portId of ports) {
          connectedPortIds.add(portId);
        }
      }

      const unconnectedPorts = sourcePorts.filter(
        (p) => !connectedPortIds.has(p.source_port_id)
      );

      // Group unconnected by component
      const unconnectedByComponent: Record<string, string[]> = {};
      for (const port of unconnectedPorts) {
        const comp = sourceComponents.find(
          (c) => c.source_component_id === port.source_component_id
        );
        const compName = comp?.name || port.source_component_id || "unknown";
        if (!unconnectedByComponent[compName]) {
          unconnectedByComponent[compName] = [];
        }
        unconnectedByComponent[compName].push(port.name || port.source_port_id);
      }

      const ercErrors = errors.filter(
        (e) =>
          e.type.includes("erc") ||
          e.type.includes("electrical") ||
          e.type.includes("pin_missing")
      );

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                success: true,
                data: {
                  total_ports: sourcePorts.length,
                  connected_ports: connectedPortIds.size,
                  unconnected_ports: unconnectedPorts.length,
                  unconnected_by_component: unconnectedByComponent,
                  erc_errors: ercErrors.map((e) => ({
                    type: e.type,
                    message: e.message || e.type,
                  })),
                  pass: ercErrors.length === 0 && unconnectedPorts.length === 0,
                  message:
                    unconnectedPorts.length === 0
                      ? "ERC passed: all ports connected"
                      : `ERC: ${unconnectedPorts.length} unconnected ports across ${Object.keys(unconnectedByComponent).length} components`,
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
    "pcb_check_manufacturability",
    "Verify design meets fab house specifications",
    {
      fab_house: z
        .enum(["jlcpcb", "pcbway", "oshpark"])
        .default("jlcpcb")
        .describe("Target fab house"),
    },
    async (args) => {
      const renderResult = await manager.ensureRendered();
      if (!renderResult.success) {
        return {
          content: [{ type: "text", text: JSON.stringify(renderResult, null, 2) }],
        };
      }

      const presetKey =
        args.fab_house === "jlcpcb"
          ? "jlcpcb_2layer"
          : args.fab_house === "pcbway"
            ? "pcbway_standard"
            : "oshpark";
      const fabRules = FAB_PRESETS[presetKey];

      const circuitJson = manager.getCircuitJson();
      const violations = runBasicDrc(
        circuitJson,
        fabRules?.min_trace_width_mm ?? 0.127,
        fabRules?.min_clearance_mm ?? 0.127
      );

      const stats = calculateBoardStats(circuitJson);

      const checks = [
        {
          rule: "Minimum trace width",
          required: `${fabRules?.min_trace_width_mm ?? 0.127}mm`,
          pass: !violations.some((v) => v.type === "min_trace_width"),
        },
        {
          rule: "Minimum clearance",
          required: `${fabRules?.min_clearance_mm ?? 0.127}mm`,
          pass: !violations.some((v) => v.type === "min_clearance"),
        },
        {
          rule: "Routing completion",
          required: "100%",
          actual: `${stats.routing_completion_pct}%`,
          pass: stats.routing_completion_pct === 100,
        },
        {
          rule: "No DRC errors",
          required: "0 errors",
          actual: `${stats.error_count} errors`,
          pass: stats.error_count === 0,
        },
      ];

      const allPass = checks.every((c) => c.pass);

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                success: true,
                data: {
                  fab_house: args.fab_house,
                  overall_pass: allPass,
                  checks,
                  violations: violations.filter((v) => v.severity === "error"),
                  board_stats: stats,
                  message: allPass
                    ? `Design passes ${args.fab_house} manufacturability checks`
                    : `Design has ${checks.filter((c) => !c.pass).length} manufacturability issue(s) for ${args.fab_house}`,
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
    "pcb_get_board_stats",
    "Return comprehensive board statistics",
    {},
    async () => {
      const renderResult = await manager.ensureRendered();
      if (!renderResult.success) {
        return {
          content: [{ type: "text", text: JSON.stringify(renderResult, null, 2) }],
        };
      }

      const circuitJson = manager.getCircuitJson();
      const stats = calculateBoardStats(circuitJson);

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({ success: true, data: stats }, null, 2),
          },
        ],
      };
    }
  );
}
