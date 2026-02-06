# @tscircuit/copper-pour-solver

Solves for copper pour polygons

```tsx
import { CopperPourPipelineSolver } from "@tscircuit/copper-pour-solver"

const solver = new CopperPourPipelineSolver({
  // Circuit JSON including pcb_plated_hole, pcb_hole, pcb_smtpad, pcb_trace, pcb_keepout etc.
  circuitJson
})

solver.solve()

solver.getOutput()
// { brepShapes }
```

## B-Rep Shapes

We use the following representation for 2D b-rep shapes

```tsx
interface BRepShape {
  outerRing: Ring // The outer boundary
  innerRings: Ring // The inner cutouts
}

interface Ring {
  cwVertices: PointWithBulge[]
}

interface PointWithBulge {
  x: number
  y: number
}
```
