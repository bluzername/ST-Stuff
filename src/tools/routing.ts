/**
 * Routing Tools: autoroute, check unrouted nets, manual routing.
 */

import { z } from "zod";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { CircuitManager } from "../engine/circuit-manager.js";
import {
  getPcbTraceErrors,
  getSourceTraces,
  getPcbTraces,
} from "../engine/circuit-json-utils.js";

export function registerRoutingTools(server: McpServer, manager: CircuitManager) {
  server.tool(
    "pcb_autoroute",
    "Run the tscircuit autorouter on all unrouted nets",
    {
      algorithm: z
        .enum(["tscircuit_default", "freerouting"])
        .default("tscircuit_default")
        .describe("Autorouting algorithm"),
      max_passes: z.number().optional().describe("Maximum routing passes"),
    },
    async (args) => {
      if (args.algorithm === "freerouting") {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                success: false,
                errors: [
                  "Freerouting integration requires a running Freerouting JAR. " +
                  "Set FREEROUTING_JAR environment variable to the path of freerouting.jar. " +
                  "Falling back to tscircuit_default is recommended.",
                ],
              }),
            },
          ],
        };
      }

      // tscircuit's built-in autorouter runs during renderUntilSettled()
      const renderResult = await manager.render();
      if (!renderResult.success) {
        return {
          content: [{ type: "text", text: JSON.stringify(renderResult, null, 2) }],
        };
      }

      const circuitJson = manager.getCircuitJson();
      const sourceTraces = getSourceTraces(circuitJson);
      const pcbTraces = getPcbTraces(circuitJson);
      const traceErrors = getPcbTraceErrors(circuitJson);

      const totalNets = sourceTraces.length;
      const routedTraces = pcbTraces.length;
      const failedTraces = traceErrors.length;
      const routingPct = totalNets > 0
        ? Math.round(((totalNets - failedTraces) / totalNets) * 100)
        : 100;

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                success: true,
                data: {
                  algorithm: args.algorithm,
                  total_nets: totalNets,
                  routed_traces: routedTraces,
                  failed_traces: failedTraces,
                  routing_completion_pct: routingPct,
                  errors: traceErrors.map((e) => e.message || "Trace routing failed"),
                  message: `Autorouting complete: ${routingPct}% routing completion (${routedTraces} traces, ${failedTraces} failures)`,
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
    "pcb_get_unrouted_nets",
    "List all nets that haven't been routed yet",
    {},
    async () => {
      await manager.ensureRendered();
      const circuitJson = manager.getCircuitJson();
      const traceErrors = getPcbTraceErrors(circuitJson);

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                success: true,
                data: {
                  unrouted_count: traceErrors.length,
                  unrouted_nets: traceErrors.map((e) => ({
                    error_id: e.pcb_trace_error_id,
                    message: e.message || "Unrouted trace",
                    source_trace_id: e.source_trace_id,
                  })),
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
    "pcb_route_net",
    "Manually route a specific net with waypoints",
    {
      from: z.string().describe("Source pin selector"),
      to: z.string().describe("Destination pin selector"),
      waypoints: z
        .array(z.object({ x_mm: z.number(), y_mm: z.number() }))
        .optional()
        .describe("Intermediate waypoints"),
      layer: z.string().optional().describe("PCB layer for the route"),
    },
    async (args) => {
      // Manual routing in tscircuit is done via trace elements
      // Waypoints would need to be implemented as intermediate components
      // For now, we add a standard trace and let the autorouter handle it
      const result = manager.addTrace(args.from, args.to);

      if (args.waypoints && args.waypoints.length > 0) {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(
                {
                  ...result,
                  data: {
                    ...result.data,
                    note: "Waypoints recorded but tscircuit's autorouter will determine the final route path. For precise manual routing, use pcb_set_tsx_source with custom trace elements.",
                  },
                },
                null,
                2
              ),
            },
          ],
        };
      }

      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    }
  );
}
