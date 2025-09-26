#!/usr/bin/env python3
"""
Script to simulate a new device joining the network.
This will send a publish request to the IPSyncer server to trigger client updates.
"""

import requests
import argparse
from datetime import datetime


def simulate_new_device(server_url, host, ip, interface):
    """Simulate a new device publishing its IP to the server"""
    data = {
        "host": host,
        "ip": ip,
        "interface": interface
    }

    try:
        response = requests.post(f"{server_url}/publish", json=data)
        if response.status_code == 200:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Successfully simulated new device: {host} {interface} {ip}")
            print(f"Response: {response.json()}")
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Failed to simulate new device: {response.text}")
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error simulating new device: {e}")


def main():
    parser = argparse.ArgumentParser(description="Simulate a new device joining the IPSyncer network")
    parser.add_argument(
        "--server",
        default="http://localhost:8080",
        help="Server URL (default: http://localhost:8080)"
    )
    parser.add_argument(
        "--host",
        default="new-device-test",
        help="Device hostname (default: new-device-test)"
    )
    parser.add_argument(
        "--ip",
        default="192.168.1.100",
        help="Device IP address (default: 192.168.1.100)"
    )
    parser.add_argument(
        "--interface",
        default="eth0",
        help="Network interface (default: eth0)"
    )

    args = parser.parse_args()

    print(f"Simulating new device with:")
    print(f"  Server: {args.server}")
    print(f"  Host: {args.host}")
    print(f"  IP: {args.ip}")
    print(f"  Interface: {args.interface}")
    print()

    simulate_new_device(args.server, args.host, args.ip, args.interface)


if __name__ == "__main__":
    main()