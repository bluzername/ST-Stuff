"""
FastAPI web server for trading pipeline monitoring
Global access configured, WebSocket support, no-bullshit implementation
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
import yaml
import logging
import asyncio
from pathlib import Path
from typing import Dict, List, Any
import uvicorn

from monitor import PipelineMonitor
from cache import CacheManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TradingMonitorApp:
    """Main application class"""
    
    def __init__(self, config_path: str = "config.yaml"):
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Initialize monitoring components
        data_dirs = self.config['monitoring']['data_directories']
        cache_size = self.config['monitoring']['cache_size']
        
        self.monitor = PipelineMonitor(data_dirs)
        self.cache_manager = CacheManager(data_dirs, cache_size)
        
        # Create FastAPI app
        self.app = FastAPI(
            title="Trading Pipeline Monitor",
            description="Real-time monitoring dashboard for ChatGPT trading pipeline",
            version="1.0.0"
        )
        
        # Setup routes
        self._setup_routes()
        
        # Mount static files
        static_path = Path(__file__).parent / "static"
        if static_path.exists():
            self.app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            # Default config for global access
            return {
                'server': {'host': '0.0.0.0', 'port': 8888, 'reload': False},
                'monitoring': {
                    'data_directories': ['../Scripts and CSV Files', '../Start Your Own', '../ib_trading'],
                    'cache_size': 1000,
                    'update_interval': 0.1
                },
                'display': {'max_recent_trades': 50, 'max_log_lines': 100, 'chart_days': 30}
            }
    
    def _setup_routes(self):
        """Setup all API routes"""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def serve_dashboard():
            """Serve main dashboard page"""
            dashboard_file = Path(__file__).parent / "static" / "dashboard.html"
            if dashboard_file.exists():
                return FileResponse(dashboard_file)
            else:
                return HTMLResponse("""
                <html><body>
                <h1>Trading Pipeline Monitor</h1>
                <p>Dashboard not found. Run from web_monitor directory.</p>
                <p><a href='/api/status'>View API Status</a></p>
                </body></html>
                """)
        
        @self.app.get("/api/status")
        async def get_system_status():
            """Get overall system status"""
            def compute_status():
                return self.monitor.get_system_status()
            
            return self.cache_manager.get_cached_or_compute('system_status', compute_status, 30)
        
        @self.app.get("/api/portfolio")
        async def get_current_portfolio():
            """Get current portfolio positions"""
            def compute_portfolio():
                return self.monitor.get_current_portfolio()
            
            return self.cache_manager.get_cached_or_compute('current_portfolio', compute_portfolio, 60)
        
        @self.app.get("/api/trades/pending")
        async def get_pending_trades():
            """Get pending trades"""
            def compute_pending():
                return self.monitor.get_pending_trades()
            
            return self.cache_manager.get_cached_or_compute('pending_trades', compute_pending, 30)
        
        @self.app.get("/api/trades/executed")
        async def get_execution_history(days: int = 7):
            """Get execution history"""
            cache_key = f'execution_history_{days}'
            
            def compute_executions():
                return self.monitor.get_execution_history(days)
            
            return self.cache_manager.get_cached_or_compute(cache_key, compute_executions, 60)
        
        @self.app.get("/api/performance")
        async def get_performance_metrics():
            """Get performance metrics"""
            def compute_metrics():
                return self.monitor.get_performance_metrics()
            
            return self.cache_manager.get_cached_or_compute('performance_metrics', compute_metrics, 60)
        
        @self.app.get("/api/logs")
        async def get_recent_logs(max_lines: int = 100):
            """Get recent log entries"""
            cache_key = f'recent_logs_{max_lines}'
            
            def compute_logs():
                return self.monitor.get_recent_logs(max_lines)
            
            return self.cache_manager.get_cached_or_compute(cache_key, compute_logs, 10)
        
        @self.app.get("/api/cache/stats")
        async def get_cache_stats():
            """Get cache performance statistics"""
            return self.cache_manager.get_cache_stats()
        
        @self.app.post("/api/cache/refresh")
        async def refresh_cache():
            """Force refresh all cached data"""
            self.cache_manager.force_refresh()
            return {"status": "cache_refreshed", "timestamp": self.cache_manager.last_update.isoformat()}
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates"""
            await websocket.accept()
            self.cache_manager.add_websocket_client(websocket)
            
            try:
                # Send initial data
                initial_data = {
                    'type': 'initial',
                    'status': await get_system_status(),
                    'portfolio': await get_current_portfolio(),
                    'pending_trades': await get_pending_trades(),
                    'recent_executions': await get_execution_history(days=1),
                    'performance': await get_performance_metrics()
                }
                await websocket.send_json(initial_data)
                
                # Keep connection alive and handle client messages
                while True:
                    try:
                        # Wait for client message (ping/pong or commands)
                        message = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
                        
                        if message.get('type') == 'ping':
                            await websocket.send_json({'type': 'pong'})
                        elif message.get('type') == 'refresh':
                            # Send fresh data
                            fresh_data = {
                                'type': 'refresh',
                                'status': await get_system_status(),
                                'portfolio': await get_current_portfolio(),
                                'pending_trades': await get_pending_trades(),
                                'performance': await get_performance_metrics()
                            }
                            await websocket.send_json(fresh_data)
                    
                    except asyncio.TimeoutError:
                        # Send periodic heartbeat
                        await websocket.send_json({'type': 'heartbeat', 'timestamp': self.cache_manager.last_update.isoformat()})
                    
            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            finally:
                self.cache_manager.remove_websocket_client(websocket)
        
        # Health check endpoint
        @self.app.get("/health")
        async def health_check():
            """Simple health check"""
            return {
                "status": "healthy",
                "service": "trading_monitor",
                "cache_stats": self.cache_manager.get_cache_stats()
            }
    
    def run(self):
        """Run the web server"""
        host = self.config['server']['host']
        port = self.config['server']['port']
        reload = self.config['server']['reload']
        
        logger.info(f"Starting Trading Pipeline Monitor on {host}:{port}")
        logger.info(f"Monitoring directories: {self.config['monitoring']['data_directories']}")
        logger.info(f"Global access enabled - server accessible from internet")
        
        try:
            uvicorn.run(
                "app:app_instance.app",
                host=host,
                port=port,
                reload=reload,
                access_log=True,
                log_level="info"
            )
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        finally:
            self.cache_manager.stop_watching()

# Global app instance
app_instance = TradingMonitorApp()
app = app_instance.app

if __name__ == "__main__":
    app_instance.run()