import type {
  AnyCircuitElement,
  LayerRef,
  PcbBoard,
  PcbHole,
  PcbPlatedHole,
  PcbPort,
  PcbSmtPad,
  PcbTrace,
  PcbVia,
  Point,
  SourceNet,
  SourcePort,
  SourceTrace,
} from "circuit-json"
import { getFullConnectivityMapFromCircuitJson } from "circuit-json-to-connectivity-map"
import type {
  InputCircularPad,
  InputPad,
  InputPolygonPad,
  InputProblem,
  InputRectPad,
  InputTracePad,
} from "lib/types"

export const convertCircuitJsonToInputProblem = (
  circuitJson: AnyCircuitElement[],
  options: {
    layer: LayerRef
    pour_connectivity_key: string
    pad_margin: number
    trace_margin: number
    board_edge_margin?: number
    cutout_margin?: number
    outline?: Point[]
  },
): InputProblem => {
  const pcb_board = circuitJson.find((e) => e.type === "pcb_board") as
    | PcbBoard
    | undefined

  if (!pcb_board) throw new Error("No pcb_board found in circuit json")

  const connectivityMap = getFullConnectivityMapFromCircuitJson(circuitJson)

  const pads: InputPad[] = []

  for (const elm of circuitJson) {
    if (elm.type === "pcb_smtpad") {
      const smtpad = elm as PcbSmtPad
      if (smtpad.layer !== options.layer) continue

      let connectivityKey: string | undefined
      connectivityKey = connectivityMap.getNetConnectedToId(
        smtpad.pcb_smtpad_id,
      )
      if (!connectivityKey) {
        connectivityKey = `unconnected:${smtpad.pcb_smtpad_id}`
      }

      if (smtpad.shape === "rect") {
        pads.push({
          shape: "rect",
          padId: smtpad.pcb_smtpad_id,
          layer: smtpad.layer,
          connectivityKey,
          bounds: {
            minX: smtpad.x - smtpad.width! / 2,
            minY: smtpad.y - smtpad.height! / 2,
            maxX: smtpad.x + smtpad.width! / 2,
            maxY: smtpad.y + smtpad.height! / 2,
          },
        } as InputRectPad)
      } else if (smtpad.shape === "circle") {
        pads.push({
          shape: "circle",
          padId: smtpad.pcb_smtpad_id,
          layer: smtpad.layer,
          connectivityKey,
          x: smtpad.x,
          y: smtpad.y,
          radius: smtpad.radius!,
        } as InputCircularPad)
      }
    } else if (elm.type === "pcb_plated_hole") {
      const platedHole = elm as PcbPlatedHole
      if (platedHole.shape !== "circle") continue
      if (!platedHole.layers.includes(options.layer)) continue

      let connectivityKey = connectivityMap.getNetConnectedToId(
        platedHole.pcb_plated_hole_id,
      )
      if (!connectivityKey) {
        connectivityKey = `unconnected-plated-hole:${platedHole.pcb_plated_hole_id}`
      }

      pads.push({
        shape: "circle",
        padId: platedHole.pcb_plated_hole_id,
        layer: options.layer,
        connectivityKey,
        x: platedHole.x,
        y: platedHole.y,
        radius: platedHole.outer_diameter / 2,
      } as InputCircularPad)
    } else if (elm.type === "pcb_hole") {
      const hole = elm as PcbHole
      if (hole.hole_shape !== "circle") continue

      pads.push({
        shape: "circle",
        padId: hole.pcb_hole_id,
        layer: options.layer, // holes are through-all
        connectivityKey: `hole:${hole.pcb_hole_id}`,
        x: hole.x,
        y: hole.y,
        radius: hole.hole_diameter / 2,
      } as InputCircularPad)
    } else if (elm.type === "pcb_cutout") {
      const cutout = elm as any
      if (cutout.shape === "rect") {
        pads.push({
          shape: "rect",
          padId: cutout.pcb_cutout_id,
          layer: options.layer, // through-all
          connectivityKey: `cutout:${cutout.pcb_cutout_id}`,
          bounds: {
            minX: cutout.center.x - cutout.width / 2,
            minY: cutout.center.y - cutout.height / 2,
            maxX: cutout.center.x + cutout.width / 2,
            maxY: cutout.center.y + cutout.height / 2,
          },
        } as InputRectPad)
      } else if (cutout.shape === "circle") {
        pads.push({
          shape: "circle",
          padId: cutout.pcb_cutout_id,
          layer: options.layer, // through-all
          connectivityKey: `cutout:${cutout.pcb_cutout_id}`,
          x: cutout.center.x,
          y: cutout.center.y,
          radius: cutout.radius,
        } as InputCircularPad)
      } else if (cutout.shape === "polygon") {
        pads.push({
          shape: "polygon",
          padId: cutout.pcb_cutout_id,
          layer: options.layer, // through-all
          connectivityKey: `cutout:${cutout.pcb_cutout_id}`,
          points: cutout.points,
        } as InputPolygonPad)
      }
    } else if (elm.type === "pcb_via") {
      const via = elm as PcbVia
      if (!via.layers.includes(options.layer)) continue

      const connectivityKey: string =
        connectivityMap.getNetConnectedToId(via.pcb_via_id) ??
        `unconnected-via:${via.pcb_via_id}`

      pads.push({
        shape: "circle",
        padId: via.pcb_via_id,
        layer: options.layer,
        connectivityKey,
        x: via.x,
        y: via.y,
        radius: via.outer_diameter / 2,
      } as InputCircularPad)
    } else if (elm.type === "pcb_trace") {
      const trace = elm as PcbTrace
      const connectivityKey = connectivityMap.getNetConnectedToId(
        trace.pcb_trace_id,
      )
      if (!connectivityKey) continue

      let currentSegmentGroup: Point[] = []
      let currentWidth: number | null = null

      const commitGroup = () => {
        if (currentSegmentGroup.length > 1) {
          pads.push({
            shape: "trace",
            padId: `${trace.pcb_trace_id}-${pads.length}`,
            layer: options.layer,
            connectivityKey,
            segments: currentSegmentGroup,
            width: currentWidth!,
          } as InputTracePad)
        }
        currentSegmentGroup = []
        currentWidth = null
      }

      for (const r of trace.route) {
        const ri = r as any
        const isWireOnLayer =
          ri.route_type === "wire" && ri.layer === options.layer
        if (isWireOnLayer) {
          if (currentWidth === null) currentWidth = ri.width
          currentSegmentGroup.push({ x: ri.x, y: ri.y })
        } else {
          commitGroup()
        }
      }
      commitGroup()
    }
  }

  const { width, height } = pcb_board

  // Use pour-specific outline if provided, otherwise fall back to board outline
  const outline = options.outline ?? pcb_board.outline

  let bounds: { minX: number; minY: number; maxX: number; maxY: number }
  if (outline && outline.length > 0) {
    const xs = outline.map((p) => p.x)
    const ys = outline.map((p) => p.y)
    bounds = {
      minX: Math.min(...xs),
      minY: Math.min(...ys),
      maxX: Math.max(...xs),
      maxY: Math.max(...ys),
    }
  } else {
    bounds = {
      minX: -width! / 2,
      minY: -height! / 2,
      maxX: width! / 2,
      maxY: height! / 2,
    }
  }

  const regionsForPour = [
    {
      shape: "rect" as const,
      layer: options.layer,
      bounds,
      outline,
      connectivityKey: options.pour_connectivity_key,
      padMargin: options.pad_margin,
      traceMargin: options.trace_margin,
      board_edge_margin: options.board_edge_margin ?? 0,
      cutout_margin: options.cutout_margin,
    },
  ]

  return {
    pads,
    regionsForPour,
  }
}
