/**
 * Template: Simple LED Blinker with ATtiny85
 * Board: 25mm x 20mm, 2-layer
 *
 * Components:
 * - ATtiny85 (DIP-8)
 * - 1x LED (0805)
 * - 1x 330Ω resistor (0805)
 * - 1x 100nF decoupling cap (0402)
 * - 1x 2-pin power header
 */

export const LED_BLINKER_TSX = `
circuit.add(
  <board width="25mm" height="20mm">
    <chip name="U1" footprint="dip8"
      pinLabels={{ pin1: "RST", pin2: "PB3", pin3: "PB4", pin4: "GND", pin5: "PB0", pin6: "PB1", pin7: "PB2", pin8: "VCC" }}
      schematicSymbolName="box"
      pcbX={0} pcbY={0} />
    <led name="LED1" footprint="0805" pcbX={8} pcbY={0} />
    <resistor name="R1" resistance="330" footprint="0805" pcbX={5} pcbY={3} />
    <capacitor name="C1" capacitance="100nF" footprint="0402" pcbX={-3} pcbY={-3} />
    <chip name="J1" footprint="pinrow2"
      pinLabels={{ pin1: "VCC", pin2: "GND" }}
      schematicSymbolName="box"
      pcbX={-8} pcbY={0} />

    <trace from=".J1 > .VCC" to=".U1 > .VCC" />
    <trace from=".J1 > .GND" to=".U1 > .GND" />
    <trace from=".C1 > .pin1" to=".U1 > .VCC" />
    <trace from=".C1 > .pin2" to=".U1 > .GND" />
    <trace from=".U1 > .PB0" to=".R1 > .pin1" />
    <trace from=".R1 > .pin2" to=".LED1 > .pin1" />
    <trace from=".LED1 > .pin2" to=".U1 > .GND" />
  </board>
)
`;
