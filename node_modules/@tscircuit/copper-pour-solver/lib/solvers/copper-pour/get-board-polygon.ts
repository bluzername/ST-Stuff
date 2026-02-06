import type { InputPourRegion } from "lib/types"
import Flatten from "@flatten-js/core"

export const getBoardPolygon = (region: InputPourRegion): Flatten.Polygon => {
  const board_edge_margin = region.board_edge_margin ?? 0

  if (region.outline && region.outline.length > 0) {
    const polygon = new Flatten.Polygon(
      region.outline.map((p) => Flatten.point(p.x, p.y)),
    )
    // Ensure polygon is CCW for consistent boolean operations
    if (polygon.orientation() === Flatten.ORIENTATION.CW) {
      polygon.reverse()
    }
    return polygon
  }

  const { bounds } = region
  const newBounds = {
    minX: bounds.minX + board_edge_margin,
    minY: bounds.minY + board_edge_margin,
    maxX: bounds.maxX - board_edge_margin,
    maxY: bounds.maxY - board_edge_margin,
  }

  if (newBounds.minX >= newBounds.maxX || newBounds.minY >= newBounds.maxY) {
    return new Flatten.Polygon()
  }

  return new Flatten.Polygon(
    new Flatten.Box(
      newBounds.minX,
      newBounds.minY,
      newBounds.maxX,
      newBounds.maxY,
    ).toPoints(),
  )
}
