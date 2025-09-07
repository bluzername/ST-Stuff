/**
 * Trading Pipeline Monitor - Pure JavaScript Client
 * WebSocket-based real-time updates, no framework dependencies
 */

class TradingMonitor {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000;
        this.isConnected = false;
        this.lastHeartbeat = null;
        
        // DOM elements cache
        this.elements = {};
        this.charts = {};
        
        this.init();
    }
    
    init() {
        this.cacheElements();
        this.setupWebSocket();
        this.setupEventListeners();
        this.startHeartbeat();
        
        console.log('Trading Monitor initialized');
    }
    
    cacheElements() {
        // Status elements
        this.elements.connectionStatus = document.getElementById('connection-status');
        this.elements.connectionIndicator = document.getElementById('connection-indicator');
        this.elements.tradingMode = document.getElementById('trading-mode');
        this.elements.lastUpdate = document.getElementById('last-update');
        this.elements.ibStatus = document.getElementById('ib-status');
        
        // Portfolio elements
        this.elements.portfolioTable = document.getElementById('portfolio-table');
        this.elements.totalValue = document.getElementById('total-value');
        this.elements.totalPnL = document.getElementById('total-pnl');
        this.elements.positionCount = document.getElementById('position-count');
        
        // Pending trades
        this.elements.pendingTrades = document.getElementById('pending-trades');
        this.elements.pendingCount = document.getElementById('pending-count');
        
        // Execution history
        this.elements.executionHistory = document.getElementById('execution-history');
        this.elements.executionCount = document.getElementById('execution-count');
        
        // Performance metrics
        this.elements.dailyPnL = document.getElementById('daily-pnl');
        this.elements.dailyVolume = document.getElementById('daily-volume');
        this.elements.avgSlippage = document.getElementById('avg-slippage');
        this.elements.dailyTrades = document.getElementById('daily-trades');
        
        // Chart canvas
        this.elements.performanceChart = document.getElementById('performance-chart');
        
        // Logs
        this.elements.logContainer = document.getElementById('log-container');
        
        console.log('DOM elements cached');
    }
    
    setupWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        try {
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.updateConnectionStatus('online', 'Connected');
            };
            
            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleWebSocketMessage(data);
                    this.lastHeartbeat = Date.now();
                } catch (error) {
                    console.error('Error parsing WebSocket message:', error);
                }
            };
            
            this.ws.onclose = (event) => {
                console.log('WebSocket disconnected:', event.code, event.reason);
                this.isConnected = false;
                this.updateConnectionStatus('offline', 'Disconnected');
                this.attemptReconnect();
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateConnectionStatus('offline', 'Connection Error');
            };
            
        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            this.updateConnectionStatus('offline', 'Connection Failed');
        }
    }
    
    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'initial':
                this.updateAllData(data);
                break;
            case 'update':
                this.fetchAndUpdateAll();
                break;
            case 'refresh':
                this.updateAllData(data);
                break;
            case 'heartbeat':
                this.updateLastActivity(data.timestamp);
                break;
            case 'pong':
                // Heartbeat response
                break;
            default:
                console.log('Unknown message type:', data.type);
        }
    }
    
    updateAllData(data) {
        if (data.status) this.updateSystemStatus(data.status);
        if (data.portfolio) this.updatePortfolio(data.portfolio);
        if (data.pending_trades) this.updatePendingTrades(data.pending_trades);
        if (data.recent_executions) this.updateExecutionHistory(data.recent_executions);
        if (data.performance) this.updatePerformance(data.performance);
    }
    
    updateSystemStatus(status) {
        // Trading mode
        if (this.elements.tradingMode) {
            this.elements.tradingMode.textContent = (status.trading_mode || 'unknown').toUpperCase();
            this.elements.tradingMode.className = `status-item ${status.trading_mode === 'paper' ? 'status-warning' : 'status-online'}`;
        }
        
        // IB connection status
        if (this.elements.ibStatus && status.ib_connection) {
            const ibConnected = status.ib_connection.connected;
            this.elements.ibStatus.innerHTML = `
                <span class="status-indicator ${ibConnected ? 'status-online' : 'status-offline'}"></span>
                IB: ${ibConnected ? 'Connected' : 'Disconnected'}
            `;
        }
        
        // Last activity
        if (status.last_activity) {
            this.updateLastActivity(status.last_activity);
        }
    }
    
    updatePortfolio(portfolio) {
        if (!this.elements.portfolioTable) return;
        
        const tbody = this.elements.portfolioTable.querySelector('tbody') || 
                     this.elements.portfolioTable.appendChild(document.createElement('tbody'));
        
        tbody.innerHTML = '';
        
        let totalValue = 0;
        let totalPnL = 0;
        let positionCount = 0;
        
        portfolio.forEach(position => {
            if (position.shares > 0) {
                positionCount++;
                totalValue += position.market_value;
                totalPnL += position.unrealized_pnl;
                
                const row = tbody.insertRow();
                row.innerHTML = `
                    <td>${position.ticker}</td>
                    <td>${position.shares.toFixed(0)}</td>
                    <td>$${position.cost_basis.toFixed(2)}</td>
                    <td>$${position.current_price.toFixed(2)}</td>
                    <td>$${position.market_value.toFixed(2)}</td>
                    <td class="${position.unrealized_pnl >= 0 ? 'positive' : 'negative'}">
                        ${position.unrealized_pnl >= 0 ? '+' : ''}$${position.unrealized_pnl.toFixed(2)}
                    </td>
                    <td>$${position.stop_loss.toFixed(2)}</td>
                `;
            }
        });
        
        // Update summary
        if (this.elements.totalValue) {
            this.elements.totalValue.textContent = `$${totalValue.toFixed(2)}`;
        }
        if (this.elements.totalPnL) {
            this.elements.totalPnL.textContent = `${totalPnL >= 0 ? '+' : ''}$${totalPnL.toFixed(2)}`;
            this.elements.totalPnL.className = totalPnL >= 0 ? 'positive' : 'negative';
        }
        if (this.elements.positionCount) {
            this.elements.positionCount.textContent = positionCount.toString();
        }
    }
    
    updatePendingTrades(trades) {
        if (!this.elements.pendingTrades) return;
        
        this.elements.pendingTrades.innerHTML = '';
        
        if (trades.length === 0) {
            this.elements.pendingTrades.innerHTML = '<div style="text-align: center; color: #888; padding: 20px;">No pending trades</div>';
        } else {
            trades.forEach(trade => {
                const tradeDiv = document.createElement('div');
                tradeDiv.className = 'trade-item';
                
                const validationClass = trade.validation_status === 'VALID' ? 'validation-valid' : 'validation-invalid';
                
                tradeDiv.innerHTML = `
                    <div>
                        <span class="trade-action trade-${trade.action.toLowerCase()}">${trade.action}</span>
                        <strong>${trade.ticker}</strong> ${trade.quantity}@$${trade.price.toFixed(2)}
                    </div>
                    <div>
                        <span class="trade-validation ${validationClass}">${trade.validation_status}</span>
                        <div style="font-size: 9px; color: #888;">${trade.date}</div>
                    </div>
                `;
                
                this.elements.pendingTrades.appendChild(tradeDiv);
            });
        }
        
        if (this.elements.pendingCount) {
            this.elements.pendingCount.textContent = trades.length.toString();
        }
    }
    
    updateExecutionHistory(executions) {
        if (!this.elements.executionHistory) return;
        
        this.elements.executionHistory.innerHTML = '';
        
        if (executions.length === 0) {
            this.elements.executionHistory.innerHTML = '<div style="text-align: center; color: #888; padding: 20px;">No recent executions</div>';
        } else {
            executions.slice(0, 10).forEach(execution => {
                const execDiv = document.createElement('div');
                execDiv.className = 'execution-item';
                
                const statusClass = `status-${execution.status.toLowerCase()}`;
                
                execDiv.innerHTML = `
                    <div>
                        <div><strong>${execution.ticker}</strong> ${execution.action} ${execution.quantity}</div>
                        <div class="execution-time">${execution.execution_time}</div>
                    </div>
                    <div>
                        <div>$${execution.executed_price.toFixed(2)}</div>
                        <span class="execution-status ${statusClass}">${execution.status}</span>
                    </div>
                `;
                
                this.elements.executionHistory.appendChild(execDiv);
            });
        }
        
        if (this.elements.executionCount) {
            this.elements.executionCount.textContent = executions.length.toString();
        }
    }
    
    updatePerformance(performance) {
        if (!performance) return;
        
        const portfolio = performance.portfolio || {};
        const executions = performance.executions || {};
        
        // Update metrics
        if (this.elements.dailyPnL) {
            const pnl = portfolio.total_pnl || 0;
            this.elements.dailyPnL.textContent = `${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}`;
            this.elements.dailyPnL.className = `metric-value ${pnl >= 0 ? 'positive' : 'negative'}`;
        }
        
        if (this.elements.dailyVolume) {
            this.elements.dailyVolume.textContent = `$${(executions.daily_volume || 0).toFixed(0)}`;
        }
        
        if (this.elements.avgSlippage) {
            const slippage = executions.avg_slippage || 0;
            this.elements.avgSlippage.textContent = `${slippage.toFixed(2)}%`;
            this.elements.avgSlippage.className = `metric-value ${Math.abs(slippage) > 1 ? 'negative' : 'positive'}`;
        }
        
        if (this.elements.dailyTrades) {
            this.elements.dailyTrades.textContent = (executions.daily_trades || 0).toString();
        }
        
        // TODO: Update performance chart
        this.updatePerformanceChart(performance);
    }
    
    updatePerformanceChart(performance) {
        // Simple placeholder chart - in production you'd use a proper charting library
        if (!this.elements.performanceChart) return;
        
        const canvas = this.elements.performanceChart;
        const ctx = canvas.getContext('2d');
        
        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Draw placeholder chart
        ctx.strokeStyle = '#00ff88';
        ctx.lineWidth = 2;
        
        ctx.beginPath();
        ctx.moveTo(0, canvas.height / 2);
        
        // Simple sine wave as placeholder
        for (let x = 0; x < canvas.width; x += 10) {
            const y = canvas.height / 2 + Math.sin(x * 0.02) * 50;
            ctx.lineTo(x, y);
        }
        
        ctx.stroke();
        
        // Draw axis labels
        ctx.fillStyle = '#888';
        ctx.font = '10px Monaco';
        ctx.fillText('Performance Chart (Placeholder)', 10, 20);
    }
    
    updateLastActivity(timestamp) {
        if (!this.elements.lastUpdate) return;
        
        try {
            const date = new Date(timestamp);
            this.elements.lastUpdate.textContent = date.toLocaleTimeString();
        } catch (error) {
            this.elements.lastUpdate.textContent = 'Invalid timestamp';
        }
    }
    
    updateConnectionStatus(status, message) {
        if (this.elements.connectionStatus) {
            this.elements.connectionStatus.textContent = message;
        }
        
        if (this.elements.connectionIndicator) {
            this.elements.connectionIndicator.className = `status-indicator status-${status}`;
        }
    }
    
    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('Max reconnection attempts reached');
            this.updateConnectionStatus('offline', 'Connection Failed');
            return;
        }
        
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, Math.min(this.reconnectAttempts - 1, 5));
        
        console.log(`Attempting reconnection ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${delay}ms`);
        this.updateConnectionStatus('warning', `Reconnecting... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        
        setTimeout(() => {
            this.setupWebSocket();
        }, delay);
    }
    
    setupEventListeners() {
        // Manual refresh button
        document.addEventListener('keydown', (event) => {
            if (event.key === 'F5' || (event.ctrlKey && event.key === 'r')) {
                event.preventDefault();
                this.forceRefresh();
            }
        });
        
        // Click to refresh areas
        document.addEventListener('click', (event) => {
            if (event.target.classList.contains('panel-header')) {
                this.forceRefresh();
            }
        });
    }
    
    startHeartbeat() {
        setInterval(() => {
            if (this.isConnected && this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'ping' }));
            }
            
            // Check for stale connection
            if (this.lastHeartbeat && Date.now() - this.lastHeartbeat > 60000) {
                console.log('Connection appears stale, reconnecting...');
                this.ws.close();
            }
        }, 30000); // Ping every 30 seconds
    }
    
    forceRefresh() {
        if (this.isConnected && this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'refresh' }));
        } else {
            // Fallback to REST API
            this.fetchAndUpdateAll();
        }
    }
    
    async fetchAndUpdateAll() {
        try {
            const [status, portfolio, pending, executions, performance] = await Promise.all([
                fetch('/api/status').then(r => r.json()),
                fetch('/api/portfolio').then(r => r.json()),
                fetch('/api/trades/pending').then(r => r.json()),
                fetch('/api/trades/executed?days=1').then(r => r.json()),
                fetch('/api/performance').then(r => r.json())
            ]);
            
            this.updateAllData({
                status,
                portfolio,
                pending_trades: pending,
                recent_executions: executions,
                performance
            });
            
        } catch (error) {
            console.error('Failed to fetch data:', error);
        }
    }
}

// Initialize monitor when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.tradingMonitor = new TradingMonitor();
});