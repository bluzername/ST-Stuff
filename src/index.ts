#!/usr/bin/env node

/**
 * PCB Designer MCP Server
 *
 * A production-grade MCP server for AI-assisted PCB design using tscircuit.
 * Enables Claude to design, validate, and export real PCBs end-to-end.
 *
 * Architecture:
 *   Claude <--MCP/stdio--> This Server <--> @tscircuit/eval <--> Circuit JSON
 *                                                                      |
 *                                   +----------------------------------+--------+
 *                                   v                v                  v        v
 *                              Gerber/Drill      SVG/PNG            BOM/CSV   SPICE
 *
 * Uses @tscircuit/eval's CircuitRunner for TSX evaluation (no bundler needed).
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CircuitManager } from "./engine/circuit-manager.js";
import { registerDesignTools } from "./tools/design.js";
import { registerComponentTools } from "./tools/components.js";
import { registerLayoutTools } from "./tools/layout.js";
import { registerRoutingTools } from "./tools/routing.js";
import { registerVerificationTools } from "./tools/verification.js";
import { registerExportTools } from "./tools/export.js";
import { registerAnalysisTools } from "./tools/analysis.js";

async function main() {
  const server = new McpServer({
    name: "pcb-designer",
    version: "1.0.0",
  });

  // Single stateful circuit manager shared across all tools
  const manager = new CircuitManager();

  // Register all tool categories
  registerDesignTools(server, manager);
  registerComponentTools(server);
  registerLayoutTools(server, manager);
  registerRoutingTools(server, manager);
  registerVerificationTools(server, manager);
  registerExportTools(server, manager);
  registerAnalysisTools(server, manager);

  // Connect via stdio transport
  const transport = new StdioServerTransport();
  await server.connect(transport);

  // Log to stderr (stdout is reserved for MCP protocol)
  console.error("PCB Designer MCP Server started (stdio transport)");
  console.error(`Tools registered: design, components, layout, routing, verification, export, analysis`);
}

main().catch((error) => {
  console.error("Fatal error starting MCP server:", error);
  process.exit(1);
});
