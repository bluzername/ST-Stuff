#!/usr/bin/env python3
"""
Simple startup script for the trading monitor web server
Configured for global internet access
"""

import sys
import os
import subprocess
from pathlib import Path

def main():
    # Ensure we're in the right directory
    monitor_dir = Path(__file__).parent
    os.chdir(monitor_dir)
    
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║                   TRADING PIPELINE MONITOR                    ║")
    print("║                                                                ║")
    print("║  Starting web server for global internet access...            ║")
    print("║                                                                ║")
    print("║  Local:    http://localhost:8888                              ║")
    print("║  Network:  http://YOUR_IP:8888                                ║")
    print("║                                                                ║")
    print("║  Press Ctrl+C to stop                                         ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print()
    
    # Show network info
    try:
        import socket
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        print(f"Server hostname: {hostname}")
        print(f"Local IP: {local_ip}")
        print(f"Access from network: http://{local_ip}:8888")
    except:
        print("Could not determine local IP address")
    
    print("-" * 70)
    print()
    
    # Check if config exists
    config_file = monitor_dir / "config.yaml"
    if not config_file.exists():
        print("WARNING: config.yaml not found, using defaults")
    
    # Start the server
    try:
        cmd = [
            sys.executable, 
            "app.py"
        ]
        
        subprocess.run(cmd, check=True)
        
    except KeyboardInterrupt:
        print("\n\nServer stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"\nError starting server: {e}")
        return 1
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())