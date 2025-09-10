"""
High-performance caching system with file watching
Uses watchdog for real-time updates and LRU cache for performance
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Set, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging
import threading
import time
from collections import OrderedDict

logger = logging.getLogger(__name__)

class LRUCache:
    """Thread-safe LRU cache implementation"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache: OrderedDict = OrderedDict()
        self.lock = threading.RLock()
        self.stats = {'hits': 0, 'misses': 0, 'evictions': 0}
    
    def get(self, key: str) -> Optional[Any]:
        with self.lock:
            if key in self.cache:
                # Move to end (most recently used)
                value = self.cache.pop(key)
                self.cache[key] = value
                self.stats['hits'] += 1
                return value
            else:
                self.stats['misses'] += 1
                return None
    
    def put(self, key: str, value: Any) -> None:
        with self.lock:
            if key in self.cache:
                # Update existing key
                self.cache.pop(key)
            elif len(self.cache) >= self.max_size:
                # Evict least recently used
                self.cache.popitem(last=False)
                self.stats['evictions'] += 1
            
            self.cache[key] = value
    
    def invalidate(self, key: str) -> None:
        with self.lock:
            self.cache.pop(key, None)
    
    def invalidate_prefix(self, prefix: str) -> None:
        """Invalidate all keys that start with the given prefix"""
        with self.lock:
            keys_to_delete = [k for k in list(self.cache.keys()) if str(k).startswith(prefix)]
            for k in keys_to_delete:
                self.cache.pop(k, None)
    
    def clear(self) -> None:
        with self.lock:
            self.cache.clear()
    
    def get_stats(self) -> Dict[str, int]:
        return self.stats.copy()

class FileWatchHandler(FileSystemEventHandler):
    """Handles file system events for cache invalidation"""
    
    def __init__(self, cache_manager):
        self.cache_manager = cache_manager
        self.debounce_delay = 0.1  # 100ms debounce
        self.pending_updates: Set[str] = set()
        self.timer: Optional[threading.Timer] = None
        self.lock = threading.Lock()
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if self._should_watch_file(file_path):
            self._schedule_update(str(file_path))
    
    def on_created(self, event):
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if self._should_watch_file(file_path):
            self._schedule_update(str(file_path))
    
    def _should_watch_file(self, file_path: Path) -> bool:
        """Check if we should monitor this file"""
        watch_patterns = [
            'chatgpt_portfolio_update.csv',
            'chatgpt_trade_log.csv', 
            'ib_execution_log.csv',
            'cp_execution_log.csv',
            'ib_executor.log',
            'cp_api.log',
            'cp_errors.log',
            '.ib_checkpoint.json',
            '.cp_checkpoint.json'
        ]
        return file_path.name in watch_patterns
    
    def _schedule_update(self, file_path: str) -> None:
        """Schedule debounced cache update"""
        with self.lock:
            self.pending_updates.add(file_path)
            
            # Cancel existing timer
            if self.timer:
                self.timer.cancel()
            
            # Schedule new update
            self.timer = threading.Timer(self.debounce_delay, self._process_updates)
            self.timer.start()
    
    def _process_updates(self) -> None:
        """Process pending file updates"""
        with self.lock:
            if self.pending_updates:
                logger.info(f"Processing cache updates for {len(self.pending_updates)} files")
                for file_path in self.pending_updates:
                    self.cache_manager.invalidate_file(file_path)
                
                # Notify WebSocket clients - thread-safe notification
                try:
                    # Try to get the running event loop
                    loop = asyncio.get_running_loop()
                    # Schedule the notification on the main event loop thread
                    loop.call_soon_threadsafe(lambda: asyncio.create_task(self.cache_manager.notify_clients()))
                except RuntimeError:
                    # No event loop running, skip notifications
                    # This happens during startup before the web server is ready
                    pass
                
                self.pending_updates.clear()

class CacheManager:
    """Manages caching and file watching for the pipeline monitor"""
    
    def __init__(self, data_dirs: List[str], cache_size: int = 1000):
        self.data_dirs = [Path(d) for d in data_dirs]
        self.cache = LRUCache(cache_size)
        self.observers: List[Observer] = []
        self.file_handler = FileWatchHandler(self)
        self.websocket_clients: Set[Any] = set()
        self.last_update = datetime.now()
        
        # Start file watching
        self._start_watching()
    
    def _start_watching(self) -> None:
        """Start watching all data directories"""
        for data_dir in self.data_dirs:
            if data_dir.exists():
                observer = Observer()
                observer.schedule(self.file_handler, str(data_dir), recursive=False)
                observer.start()
                self.observers.append(observer)
                logger.info(f"Started watching directory: {data_dir}")
    
    def stop_watching(self) -> None:
        """Stop all file observers"""
        for observer in self.observers:
            observer.stop()
            observer.join()
        self.observers.clear()
        logger.info("Stopped all file watchers")
    
    def get_cached_or_compute(self, key: str, compute_func: callable, ttl_seconds: int = 60) -> Any:
        """Get cached value or compute it"""
        # Check cache first
        cached_item = self.cache.get(key)
        if cached_item:
            value, timestamp = cached_item
            if datetime.now() - timestamp < timedelta(seconds=ttl_seconds):
                return value
        
        # Compute new value
        try:
            value = compute_func()
            self.cache.put(key, (value, datetime.now()))
            return value
        except Exception as e:
            logger.error(f"Error computing value for key {key}: {e}")
            return None
    
    def invalidate_file(self, file_path: str) -> None:
        """Invalidate cache entries related to a file"""
        file_path = Path(file_path)
        
        # Invalidate based on file type
        if 'portfolio_update' in file_path.name:
            self.cache.invalidate('current_portfolio')
            self.cache.invalidate('portfolio_history')
            self.cache.invalidate('performance_metrics')
            self.cache.invalidate('system_status')
            logger.debug(f"Invalidated portfolio cache due to {file_path}")
        
        elif 'trade_log' in file_path.name:
            self.cache.invalidate('pending_trades')
            self.cache.invalidate('system_status')
            logger.debug(f"Invalidated trades cache due to {file_path}")
        
        elif 'execution_log' in file_path.name:
            # Invalidate all variations by days (execution_history_*) and dependent metrics
            self.cache.invalidate_prefix('execution_history_')
            self.cache.invalidate('performance_metrics')
            self.cache.invalidate('system_status')
            logger.debug(f"Invalidated execution cache due to {file_path}")
        
        elif 'ib_executor.log' in file_path.name:
            self.cache.invalidate_prefix('recent_logs_')
            self.cache.invalidate('system_status')
            logger.debug(f"Invalidated logs cache due to {file_path}")

        elif 'cp_api.log' in file_path.name or 'cp_errors.log' in file_path.name:
            self.cache.invalidate_prefix('recent_logs_')
            self.cache.invalidate('system_status')
            logger.debug(f"Invalidated CP logs cache due to {file_path}")

        elif '.ib_checkpoint.json' in file_path.name or '.cp_checkpoint.json' in file_path.name:
            self.cache.invalidate('pending_trades')
            self.cache.invalidate('system_status')
            logger.debug(f"Invalidated checkpoint cache due to {file_path}")
        
        self.last_update = datetime.now()
    
    def add_websocket_client(self, websocket) -> None:
        """Register WebSocket client for updates"""
        self.websocket_clients.add(websocket)
        logger.info(f"Added WebSocket client, total: {len(self.websocket_clients)}")
    
    def remove_websocket_client(self, websocket) -> None:
        """Unregister WebSocket client"""
        self.websocket_clients.discard(websocket)
        logger.info(f"Removed WebSocket client, total: {len(self.websocket_clients)}")
    
    async def notify_clients(self, message: Dict[str, Any] = None) -> None:
        """Notify all WebSocket clients of updates"""
        if not self.websocket_clients:
            return
        
        if not message:
            message = {
                'type': 'update',
                'timestamp': self.last_update.isoformat(),
                'cache_stats': self.cache.get_stats()
            }
        
        # Send to all connected clients
        disconnected_clients = set()
        for client in self.websocket_clients.copy():
            try:
                await client.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send message to client: {e}")
                disconnected_clients.add(client)
        
        # Clean up disconnected clients
        for client in disconnected_clients:
            self.websocket_clients.discard(client)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        stats = self.cache.get_stats()
        stats.update({
            'cache_size': len(self.cache.cache),
            'max_size': self.cache.max_size,
            'hit_rate': stats['hits'] / max(stats['hits'] + stats['misses'], 1),
            'watching_dirs': len([d for d in self.data_dirs if d.exists()]),
            'websocket_clients': len(self.websocket_clients),
            'last_update': self.last_update.isoformat()
        })
        return stats
    
    def force_refresh(self) -> None:
        """Force refresh all cache entries"""
        self.cache.clear()
        self.last_update = datetime.now()
        logger.info("Force refreshed all cache entries")
    
    def __del__(self):
        """Cleanup file watchers on destruction"""
        self.stop_watching()
