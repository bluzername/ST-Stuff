/**
 * Analysis Tools: design comparison and AI-assisted design review.
 */

import { z } from "zod";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { CircuitManager } from "../engine/circuit-manager.js";
import {
  calculateBoardStats,
  runBasicDrc,
  getSourceComponents,
  getSourceTraces,
  getPcbTraces,
  getPcbSmtPads,
} from "../engine/circuit-json-utils.js";
import type { CircuitElement } from "../engine/circuit-json-utils.js";
import * as fs from "node:fs";

export function registerAnalysisTools(server: McpServer, manager: CircuitManager) {
  server.tool(
    "pcb_compare_designs",
    "Compare AI-generated design against a reference design",
    {
      reference_circuit_json_path: z
        .string()
        .describe("Path to reference Circuit JSON file"),
    },
    async (args) => {
      const renderResult = await manager.ensureRendered();
      if (!renderResult.success) {
        return {
          content: [{ type: "text", text: JSON.stringify(renderResult, null, 2) }],
        };
      }

      let refJson: CircuitElement[];
      try {
        const refContent = fs.readFileSync(args.reference_circuit_json_path, "utf-8");
        refJson = JSON.parse(refContent);
      } catch (error: any) {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                success: false,
                errors: [`Could not read reference design: ${error.message}`],
              }),
            },
          ],
        };
      }

      const currentJson = manager.getCircuitJson();
      const currentStats = calculateBoardStats(currentJson);
      const refStats = calculateBoardStats(refJson);
      const rules = manager.getDesignRules();
      const currentDrc = runBasicDrc(currentJson, rules.min_trace_width_mm, rules.min_clearance_mm);
      const refDrc = runBasicDrc(refJson, rules.min_trace_width_mm, rules.min_clearance_mm);

      const comparison = {
        metric: [
          "Component count",
          "Net count",
          "Trace count",
          "Via count",
          "Board area (mm²)",
          "Routing completion %",
          "DRC errors",
          "DRC warnings",
        ],
        current: [
          currentStats.component_count,
          currentStats.net_count,
          currentStats.trace_count,
          currentStats.via_count,
          currentStats.board_area_mm2,
          currentStats.routing_completion_pct,
          currentDrc.filter((v) => v.severity === "error").length,
          currentDrc.filter((v) => v.severity === "warning").length,
        ],
        reference: [
          refStats.component_count,
          refStats.net_count,
          refStats.trace_count,
          refStats.via_count,
          refStats.board_area_mm2,
          refStats.routing_completion_pct,
          refDrc.filter((v) => v.severity === "error").length,
          refDrc.filter((v) => v.severity === "warning").length,
        ],
      };

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                success: true,
                data: {
                  comparison,
                  current_stats: currentStats,
                  reference_stats: refStats,
                  message: "Design comparison complete. See comparison table for details.",
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
    "pcb_design_review",
    "AI-assisted design review - analyze the current circuit for common issues",
    {},
    async () => {
      const renderResult = await manager.ensureRendered();
      if (!renderResult.success) {
        return {
          content: [{ type: "text", text: JSON.stringify(renderResult, null, 2) }],
        };
      }

      const circuitJson = manager.getCircuitJson();
      const components = getSourceComponents(circuitJson);
      const traces = getSourceTraces(circuitJson);
      const pcbTraces = getPcbTraces(circuitJson);
      const pads = getPcbSmtPads(circuitJson);
      const stats = calculateBoardStats(circuitJson);
      const rules = manager.getDesignRules();
      const drc = runBasicDrc(circuitJson, rules.min_trace_width_mm, rules.min_clearance_mm);

      const findings: Array<{
        category: string;
        severity: "info" | "warning" | "error";
        message: string;
        recommendation: string;
      }> = [];

      // Check for decoupling caps near ICs
      const ics = components.filter(
        (c) =>
          c.ftype === "simple_chip" ||
          c.ftype === "chip" ||
          (c.component_type && !["resistor", "capacitor", "inductor", "led", "diode"].includes(c.component_type))
      );
      const caps = components.filter(
        (c) => c.ftype === "simple_capacitor" || c.component_type === "capacitor"
      );

      if (ics.length > 0 && caps.length === 0) {
        findings.push({
          category: "Decoupling",
          severity: "warning",
          message: `Found ${ics.length} IC(s) but no decoupling capacitors`,
          recommendation:
            "Add 100nF decoupling capacitors (0402 or 0805) close to each IC's power pins",
        });
      } else if (ics.length > caps.length) {
        findings.push({
          category: "Decoupling",
          severity: "info",
          message: `${ics.length} IC(s) with only ${caps.length} capacitor(s) - may need more decoupling`,
          recommendation:
            "Rule of thumb: at least one 100nF cap per IC, plus bulk caps near power input",
        });
      }

      // Check routing completion
      if (stats.routing_completion_pct < 100) {
        findings.push({
          category: "Routing",
          severity: "error",
          message: `Routing completion is ${stats.routing_completion_pct}% - some nets are unrouted`,
          recommendation:
            "Check pcb_get_unrouted_nets for details. Try adjusting component placement or adding vias for multi-layer routing.",
        });
      }

      // Check board area efficiency
      if (stats.component_count > 0 && stats.board_area_mm2 > 0) {
        const density = stats.component_count / (stats.board_area_mm2 / 100); // per cm²
        if (density < 0.5) {
          findings.push({
            category: "Board Size",
            severity: "info",
            message: `Low component density (${density.toFixed(1)} components/cm²). Board may be larger than needed.`,
            recommendation:
              "Consider reducing board dimensions for cost savings (smaller boards are cheaper to fabricate)",
          });
        }
      }

      // Check DRC
      const drcErrors = drc.filter((v) => v.severity === "error");
      if (drcErrors.length > 0) {
        findings.push({
          category: "DRC",
          severity: "error",
          message: `${drcErrors.length} DRC error(s) found`,
          recommendation: "Run pcb_run_drc for detailed violation list. Fix errors before ordering.",
        });
      }

      // Check for power traces
      const powerNets = components.filter(
        (c) => c.name?.includes("REG") || c.name?.includes("LDO") || c.ftype?.includes("regulator")
      );
      if (powerNets.length > 0) {
        findings.push({
          category: "Power",
          severity: "info",
          message: "Voltage regulators detected",
          recommendation:
            "Ensure power traces are wider than signal traces (0.3mm+ for low power, 0.5mm+ for >500mA). Add thermal relief for power pads.",
        });
      }

      // General findings
      if (stats.component_count === 0) {
        findings.push({
          category: "General",
          severity: "warning",
          message: "No components in the design",
          recommendation: "Add components using pcb_add_component before review.",
        });
      }

      if (findings.length === 0) {
        findings.push({
          category: "General",
          severity: "info",
          message: "No obvious issues found",
          recommendation:
            "Design looks clean. Always verify Gerber output visually before ordering.",
        });
      }

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                success: true,
                data: {
                  board_stats: stats,
                  finding_count: findings.length,
                  findings,
                  message: `Design review complete: ${findings.filter((f) => f.severity === "error").length} errors, ${findings.filter((f) => f.severity === "warning").length} warnings, ${findings.filter((f) => f.severity === "info").length} info`,
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
