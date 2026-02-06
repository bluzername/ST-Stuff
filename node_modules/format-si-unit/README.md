# format-si-unit

A lightweight utility to format numbers with SI unit prefixes (k, M, G, etc.).

## Installation

```bash
npm install format-si-unit
# or
bun add format-si-unit
```

## Usage

```typescript
import { formatSiUnit } from "format-si-unit"

console.log(formatSiUnit(1500)) // "1.5k"
console.log(formatSiUnit(1_000_000)) // "1M"
console.log(formatSiUnit(0.001)) // "1m"
console.log(formatSiUnit(0)) // "0"
console.log(formatSiUnit()) // ""
```

## Features

- Supports SI prefixes from pico (p) to tera (T)
- Handles null and undefined inputs
- Returns numbers with up to 3 significant digits
- Automatically selects the most appropriate SI prefix
- TypeScript support included

## Development

To install dependencies:

```bash
bun install
```

To run tests:

```bash
bun test
```

To build:

```bash
bun run build
```

## License

MIT
