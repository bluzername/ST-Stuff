/**
 * Template: ESP32 Development Board
 * Board: 50mm x 35mm, 2-layer
 *
 * Components:
 * - ESP32-WROOM-32 module
 * - AMS1117-3.3 voltage regulator
 * - USB power input header
 * - Reset/Boot buttons
 * - Status LED
 * - Breakout header
 */

export const ESP32_DEVBOARD_TSX = `
circuit.add(
  <board width="50mm" height="35mm">
    <chip name="U1" footprint="qfp32"
      pinLabels={{
        pin1: "GND", pin2: "3V3", pin3: "EN", pin4: "IO36",
        pin5: "IO39", pin6: "IO34", pin7: "IO35", pin8: "IO32",
        pin9: "IO33", pin10: "IO25", pin11: "IO26", pin12: "IO27",
        pin13: "IO14", pin14: "IO12", pin15: "IO13", pin16: "IO15",
        pin17: "IO2", pin18: "IO0", pin19: "IO4", pin20: "IO16",
        pin21: "IO17", pin22: "IO5", pin23: "IO18", pin24: "IO19",
        pin25: "IO21", pin26: "RXD0", pin27: "TXD0", pin28: "IO22",
        pin29: "IO23"
      }}
      schematicSymbolName="box"
      pcbX={0} pcbY={0} />

    <chip name="U2" footprint="sot223"
      pinLabels={{ pin1: "GND", pin2: "VOUT", pin3: "VIN" }}
      schematicSymbolName="box"
      pcbX={-18} pcbY={0} />

    <chip name="J1" footprint="pinrow2"
      pinLabels={{ pin1: "5V", pin2: "GND" }}
      schematicSymbolName="box"
      pcbX={-22} pcbY={0} />

    <capacitor name="C1" capacitance="10uF" footprint="0805" pcbX={-15} pcbY={-5} />
    <capacitor name="C2" capacitance="10uF" footprint="0805" pcbX={-12} pcbY={-5} />
    <capacitor name="C3" capacitance="100nF" footprint="0402" pcbX={-5} pcbY={-8} />

    <resistor name="R1" resistance="10k" footprint="0402" pcbX={5} pcbY={10} />
    <resistor name="R2" resistance="10k" footprint="0402" pcbX={8} pcbY={10} />

    <led name="LED1" footprint="0805" pcbX={15} pcbY={10} />
    <resistor name="R3" resistance="330" footprint="0402" pcbX={12} pcbY={10} />

    <trace from=".J1 > .5V" to=".U2 > .VIN" />
    <trace from=".U2 > .VOUT" to=".U1 > .3V3" />
    <trace from=".U2 > .VIN" to=".C1 > .pin1" />
    <trace from=".C1 > .pin2" to=".U2 > .GND" />
    <trace from=".U2 > .VOUT" to=".C2 > .pin1" />
    <trace from=".C2 > .pin2" to=".U2 > .GND" />
    <trace from=".U1 > .3V3" to=".C3 > .pin1" />
    <trace from=".C3 > .pin2" to=".U1 > .GND" />
    <trace from=".R1 > .pin1" to=".U1 > .3V3" />
    <trace from=".R1 > .pin2" to=".U1 > .EN" />
    <trace from=".R2 > .pin1" to=".U1 > .3V3" />
    <trace from=".R2 > .pin2" to=".U1 > .IO0" />
    <trace from=".U1 > .IO2" to=".R3 > .pin1" />
    <trace from=".R3 > .pin2" to=".LED1 > .pin1" />
    <trace from=".LED1 > .pin2" to=".U1 > .GND" />
    <trace from=".U1 > .GND" to=".U2 > .GND" />
    <trace from=".J1 > .GND" to=".U2 > .GND" />
  </board>
)
`;
