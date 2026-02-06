/**
 * Component Search Tools: search tscircuit registry, suggest components.
 */

import { z } from "zod";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";

const REGISTRY_API = "https://registry-api.tscircuit.com";

interface RegistryPackage {
  name: string;
  description: string;
  owner_name: string;
  latest_version: string;
  star_count: number;
}

async function searchRegistry(
  query: string,
  limit: number = 10
): Promise<{ packages: RegistryPackage[]; error?: string }> {
  try {
    const response = await fetch(`${REGISTRY_API}/packages/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, limit }),
      signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) {
      return { packages: [], error: `Registry API returned ${response.status}` };
    }
    const data = (await response.json()) as any;
    return { packages: data.packages || [] };
  } catch (error: any) {
    return { packages: [], error: `Registry search failed: ${error.message}` };
  }
}

async function getPackageDetails(
  packageName: string
): Promise<{ details: any; error?: string }> {
  try {
    const response = await fetch(
      `${REGISTRY_API}/packages/get?name=${encodeURIComponent(packageName)}`,
      { signal: AbortSignal.timeout(10000) }
    );
    if (!response.ok) {
      return { details: null, error: `Package not found: ${response.status}` };
    }
    const data = await response.json();
    return { details: data };
  } catch (error: any) {
    return { details: null, error: `Failed to get package: ${error.message}` };
  }
}

const COMMON_FOOTPRINTS: Record<string, string[]> = {
  "0201": ["0201 (0.6mm x 0.3mm) - Ultra-small passive"],
  "0402": ["0402 (1.0mm x 0.5mm) - Small passive, good for dense boards"],
  "0603": ["0603 (1.6mm x 0.8mm) - Common passive, easy hand-solder"],
  "0805": ["0805 (2.0mm x 1.25mm) - Standard passive, very easy to solder"],
  "1206": ["1206 (3.2mm x 1.6mm) - Large passive, power applications"],
  "1210": ["1210 (3.2mm x 2.5mm) - Larger passive for power"],
  sot23: ["SOT-23 (3-pin small transistor/regulator)"],
  "sot23-5": ["SOT-23-5 (5-pin small IC)"],
  "sot23-6": ["SOT-23-6 (6-pin small IC)"],
  sot223: ["SOT-223 (voltage regulator, power)"],
  soic8: ["SOIC-8 (8-pin standard IC)"],
  soic14: ["SOIC-14 (14-pin IC)"],
  soic16: ["SOIC-16 (16-pin IC)"],
  ssop20: ["SSOP-20 (20-pin narrow IC)"],
  tssop20: ["TSSOP-20 (20-pin thin IC)"],
  qfp32: ["QFP-32 (32-pin quad flat pack)"],
  qfp44: ["QFP-44 (44-pin quad flat pack)"],
  qfp64: ["QFP-64 (64-pin quad flat pack)"],
  qfn16: ["QFN-16 (16-pin quad flat no-lead)"],
  qfn32: ["QFN-32 (32-pin quad flat no-lead)"],
  dip8: ["DIP-8 (8-pin through-hole)"],
  dip14: ["DIP-14 (14-pin through-hole)"],
  dip16: ["DIP-16 (16-pin through-hole)"],
  dip28: ["DIP-28 (28-pin through-hole)"],
  pinrow2: ["2-pin header (2.54mm pitch)"],
  pinrow3: ["3-pin header (2.54mm pitch)"],
  pinrow4: ["4-pin header (2.54mm pitch)"],
  pinrow6: ["6-pin header (2.54mm pitch)"],
  pinrow8: ["8-pin header (2.54mm pitch)"],
  pinrow10: ["10-pin header (2.54mm pitch)"],
  pinrow20: ["20-pin header (2.54mm pitch)"],
  pinrow40: ["40-pin header (2.54mm pitch)"],
};

const COMPONENT_SUGGESTIONS: Record<
  string,
  Array<{
    type: string;
    name: string;
    value?: string;
    footprint: string;
    reason: string;
  }>
> = {
  "voltage regulator": [
    { type: "chip", name: "AMS1117-3.3", footprint: "sot223", reason: "Common 3.3V LDO, 1A output, widely available" },
    { type: "chip", name: "LM7805", footprint: "sot223", reason: "Classic 5V regulator, robust" },
    { type: "chip", name: "AP2112K-3.3", footprint: "sot23-5", reason: "Low dropout, 600mA, small footprint" },
  ],
  "decoupling": [
    { type: "capacitor", name: "100nF", value: "100nF", footprint: "0402", reason: "Standard decoupling cap, place close to IC power pins" },
    { type: "capacitor", name: "10uF", value: "10uF", footprint: "0805", reason: "Bulk decoupling for voltage regulators" },
  ],
  "led indicator": [
    { type: "led", name: "LED", footprint: "0805", reason: "Standard indicator LED" },
    { type: "resistor", name: "R_LED", value: "330", footprint: "0402", reason: "Current limiting resistor for 3.3V supply (~10mA)" },
  ],
  "usb-c": [
    { type: "chip", name: "USB-C", footprint: "soic16", reason: "USB Type-C 16-pin connector" },
    { type: "resistor", name: "R_CC1", value: "5.1k", footprint: "0402", reason: "CC1 pull-down for USB-C power" },
    { type: "resistor", name: "R_CC2", value: "5.1k", footprint: "0402", reason: "CC2 pull-down for USB-C power" },
  ],
  "crystal oscillator": [
    { type: "crystal", name: "Y1", value: "16MHz", footprint: "0805", reason: "Standard crystal for MCUs" },
    { type: "capacitor", name: "C_Y1", value: "22pF", footprint: "0402", reason: "Load capacitor for crystal" },
    { type: "capacitor", name: "C_Y2", value: "22pF", footprint: "0402", reason: "Load capacitor for crystal" },
  ],
  "pull-up resistor": [
    { type: "resistor", name: "R_PU", value: "4.7k", footprint: "0402", reason: "Standard I2C pull-up value" },
  ],
  "esd protection": [
    { type: "diode", name: "D_TVS", footprint: "sot23", reason: "TVS diode for ESD protection" },
  ],
};

export function registerComponentTools(server: McpServer) {
  server.tool(
    "pcb_search_components",
    "Search the tscircuit registry for reusable circuit modules",
    {
      query: z.string().describe("Search query (e.g., 'led driver', 'esp32')"),
      category: z.string().optional().describe("Category filter"),
      max_results: z.number().default(10).describe("Maximum results to return"),
    },
    async (args) => {
      const result = await searchRegistry(args.query, args.max_results);
      if (result.error) {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                success: false,
                errors: [result.error],
                packages: [],
              }),
            },
          ],
        };
      }
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                success: true,
                data: {
                  query: args.query,
                  count: result.packages.length,
                  packages: result.packages.map((p: RegistryPackage) => ({
                    name: `@tsci/${p.owner_name}.${p.name}`,
                    description: p.description,
                    version: p.latest_version,
                    stars: p.star_count,
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
    "pcb_get_component_details",
    "Get full details of a tscircuit registry package",
    {
      package_name: z.string().describe('Package name (e.g., "seveibar/red-led")'),
    },
    async (args) => {
      const result = await getPackageDetails(args.package_name);
      if (result.error) {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({ success: false, errors: [result.error] }),
            },
          ],
        };
      }
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({ success: true, data: result.details }, null, 2),
          },
        ],
      };
    }
  );

  server.tool(
    "pcb_search_footprints",
    "Search available footprints by keyword or package size",
    {
      query: z.string().describe('Search query (e.g., "0805", "soic", "dip")'),
    },
    async (args) => {
      const q = args.query.toLowerCase();
      const matches: Array<{ footprint: string; description: string }> = [];
      for (const [fp, descs] of Object.entries(COMMON_FOOTPRINTS)) {
        if (fp.includes(q) || descs.some((d) => d.toLowerCase().includes(q))) {
          matches.push({ footprint: fp, description: descs[0] });
        }
      }
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                success: true,
                data: {
                  query: args.query,
                  count: matches.length,
                  footprints: matches,
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
    "pcb_suggest_component",
    "Given a functional requirement, suggest appropriate components",
    {
      description: z.string().describe('Functional description (e.g., "voltage regulator", "LED indicator")'),
      constraints: z
        .object({
          package_size: z.string().optional(),
          voltage_rating: z.string().optional(),
          value_range: z.string().optional(),
        })
        .optional()
        .describe("Optional constraints"),
    },
    async (args) => {
      const q = args.description.toLowerCase();
      let suggestions: typeof COMPONENT_SUGGESTIONS[string] = [];

      // Search through suggestion database
      for (const [key, sugs] of Object.entries(COMPONENT_SUGGESTIONS)) {
        if (q.includes(key) || key.includes(q)) {
          suggestions = [...suggestions, ...sugs];
        }
      }

      // Filter by constraints
      if (args.constraints?.package_size) {
        const size = args.constraints.package_size.toLowerCase();
        suggestions = suggestions.filter(
          (s) => s.footprint.toLowerCase().includes(size)
        );
      }

      if (suggestions.length === 0) {
        suggestions = [
          {
            type: "chip",
            name: "suggested_component",
            footprint: "soic8",
            reason: `No specific suggestion for "${args.description}". Consider searching the tscircuit registry with pcb_search_components.`,
          },
        ];
      }

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(
              {
                success: true,
                data: {
                  description: args.description,
                  suggestions,
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
