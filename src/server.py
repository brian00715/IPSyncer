from flask import Flask, request, jsonify
import time
import json
import os
from datetime import datetime
import threading
import shutil
import argparse

app = Flask(__name__)

curr_dir = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = "host_ip_data.json"
BACKUP_DIR = curr_dir
DEFAULT_BACKUP_INTERVAL = 7200  # Default backup interval in seconds

# Dictionary to store host:interface information
# Format: {
#   "hostname": {
#     "interfaces": {
#       "tun0": {"ip": "1.2.3.4", "last_updated": "timestamp"},
#       "eth0": {"ip": "5.6.7.8", "last_updated": "timestamp"}
#     },
#     "last_updated": "timestamp"
#   }
# }
host_ip_map = {}


def ensure_backup_dir():
    """Ensure backup directory exists"""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)


def load_data():
    """Load data from file"""
    global host_ip_map
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                host_ip_map = json.load(f)
            # Ensure each host record has the correct structure
            for host in host_ip_map:
                if "interfaces" not in host_ip_map[host]:
                    host_ip_map[host]["interfaces"] = {}
                if "last_updated" not in host_ip_map[host]:
                    host_ip_map[host]["last_updated"] = datetime.now().isoformat()
            print(f"Loaded {len(host_ip_map)} hosts from {DATA_FILE}")
        except Exception as e:
            print(f"Error loading data: {e}")
            host_ip_map = {}


def save_data():
    """Save data to file"""
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(host_ip_map, f, indent=2)
        print(f"Saved {len(host_ip_map)} hosts to {DATA_FILE}")
    except Exception as e:
        print(f"Error saving data: {e}")


def create_backup():
    """Create data backup"""
    ensure_backup_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"host_ip_data_{timestamp}.json")
    try:
        shutil.copy2(DATA_FILE, backup_file)
        print(f"Created backup: {backup_file}")
    except Exception as e:
        print(f"Error creating backup: {e}")


def backup_task(interval):
    """Scheduled backup task"""
    while True:
        time.sleep(interval)
        create_backup()


@app.route("/publish", methods=["POST"])
def publish_ip():
    """Receive IP address from client"""
    data = request.get_json()
    
    if not data or "host" not in data or "ip" not in data or "interface" not in data:
        print(f"Invalid request data: {data}")
        return jsonify({"error": "Missing host, ip, or interface"}), 400

    host = data["host"]
    ip = data["ip"]
    interface = data["interface"]
    timestamp = datetime.now().isoformat()

    if host not in host_ip_map:
        host_ip_map[host] = {
            "interfaces": {},
            "last_updated": timestamp
        }
    elif "interfaces" not in host_ip_map[host]:
        print(f"Adding interfaces dictionary for existing host {host}")
        host_ip_map[host]["interfaces"] = {}

    host_ip_map[host]["interfaces"][interface] = {
        "ip": ip,
        "last_updated": timestamp
    }
    host_ip_map[host]["last_updated"] = timestamp

    save_data()

    print(f"Updated IP for host:{host} interface:{interface} ip:{ip}")
    return jsonify({"status": "success"})


@app.route("/subscribe", methods=["POST"])
def subscribe():
    """Return specified host:interface information mapping"""
    data = request.get_json()
    if not data or "hosts" not in data:
        return jsonify({"error": "Missing hosts parameter"}), 400

    # Filter specified hosts and interfaces
    filtered_data = {}
    for host in data["hosts"]:
        if host in host_ip_map:
            filtered_data[host] = {
                "interfaces": {},
                "last_updated": host_ip_map[host]["last_updated"]
            }
            
            # If interfaces are specified, only return those interface information
            if "interfaces" in data and host in data["interfaces"]:
                for interface in data["interfaces"][host]:
                    if interface in host_ip_map[host]["interfaces"]:
                        filtered_data[host]["interfaces"][interface] = host_ip_map[host]["interfaces"][interface]
            else:
                filtered_data[host]["interfaces"] = host_ip_map[host]["interfaces"]

    return jsonify(filtered_data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='IP Server')
    parser.add_argument('--host', default='0.0.0.0', help='Server host (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8080, help='Server port (default: 8080)')
    parser.add_argument('--backup-interval', type=int, default=DEFAULT_BACKUP_INTERVAL, 
                       help=f'Backup interval in seconds (default: {DEFAULT_BACKUP_INTERVAL})')
    args = parser.parse_args()
    
    print(f"Backup interval: {args.backup_interval}")

    load_data()

    backup_thread = threading.Thread(target=backup_task, args=(args.backup_interval,), daemon=True)
    backup_thread.start()

    app.run(host=args.host, port=args.port)
