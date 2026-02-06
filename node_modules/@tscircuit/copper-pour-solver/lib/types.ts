import type { Bounds, Point } from "@tscircuit/math-utils"
import type { BRepShape } from "circuit-json"

export interface InputPourRegion {
  shape: "rect"
  layer: string
  bounds: Bounds
  outline?: Point[]
  connectivityKey: string
  padMargin: number
  traceMargin: number
  board_edge_margin?: number
  cutout_margin?: number
}

export interface BaseInputPad {
  padId: string
  connectivityKey: string
  layer: string
}

export interface InputRectPad extends BaseInputPad {
  shape: "rect"
  bounds: Bounds
}

export interface InputCircularPad extends BaseInputPad {
  shape: "circle"
  x: number
  y: number
  radius: number
}

export interface InputTracePad extends BaseInputPad {
  shape: "trace"
  width: number
  segments: Point[]
}

export interface InputPolygonPad extends BaseInputPad {
  shape: "polygon"
  points: Point[]
}

export type InputPad =
  | InputRectPad
  | InputCircularPad
  | InputTracePad
  | InputPolygonPad

export interface InputProblem {
  regionsForPour: InputPourRegion[]
  pads: InputPad[]
}
export interface PipelineOutput {
  brep_shapes: BRepShape[]
}
