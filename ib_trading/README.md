# Interactive Brokers Trading Module

> **📚 For complete documentation, installation, and usage instructions, see the [main README](../README.md)**

Standalone CLI tool that executes trades through Interactive Brokers based on CSV signals from the main trading script.

## Architecture

```
trading_script.py → CSVs → ib_executor.py → IB API
                              ↓
                    ib_execution_log.csv
```

## Features

- **Complete separation** from original trading script
- **Comprehensive logging** of all IB executions to CSV
- **Safety limits** and validation
- **Paper trading** support
- **Multiple data directory** monitoring  
- **Position reconciliation**
- **Slippage analysis**

## Installation

1. Install dependencies:
```bash
cd ib_trading
pip install -r requirements.txt
```

2. Install TWS or IB Gateway from Interactive Brokers

3. Configure API settings in TWS/Gateway:
   - Enable API connections
   - Set socket port (7497 for paper, 7496 for live)
   - Add trusted IP addresses

## Configuration

Edit `ib_config.yaml`:

```yaml
connection:
  host: "127.0.0.1"
  port: 7497  # TWS paper trading
  client_id: 1

execution:
  mode: "paper"  # or "live"
  max_order_value: 10000
  require_confirmation: true

monitoring:
  data_directories:
    - "../Start Your Own"
    - "../Scripts and CSV Files"
```

## Usage

### Monitor Mode (Recommended)
Continuously watch CSV files and execute new trades:
```bash
python ib_executor.py --monitor --data-dir "../Start Your Own"
```

### Execute Pending Trades
Execute all unprocessed trades:
```bash
python ib_executor.py --execute-pending
```

### Execute Specific Date
Execute trades from a specific date:
```bash
python ib_executor.py --execute-pending --date 2025-01-09
```

### Dry Run
See what would be executed without placing orders:
```bash
python ib_executor.py --dry-run --show-trades
```

### Show Execution History
View recent trade executions:
```bash
python ib_executor.py --show-executions --days 7
```

### Position Reconciliation
Compare IB positions with CSV portfolio:
```bash
python ib_executor.py --reconcile
```

## Output CSV Format

The `ib_execution_log.csv` contains:

| Column | Description |
|--------|-------------|
| execution_date | Date executed on IB |
| execution_time | Time executed |
| ib_order_id | IB order identifier |
| ticker | Stock symbol |
| action | BUY/SELL |
| quantity | Number of shares |
| order_type | MKT/LMT |
| limit_price | For limit orders |
| executed_price | Actual fill price |
| commission | IB commission |
| total_cost | Price × Qty + Commission |
| status | FILLED/CANCELLED/etc |
| csv_source | Source CSV file |
| slippage | Execution vs limit price % |

## Safety Features

1. **Trade Validation**: Price, quantity, and value limits
2. **Daily Limits**: Max trades per day
3. **Confirmation**: Optional user confirmation for trades
4. **Checkpoints**: Never process same trade twice
5. **Paper Trading**: Safe testing environment
6. **Order Timeouts**: Automatic order cancellation

## Trade Detection

The system detects trades from two sources:

### Primary: Trade Log CSV
Explicit buy/sell records from `chatgpt_trade_log.csv`:
- Looks for "MANUAL BUY" and "MANUAL SELL" entries
- Extracts exact order details
- Most reliable method

### Backup: Portfolio Changes
Infers trades from portfolio snapshots in `chatgpt_portfolio_update.csv`:
- Compares consecutive dates
- Detects position changes
- Used when trade log is incomplete

## Error Handling

- **Connection failures**: Auto-reconnect attempts
- **Order rejections**: Logged with reasons
- **Timeouts**: Automatic order cancellation
- **Validation failures**: Trades rejected with warnings
- **Partial fills**: Tracked and logged

## Troubleshooting

### Connection Issues
1. Check TWS/Gateway is running
2. Verify API settings enabled
3. Check port configuration (7497 vs 7496)
4. Verify client_id not in use

### No Trades Detected
1. Check CSV file paths in config
2. Verify CSV format matches expected structure
3. Check checkpoint files for processing state
4. Use `--show-trades` to debug

### Execution Failures
1. Check account buying power
2. Verify market hours
3. Check for duplicate orders
4. Review safety limit violations

## Development

### File Structure
```
ib_trading/
├── ib_executor.py          # Main CLI
├── csv_monitor.py          # CSV trade detection
├── ib_connection.py        # IB API interface
├── execution_logger.py     # Trade logging
├── config_manager.py       # Configuration
├── ib_config.yaml         # Settings
└── requirements.txt       # Dependencies
```

### Adding New Features

1. **New order types**: Extend `ib_connection.py`
2. **Additional brokers**: Create new connection manager
3. **Custom validation**: Modify `config_manager.py`
4. **Enhanced reporting**: Extend `execution_logger.py`

## License

Same as parent project.

## Disclaimer

This software is for educational purposes. Trading involves risk of loss. Always test with paper trading first.