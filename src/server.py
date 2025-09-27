import argparse
import json
import os
import shutil
import threading
import time
from datetime import datetime

from flask import Flask, jsonify, request

app = Flask(__name__)

curr_dir = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = "host_ip_data.json"
BACKUP_DIR = curr_dir
DEFAULT_BACKUP_INTERVAL = 7200  # Default backup interval in seconds

# Authentication
server_password = None

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
                data = json.load(f)
                host_ip_map = data.get("hosts", {})
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
        data = {"hosts": host_ip_map}
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Saved {len(host_ip_map)} hosts to {DATA_FILE}")
    except Exception as e:
        print(f"Error saving data: {e}")


def create_backup():
    """Create data backup"""
    # Create empty data file if it doesn't exist
    if not os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "w") as f:
                json.dump({}, f, indent=2)
            print(f"Created empty data file: {DATA_FILE}")
        except Exception as e:
            print(f"Error creating empty data file: {e}")
            return

    ensure_backup_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"host_ip_data_{timestamp}.json")
    try:
        shutil.copy2(DATA_FILE, backup_file)
        print(f"Created backup: {backup_file}")

        # Clean up old backups, keep only the latest 10
        backup_files = [f for f in os.listdir(BACKUP_DIR) if f.startswith("host_ip_data_") and f.endswith(".json")]
        if len(backup_files) > 10:
            backup_files.sort(reverse=True)  # Sort by name descending (newest first)
            files_to_delete = backup_files[10:]  # Keep first 10, delete the rest
            for file in files_to_delete:
                os.remove(os.path.join(BACKUP_DIR, file))
                print(f"Deleted old backup: {file}")

    except Exception as e:
        print(f"Error creating backup: {e}")


def backup_task(interval):
    """Scheduled backup task"""
    while True:
        time.sleep(interval)
        create_backup()


def check_auth(data):
    """Check authentication from request data"""
    if server_password is None:
        return True  # No password required

    if not data:
        return False

    # Check for token first
    if "token" in data:
        for host, host_info in host_ip_map.items():
            if host_info.get("token") == data["token"]:
                # Check if token is expired (1 hour)
                token_time = datetime.fromisoformat(host_info["token_timestamp"])
                if (datetime.now() - token_time).total_seconds() > 3600:  # 1 hour
                    del host_ip_map[host]["token"]
                    del host_ip_map[host]["token_timestamp"]
                    save_data()  # Save after removing expired token
                    return False
                return True

    # Fallback to password for initial auth
    if "password" in data and data["password"] == server_password:
        return True

    return False


@app.route("/auth", methods=["POST"])
def authenticate():
    """Authenticate client and return token"""
    data = request.get_json()

    if not data or "password" not in data or "host" not in data:
        return jsonify({"error": "Missing password or host"}), 400

    if data["password"] != server_password:
        return jsonify({"error": "Authentication failed"}), 401

    # Use hostname as client_id
    client_id = data["host"]

    # Check if client already has a token
    if client_id in host_ip_map and "token" in host_ip_map[client_id]:
        # Check if existing token is still valid
        token_time = datetime.fromisoformat(host_ip_map[client_id]["token_timestamp"])
        if (datetime.now() - token_time).total_seconds() <= 3600:  # 1 hour
            return jsonify({"token": host_ip_map[client_id]["token"]})
        else:
            # Token expired, remove it
            del host_ip_map[client_id]["token"]
            del host_ip_map[client_id]["token_timestamp"]

    # Generate a new token
    import uuid

    token = str(uuid.uuid4())
    if client_id not in host_ip_map:
        host_ip_map[client_id] = {"interfaces": {}, "last_updated": datetime.now().isoformat()}
    host_ip_map[client_id]["token"] = token
    host_ip_map[client_id]["token_timestamp"] = datetime.now().isoformat()

    save_data()  # Save after adding token

    return jsonify({"token": token})


@app.route("/publish", methods=["POST"])
def publish_ip():
    """Receive IP address from client"""
    data = request.get_json()

    if not check_auth(data):
        return jsonify({"error": "Authentication failed"}), 401

    if not data or "host" not in data or "ip" not in data or "interface" not in data:
        print(f"Invalid request data: {data}")
        return jsonify({"error": "Missing host, ip, or interface"}), 400

    host = data["host"]
    ip = data["ip"]
    interface = data["interface"]
    timestamp = datetime.now().isoformat()

    if host not in host_ip_map:
        host_ip_map[host] = {"interfaces": {}, "last_updated": timestamp}
    elif "interfaces" not in host_ip_map[host]:
        print(f"Adding interfaces dictionary for existing host {host}")
        host_ip_map[host]["interfaces"] = {}

    host_ip_map[host]["interfaces"][interface] = {"ip": ip, "last_updated": timestamp}
    host_ip_map[host]["last_updated"] = timestamp

    save_data()

    print(f"Updated IP for host:{host} interface:{interface} ip:{ip}")
    return jsonify({"status": "success"})


@app.route("/subscribe", methods=["POST"])
def subscribe():
    """Return specified host:interface information mapping"""
    data = request.get_json()

    if not check_auth(data):
        return jsonify({"error": "Authentication failed"}), 401

    if not data or "hosts" not in data:
        return jsonify({"error": "Missing hosts parameter"}), 400

    # Filter specified hosts and interfaces
    filtered_data = {}
    for host in data["hosts"]:
        if host in host_ip_map:
            filtered_data[host] = {"interfaces": {}, "last_updated": host_ip_map[host]["last_updated"]}

            # If interfaces are specified, only return those interface information
            if "interfaces" in data and host in data["interfaces"]:
                for interface in data["interfaces"][host]:
                    if interface in host_ip_map[host]["interfaces"]:
                        filtered_data[host]["interfaces"][interface] = host_ip_map[host]["interfaces"][interface]
            else:
                filtered_data[host]["interfaces"] = host_ip_map[host]["interfaces"]

    # Check for new devices joined
    all_hosts = set(host_ip_map.keys())
    requested_hosts = set(data["hosts"])
    new_hosts = all_hosts - requested_hosts
    if new_hosts:
        filtered_data["new_device_joined"] = True
        filtered_data["all_hosts"] = list(all_hosts)
    else:
        filtered_data["new_device_joined"] = False

    return jsonify(filtered_data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IP Server")
    parser.add_argument("--host", default="0.0.0.0", help="Server host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="Server port (default: 8080)")
    parser.add_argument(
        "--backup-interval",
        type=int,
        default=DEFAULT_BACKUP_INTERVAL,
        help=f"Backup interval in seconds (default: {DEFAULT_BACKUP_INTERVAL})",
    )
    parser.add_argument("--password", help="Password for client authentication")
    args = parser.parse_args()

    server_password = args.password

    print(f"Backup interval: {args.backup_interval}")
    if args.password:
        print("Password authentication enabled")
    else:
        print("Warning: No password set - clients can connect without authentication")

    load_data()

    backup_thread = threading.Thread(target=backup_task, args=(args.backup_interval,), daemon=True)
    backup_thread.start()

    app.run(host=args.host, port=args.port)
