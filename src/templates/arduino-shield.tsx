/**
 * Template: Arduino Shield Base
 * Board: 68.6mm x 53.3mm, 2-layer (standard Arduino Uno shield dimensions)
 *
 * Provides the base board with header connectors matching Arduino Uno pinout.
 * Users add their own circuit components on top.
 */

export const ARDUINO_SHIELD_TSX = `
circuit.add(
  <board width="68.6mm" height="53.3mm">
    <chip name="J1" footprint="pinrow10"
      pinLabels={{
        pin1: "D8", pin2: "D9", pin3: "D10", pin4: "D11",
        pin5: "D12", pin6: "D13", pin7: "GND", pin8: "AREF",
        pin9: "SDA", pin10: "SCL"
      }}
      schematicSymbolName="box"
      pcbX={20} pcbY={22} />

    <chip name="J2" footprint="pinrow8"
      pinLabels={{
        pin1: "D0", pin2: "D1", pin3: "D2", pin4: "D3",
        pin5: "D4", pin6: "D5", pin7: "D6", pin8: "D7"
      }}
      schematicSymbolName="box"
      pcbX={-15} pcbY={22} />

    <chip name="J3" footprint="pinrow6"
      pinLabels={{
        pin1: "A0", pin2: "A1", pin3: "A2", pin4: "A3",
        pin5: "A4", pin6: "A5"
      }}
      schematicSymbolName="box"
      pcbX={-15} pcbY={-22} />

    <chip name="J4" footprint="pinrow8"
      pinLabels={{
        pin1: "VIN", pin2: "GND1", pin3: "GND2", pin4: "5V",
        pin5: "3V3", pin6: "RST", pin7: "IOREF", pin8: "NC"
      }}
      schematicSymbolName="box"
      pcbX={20} pcbY={-22} />
  </board>
)
`;
