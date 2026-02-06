# AI PCB Designer — MCP Server for Circuit Board Design

An MCP server that enables Claude to design, validate, and export real PCBs end-to-end. Uses [tscircuit](https://tscircuit.com) as the design engine: natural language requirements → component selection → schematic → PCB layout → autorouted board → Gerber export.

The output is orderable from JLCPCB.

```
Claude ←MCP/stdio→ pcb-mcp-server ←→ @tscircuit/eval ←→ Circuit JSON
                                                              ↓
                                     ┌────────────────────────┼───────────────┐
                                     ↓                        ↓               ↓
                                Gerber/Drill              SVG/PNG         BOM/CSV
                                (orderable!)            (preview)       (procurement)
```

## Quick Start

### 1. Install

```bash
git clone <this-repo> pcb-mcp-server
cd pcb-mcp-server
npm install --legacy-peer-deps
```

Requires Node.js 20+.

### 2. Verify Installation

```bash
npm run quick-test
```

You should see all tests pass with "OK" status.

### 3. Configure Claude Code

Add to your Claude Code MCP settings (`.claude/settings.json` or project config):

```json
{
  "mcpServers": {
    "pcb-designer": {
      "command": "npx",
      "args": ["tsx", "src/index.ts"],
      "cwd": "/absolute/path/to/pcb-mcp-server"
    }
  }
}
```

### 4. Design Your First Board

Start a Claude Code session and say:

> "Design a simple LED blinker circuit with a 555 timer on a 30x25mm board"

Claude will use tools like `pcb_create_project`, `pcb_add_component`, `pcb_add_trace`, `pcb_autoroute`, and `pcb_export_gerbers` to design the board step by step.

---

## Tool Reference

### Design Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `pcb_create_project` | Create a new circuit project | `name`, `board_width_mm`, `board_height_mm`, `layer_count` |
| `pcb_add_component` | Add an electronic component | `component_type`, `name`, `properties`, `footprint`, `pcb_x_mm`, `pcb_y_mm` |
| `pcb_add_trace` | Connect two pins | `from`, `to` (selector syntax: `".R1 > .pin1"`) |
| `pcb_add_net` | Create a named net | `net_name`, `connections[]` |
| `pcb_add_group` | Group components | `name`, `components[]` |
| `pcb_modify_component` | Update component properties | `name`, `updates` |
| `pcb_remove_component` | Remove component + traces | `name` |
| `pcb_get_circuit_state` | Get full circuit state | — |
| `pcb_get_tsx_source` | Get generated TSX code | — |
| `pcb_set_tsx_source` | Set TSX directly | `tsx_code` |

### Component Tools

| Tool | Description |
|------|-------------|
| `pcb_search_components` | Search tscircuit registry |
| `pcb_get_component_details` | Get package details |
| `pcb_search_footprints` | Search available footprints |
| `pcb_suggest_component` | Get component suggestions for a requirement |

### Layout Tools

| Tool | Description |
|------|-------------|
| `pcb_set_board_outline` | Set board dimensions/shape |
| `pcb_auto_place` | Auto-place components (grid/clustered) |
| `pcb_add_mounting_hole` | Add mounting hole |
| `pcb_set_design_rules` | Set DRC rules or fab presets |
| `pcb_add_ground_plane` | Record ground plane intent |

### Routing Tools

| Tool | Description |
|------|-------------|
| `pcb_autoroute` | Run autorouter on all nets |
| `pcb_get_unrouted_nets` | List unrouted nets |
| `pcb_route_net` | Manually route a net |

### Verification Tools

| Tool | Description |
|------|-------------|
| `pcb_run_drc` | Design Rule Check |
| `pcb_run_erc` | Electrical Rules Check |
| `pcb_check_manufacturability` | Check against fab specs (JLCPCB/PCBWay/OSHPark) |
| `pcb_get_board_stats` | Board statistics |

### Export Tools

| Tool | Description |
|------|-------------|
| `pcb_export_gerbers` | Gerber + drill files for manufacturing |
| `pcb_export_bom` | Bill of Materials (CSV/JSON) |
| `pcb_export_svg` | SVG preview |
| `pcb_export_circuit_json` | Raw Circuit JSON |
| `pcb_export_pick_and_place` | Pick-and-place CSV |
| `pcb_export_spice_netlist` | SPICE netlist |
| `pcb_export_3d_model` | 3D model (not yet implemented) |

### Analysis Tools

| Tool | Description |
|------|-------------|
| `pcb_compare_designs` | Compare against reference design |
| `pcb_design_review` | Automated design review |

---

## Design Workflow

A typical PCB design session follows this flow:

```
1. pcb_create_project    → Set board size, layers, name
2. pcb_add_component     → Add all components (repeat)
3. pcb_add_trace         → Connect pins (repeat)
4. pcb_auto_place        → Optimize component placement
5. pcb_autoroute         → Route all traces
6. pcb_run_drc           → Check for violations
7. pcb_run_erc           → Check electrical rules
8. pcb_export_gerbers    → Generate manufacturing files
9. pcb_export_bom        → Generate bill of materials
```

### Example Conversation Flow

**User:** Design a USB-C power board with a 3.3V regulator, status LED, and 6-pin output header.

**Claude uses:**
1. `pcb_create_project` — 40x25mm, 2-layer board
2. `pcb_add_component` — USB-C connector, AMS1117-3.3, caps, resistors, LED, header
3. `pcb_add_trace` — VBUS→regulator, CC resistors to GND, LED circuit, power output
4. `pcb_set_design_rules` — JLCPCB 2-layer preset
5. `pcb_autoroute` — Route all traces
6. `pcb_run_drc` — Check violations
7. `pcb_export_gerbers` — Generate manufacturing files
8. `pcb_export_bom` — Component list for ordering

---

## Examples

Three complete examples in `examples/`:

- **`555-timer-blinker.ts`** — Classic 555 astable circuit with LED (9 components)
- **`usb-c-power-board.ts`** — USB-C power input with 3.3V LDO (10 components)
- **`esp32-sensor-board.ts`** — ESP32 with BME280 I2C sensor (13 components)

Run any example:

```bash
npx tsx examples/555-timer-blinker.ts
```

---

## Benchmark Results

All three test cases from the benchmark suite:

| Metric | LED Blinker | USB-C Power | ESP32 Sensor |
|--------|------------|-------------|--------------|
| Components | 5 | 14 | 22 |
| Traces | 7 | 17 | 34 |
| Tool Calls | 14 | 33 | 59 |
| Render | OK | OK | OK |
| DRC Errors | 16 | 30 | 1 |
| DRC Warnings | 0 | 9 | 8 |
| Routing | 100% | 100% | 0% |
| Board Area | 500 mm² | 1000 mm² | 1750 mm² |
| Gerber Export | OK | OK | OK |
| Gerber Files | 11 | 11 | 11 |
| BOM Entries | 5 | 14 | 21 |
| SVG Export | OK | OK | OK |
| Time | ~1.7s | ~28s | ~6s |

### Analysis

**LED Blinker (Simple):** Renders and routes successfully. 16 DRC errors are primarily trace overlap warnings from the autorouter placing traces too close to adjacent pads on the compact 25x20mm board. Gerbers are valid and exportable.

**USB-C Power (Medium):** Renders and routes all traces. 30 DRC errors are mostly trace-pad overlap issues from dense routing. The 28-second render time is dominated by the autorouter working through 17 nets with many GND connections. All exports work.

**ESP32 Sensor (Complex):** Renders but the autorouter fails to route any traces (0% routing). The 29-pin ESP32 + 13-pin CP2102N + BME280 with 34 nets exceeds the capacity-mesh autorouter's capability on a 2-layer board. The circuit JSON is generated correctly (788 elements), all components are placed, and Gerber/BOM/SVG exports succeed — but the board has no routed copper traces. This design would require either a 4-layer board, manual routing assistance, or the Freerouting external autorouter.

**Key finding:** The tscircuit autorouter handles simple-to-medium designs (5-15 components) well but struggles with dense, complex designs (20+ components with many nets). This is consistent with expectations for an open-source mesh autorouter. For production complex boards, export the DSN file and use Freerouting or manually route critical nets.

---

## Limitations — Honest Assessment

### Spatial Reasoning
LLMs have no visual intuition for PCB layout. Component placement is geometric (grid or connectivity-based) but not aesthetically optimized. Human review of placement is recommended for any board going to production.

### Analog/RF Design
No impedance matching, no controlled impedance routing, no SPICE-aware trace management. Not suitable for RF, high-speed differential pairs, or precision analog circuits without human oversight.

### Complex Routing
Fully dependent on tscircuit's built-in autorouter quality. The capacity-mesh autorouter works for simple boards but fails on dense designs with many nets. Boards with >15 nets or requiring 4+ layers will likely need manual intervention or Freerouting.

### Component Availability
Component search is limited to the tscircuit registry. Real-world BOM optimization (Digi-Key/Mouser/LCSC cross-referencing) is not implemented. The registry has limited coverage compared to commercial databases.

### Thermal Analysis
No thermal simulation. Power component placement and thermal relief should be reviewed by an engineer for any board dissipating significant power.

### Footprint Accuracy
Common footprints (0402, 0805, SOIC, DIP, SOT-223, etc.) are well-supported. Custom or complex footprints (BGA, fine-pitch QFN, odd connectors) may need manual verification against datasheets.

### DRC Completeness
DRC checks trace width minimums, detects routing errors, and flags unconnected pins. It does not check: clearance between traces, courtyard overlaps, thermal relief, acid traps, or copper balance. Critical designs need secondary verification in KiCad or a commercial tool.

### Supplier Fetch Errors
In offline environments, tscircuit generates harmless "unknown_error_finding_part" warnings when it can't reach its parts registry. These don't affect circuit rendering or export.

---

## Technical Architecture

### Circuit JSON

Circuit JSON is the universal intermediate format — a JSON array of typed elements:

- **`source_`** elements: Original circuit definition (component values, net connections)
- **`schematic_`** elements: Schematic visualization data
- **`pcb_`** elements: Physical PCB data (pads, traces, vias, board outline)

From Circuit JSON, you can generate Gerbers, SVGs, BOMs, SPICE netlists, and 3D models.

### Render Pipeline

```
Structured State → TSX Generator → CircuitRunner.execute() →
  renderUntilSettled() → Circuit JSON → Export Pipeline
```

1. **CircuitManager** maintains components, traces, nets as structured data
2. **TSX Generator** serializes state to tscircuit TSX code
3. **CircuitRunner** (from `@tscircuit/eval`) evaluates TSX in an isolated runtime
4. **renderUntilSettled()** runs the autorouter and produces Circuit JSON
5. **Export Pipeline** converts Circuit JSON to Gerber, BOM, SVG, etc.

### State Management

The MCP server is stateful — it maintains a single circuit session across tool calls. Each mutation (add component, add trace, etc.) marks the state as dirty. The next query or export triggers a re-render.

This design matches how PCB design actually works: iterative, incremental changes with periodic validation.

### Why @tscircuit/eval Instead of @tscircuit/core Directly

`@tscircuit/core` requires JSX compilation (React runtime). In a Node.js MCP server without a bundler, this is cumbersome. `@tscircuit/eval`'s `CircuitRunner` accepts raw TSX strings and handles the React runtime internally, making it the ideal choice for a server environment.

---

## Project Structure

```
pcb-mcp-server/
├── src/
│   ├── index.ts                    # MCP server entry point (stdio)
│   ├── tools/
│   │   ├── design.ts               # Create, modify, query circuits
│   │   ├── components.ts           # Component search & suggestions
│   │   ├── layout.ts               # Board config, placement, design rules
│   │   ├── routing.ts              # Autorouting & trace management
│   │   ├── verification.ts         # DRC, ERC, manufacturability
│   │   ├── export.ts               # Gerber, BOM, SVG, SPICE export
│   │   └── analysis.ts             # Design comparison & review
│   ├── engine/
│   │   ├── circuit-manager.ts      # Stateful circuit session manager
│   │   ├── tsx-generator.ts        # State → TSX serialization
│   │   ├── circuit-json-utils.ts   # Circuit JSON query helpers
│   │   └── export-pipeline.ts      # Format conversion
│   └── types/
│       └── index.ts                # Shared types
├── tests/
│   ├── tools/design.test.ts        # 16 unit tests
│   ├── integration/end-to-end.test.ts  # 2 integration tests
│   └── benchmarks/
│       └── benchmark-runner.ts     # 3 test case benchmarks
├── examples/
│   ├── 555-timer-blinker.ts
│   ├── esp32-sensor-board.ts
│   └── usb-c-power-board.ts
├── claude-code-config.json         # Ready-to-use MCP config
├── vitest.config.ts
├── tsconfig.json
└── package.json
```

---

## Running Tests

```bash
# Unit + integration tests (18 tests)
npm test

# Benchmark suite (3 test cases)
npm run benchmark

# Quick smoke test
npm run quick-test
```

---

## Troubleshooting

**"No project initialized"** — Call `pcb_create_project` before adding components.

**Supplier fetch errors** — Harmless in offline environments. tscircuit tries to look up part numbers online. Does not affect rendering or export.

**Autorouter fails on complex boards** — Expected for dense designs. Try:
- Increasing board dimensions
- Reducing component count
- Using `pcb_auto_place` with "clustered" strategy before routing
- Exporting DSN and using Freerouting externally

**Gerber export path** — Default output is `/tmp/pcb-exports/`. Specify a custom path with the `output_path` parameter.

---

## Roadmap

- KiCad export (Circuit JSON → .kicad_pcb)
- Digi-Key/LCSC component sourcing integration
- Impedance-aware routing for high-speed designs
- Multi-board / panel design support
- SPICE simulation integration
- Interactive browser-based visual preview
- Freerouting JAR integration for complex autorouting
- 3D model export (GLTF/GLB)

---

## License

MIT
