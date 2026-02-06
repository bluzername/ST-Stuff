import { BasePipelineSolver } from "@tscircuit/solver-utils"
import { getBoardPolygon } from "./copper-pour/get-board-polygon"
import Flatten from "@flatten-js/core"
import { processObstaclesForPour } from "./copper-pour/process-obstacles"
import { generateBRep } from "./copper-pour/generate-brep"
import type { BRepShape } from "circuit-json"
import type { InputProblem, PipelineOutput } from "lib/types"

export class CopperPourPipelineSolver extends BasePipelineSolver<InputProblem> {
  pipelineDef = []
  constructor(public input: InputProblem) {
    super(input)
  }

  override getSolverName(): string {
    return "CopperPourPipelineSolver"
  }

  override getOutput(): PipelineOutput {
    const brep_shapes: BRepShape[] = []

    for (const region of this.input.regionsForPour) {
      const boardPolygon = getBoardPolygon(region)

      const padsForLayer = this.input.pads.filter(
        (p) => p.layer === region.layer,
      )

      const { polygonsToSubtract } = processObstaclesForPour(
        padsForLayer,
        region.connectivityKey,
        {
          padMargin: region.padMargin,
          traceMargin: region.traceMargin,
          board_edge_margin: region.board_edge_margin,
          cutoutMargin: region.cutout_margin,
        },
        region.outline,
      )

      let pourPolygons: Flatten.Polygon | Flatten.Polygon[] = boardPolygon

      for (const poly of polygonsToSubtract) {
        const currentPolys = Array.isArray(pourPolygons)
          ? pourPolygons
          : [pourPolygons]
        const nextPolys: Flatten.Polygon[] = []
        for (const p of currentPolys) {
          const result = Flatten.BooleanOperations.subtract(p, poly)
          if (result) {
            if (Array.isArray(result)) {
              nextPolys.push(...result.filter((r) => !r.isEmpty()))
            } else {
              if (!result.isEmpty()) nextPolys.push(result)
            }
          }
        }
        pourPolygons = nextPolys
      }

      const new_breps = generateBRep(pourPolygons)
      brep_shapes.push(...new_breps)
    }

    return {
      brep_shapes,
    }
  }
}
