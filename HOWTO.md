# ChatGPT Micro-Cap Trading Pipeline - Execution Instructions

## Daily Trading Pipeline Execution Schedule

### **When to Run: After Market Close (4 PM ET)**
The pipeline should be executed **after each trading day closes** because:

1. **Market Data Requirements**: The `trading_script.py` pulls end-of-day prices (Close, High, Low, Volume)
2. **Weekend Handling**: The script automatically maps weekend dates to Friday's data
3. **Stop-Loss Calculations**: Uses the day's low price to check if stops were triggered

### **Daily Workflow Timeline**

#### **4:15 PM ET - 5:00 PM ET (Post-Market)**
1. **Generate Trade Signals**:
   ```bash
   python trading_script.py --file "Scripts and CSV Files/chatgpt_portfolio_update.csv"
   ```
   - Updates portfolio with current prices
   - Checks stop-losses
   - Generates daily report for ChatGPT

2. **Submit to ChatGPT**:
   - Copy the terminal output
   - Paste into ChatGPT for analysis
   - Receive trade recommendations

3. **Log Manual Trades** (if any):
   - Enter buy/sell orders when prompted
   - These go into `chatgpt_trade_log.csv`

#### **Next Trading Day: 9:00 AM - 9:30 AM ET (Pre-Market)**
4. **Execute Trades via IB**:
   ```bash
   cd ib_trading
   python ib_executor.py --execute-pending --date $(date +%Y-%m-%d)
   ```
   - Executes accumulated trades from previous day
   - Places orders before market open

### **Weekly Deep Research Schedule**

#### **Friday Evening or Saturday**
- Run deep research prompt with ChatGPT
- More comprehensive portfolio analysis
- Strategic adjustments and new positions

### **Automated Monitoring Mode (Optional)**

For continuous execution without manual intervention:

```bash
# Terminal 1: Web Monitor
cd web_monitor
python app.py

# Terminal 2: IB Auto-Executor
cd ib_trading
python ib_executor.py --monitor  # Checks every 60 seconds
```

### **Important Timing Notes**

1. **Never Run During Market Hours** for daily updates - prices will be incomplete
2. **Weekend Runs**: Script automatically uses Friday's data
3. **Historical Backtesting**: Use `--asof YYYY-MM-DD` flag
4. **Market-on-Open Orders**: Must be placed before 9:30 AM ET
5. **Stop-Loss Triggers**: Processed automatically when running after close

### **Execution Verification Checklist**

After market close:
- [ ] Run `trading_script.py` 
- [ ] Submit results to ChatGPT
- [ ] Log any recommended trades
- [ ] Review `chatgpt_trade_log.csv` for new entries

Before next market open:
- [ ] Start IB Gateway/TWS
- [ ] Execute pending trades via `ib_executor.py`
- [ ] Verify execution in `ib_execution_log.csv`
- [ ] Check web monitor dashboard

### **Key Commands Reference**

#### Daily Trading Script
```bash
# Standard daily update
python trading_script.py --file "Scripts and CSV Files/chatgpt_portfolio_update.csv"

# Historical date
python trading_script.py --asof 2025-09-05 --file "Scripts and CSV Files/chatgpt_portfolio_update.csv"
```

#### IB Trade Execution
```bash
cd ib_trading

# Dry run (see what would be executed)
python ib_executor.py --dry-run --show-trades

# Execute all pending trades
python ib_executor.py --execute-pending --date $(date +%Y-%m-%d)

# Show execution history
python ib_executor.py --show-executions --days 7

# Continuous monitoring
python ib_executor.py --monitor
```

#### Web Monitor
```bash
cd web_monitor
python app.py
# Access at: http://localhost:8889
```

#### Performance Graphs
```bash
python "Start Your Own/Generate_Graph.py"
```

### **File Locations**

- **Portfolio State**: `Scripts and CSV Files/chatgpt_portfolio_update.csv`
- **Trade Signals**: `Scripts and CSV Files/chatgpt_trade_log.csv`
- **Execution Log**: `ib_trading/ib_execution_log.csv`
- **IB Config**: `ib_trading/ib_config.yaml`
- **Web Config**: `web_monitor/config.yaml`

### **Safety Reminders**

1. **Always start with paper trading** (`mode: "paper"` in `ib_config.yaml`)
2. **Verify IB Gateway connection** before executing trades
3. **Check daily trade limits** (default: 50 trades/day)
4. **Monitor stop-loss levels** for risk management
5. **Review execution logs** for slippage and fill quality

The key to success is **consistency**: run the same process at the same time each day after market close to ensure accurate data and proper stop-loss execution.