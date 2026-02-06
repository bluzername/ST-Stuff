# circuit-json-flex

Lay out circuit json

```tsx
function convertCircuitJsonToMiniFlex(circuitJson: CircuitJson): MiniFlexInput


function layoutCircuitJsonWithFlex(circuitJson: CircuitJson, flexOptions: {
  justifyContent?: "center" | "...",
  alignItems?: "center" | "...",
  flexDirection?: "row" | "column",
  gap?: number
}): {
  modifiedCircuitJson: CircuitJson,
  operations: Operation[]
}
```
