import argparse
import os
import platform
import re
import socket
import subprocess
import time
from datetime import datetime

import psutil
import requests
import yaml

EXCLUDED_INTERFACE_PATTERNS = ["lo", "docker0", "utun.*"]


def is_excluded_interface(interface, patterns=None):
    """Check if an interface should be excluded based on patterns"""
    if patterns is None:
        patterns = EXCLUDED_INTERFACE_PATTERNS
    for pattern in patterns:
        if re.match(pattern, interface):
            return True
    return False


def parse_ifconfig(ifconfig_output, interfaces=None):
    """
    Parse the output of ifconfig command and extract IP addresses for specified interfaces.

    Args:
        ifconfig_output (str): The output of the ifconfig command as a string
        interfaces (list, optional): List of interface names to filter by.
                                     If None, all interfaces are included.

    Returns:
        dict: A dictionary with interface names as keys and their IP addresses as values
    """
    ip_dict = {}
    current_interface = None

    # Split the output into lines
    lines = ifconfig_output.strip().split("\n")

    for line in lines:
        # Check if this line starts a new interface definition
        if not line.startswith(" ") and not line.startswith("\t"):
            # Extract interface name (appears before ':' or ' ')
            parts = line.split(":" if ":" in line else " ", 1)
            current_interface = parts[0].strip()

            # Skip this interface if we have a filter and it's not in the list
            if interfaces and current_interface not in interfaces:
                current_interface = None

        # If we're tracking a relevant interface, look for inet/inet addr
        elif current_interface and ("inet " in line or "inet addr:" in line):
            # Handle different formats of ifconfig output
            if "inet addr:" in line:  # Older Linux systems
                ip = line.split("inet addr:")[1].split()[0]
            else:  # Newer Linux systems and macOS
                ip = line.split("inet ")[1].split()[0]

                # Some systems include subnet mask after '/'
                if "/" in ip:
                    ip = ip.split("/")[0]

            ip_dict[current_interface] = ip

    return ip_dict


def parse_ipconfig(ipconfig_output, interfaces=None):
    """
    Parse the output of ipconfig command (Windows) and extract IP addresses for specified interfaces.

    Args:
        ipconfig_output (str): The output of the ipconfig command as a string
        interfaces (list, optional): List of interface names to filter by.
                                     If None, all interfaces are included.

    Returns:
        dict: A dictionary with interface names as keys and their IP addresses as values
    """
    ip_dict = {}
    current_interface = None

    lines = ipconfig_output.strip().split("\n")

    for line in lines:
        line = line.strip()

        # Check if this line starts a new interface definition
        if line and not line.startswith(" ") and "adapter" in line.lower():
            # Extract interface name from "Ethernet adapter Local Area Connection:" format
            if ":" in line:
                current_interface = line.split(":")[0].strip()
                # Clean up the interface name
                if "adapter" in current_interface.lower():
                    current_interface = current_interface.split("adapter")[-1].strip()

            # Skip this interface if we have a filter and it's not in the list
            if interfaces and current_interface not in interfaces:
                current_interface = None

        # Look for IPv4 Address
        elif current_interface and "IPv4 Address" in line:
            # Extract IP from "   IPv4 Address. . . . . . . . . . . : 192.168.1.100"
            if ":" in line:
                ip = line.split(":")[-1].strip()
                # Remove any additional info like "(Preferred)"
                if "(" in ip:
                    ip = ip.split("(")[0].strip()
                ip_dict[current_interface] = ip

    return ip_dict


class IPClient:
    def __init__(
        self,
        server_url,
        update_interval=60,
        interfaces=None,
        subscribe_hosts=None,
        interface_mapping=None,
        config_file=None,
        dry_run=False,
        subscribe_all=False,
        password=None,
        excluded_interface_patterns=None,
        subscribe_config=False,
    ):
        self.server_url = server_url
        self.update_interval = update_interval
        self.config_file = config_file
        self.dry_run = dry_run
        self.subscribe_all = subscribe_all
        self.password = password
        self.token = None
        self.hostname = socket.gethostname()  # Store hostname for authentication
        self.excluded_interface_patterns = excluded_interface_patterns or EXCLUDED_INTERFACE_PATTERNS
        self.subscribe_config = subscribe_config

        # Set hosts file path based on OS
        self.os_type = platform.system().lower() if not self.dry_run else "fake"
        if self.os_type == "windows":
            self.hosts_file = r"C:\Windows\System32\drivers\etc\hosts"
        elif self.os_type == "fake":
            self.hosts_file = "./fake_hosts"
            with open(self.hosts_file, "a"):
                os.utime(self.hosts_file, None)  # Create the file if it doesn't exist
        else:
            self.hosts_file = "/etc/hosts"

        # List of interfaces to publish, if None then publish all interfaces
        self.interfaces = interfaces
        # Hosts and interfaces to subscribe to
        # Format: {
        #   "hostname": ["interface1", "interface2"],  # specific interfaces
        #   "hostname2": None  # subscribe to all interfaces
        # }
        self.subscribe_hosts = subscribe_hosts or {}
        # Mapping from host and interface to hostname
        # Format: {
        #   "hostname:interface": "target_hostname"
        # }
        self.interface_mapping = interface_mapping or {}

    def get_network_interfaces(self):
        """Get network interface information based on OS"""
        try:
            if self.os_type == "windows":
                output = subprocess.check_output(["ipconfig"], shell=True).decode("utf-8", errors="ignore")
                ip_dict = parse_ipconfig(output, self.interfaces)
            else:
                output = subprocess.check_output(["ifconfig"]).decode("utf-8")
                ip_dict = parse_ifconfig(output, self.interfaces)

            # Filter out excluded interfaces
            filtered_ip_dict = {
                interface: ip
                for interface, ip in ip_dict.items()
                if not is_excluded_interface(interface, self.excluded_interface_patterns)
            }
            return filtered_ip_dict
        except subprocess.CalledProcessError as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error getting network interfaces: {e}")
            return {}
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error parsing network interfaces: {e}")
            return {}

    def publish_ips(self):
        """Publish specified interface IP addresses to server"""
        interface_ips = self.get_network_interfaces()
        hostname = socket.gethostname()

        for interface, ip in interface_ips.items():
            if ip:  # Only publish interfaces with IP
                data = {"host": hostname, "ip": ip, "interface": interface}
                if self.token:
                    data["token"] = self.token

                try:
                    response = requests.post(f"{self.server_url}/publish", json=data)
                    if response.status_code == 200:
                        print(
                            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Published IP {ip} for {hostname} {interface}"
                        )
                    else:
                        print(
                            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Failed to publish IP for {interface}: {response.text}"
                        )
                except Exception as e:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error publishing IP for {interface}: {e}")
            else:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] No IP found for interface {interface}")

    def get_hostname_for_interface(self, host, interface):
        """Get corresponding hostname based on host and interface name"""
        # Check for specific mapping rules
        mapping_key = f"{host}:{interface}"
        if mapping_key in self.interface_mapping:
            return self.interface_mapping[mapping_key]
        # If no mapping rule, use default format
        return f"{host}-{interface}"

    def update_hosts(self, host_ips):
        """Update hosts file"""
        try:
            # Read existing hosts file
            with open(self.hosts_file, "r", encoding="utf-8", errors="ignore") as f:
                hosts_lines = f.readlines()

            # Create new hosts content
            new_hosts_lines = []
            hostname_updated = set()  # Track updated hostnames

            # Process existing lines
            for line in hosts_lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    new_hosts_lines.append(line)
                    continue

                parts = line.split()
                if len(parts) < 2:
                    new_hosts_lines.append(line)
                    continue

                ip = parts[0]
                hostnames = parts[1:]

                # Check if any hostnames need updating
                updated = False
                for i, hostname in enumerate(hostnames):
                    if hostname in host_ips:
                        # Update IP address
                        new_ip = host_ips[hostname]
                        if new_ip != ip:
                            # Replace IP address, keep other parts unchanged
                            parts[0] = new_ip
                            line = " ".join(parts)
                            updated = True
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {hostname} is updated to {new_ip}")
                        hostname_updated.add(hostname)

                new_hosts_lines.append(line)

            # Add new hostname entries
            for hostname, ip in host_ips.items():
                if hostname not in hostname_updated:
                    new_hosts_lines.append(f"{ip} {hostname}")

            # Write updated hosts file
            with open(self.hosts_file, "w", encoding="utf-8") as f:
                f.write("\n".join(new_hosts_lines) + "\n")

            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Updated hosts file at {self.hosts_file}")
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error updating hosts file: {e}")
            if self.os_type == "windows":
                print("Note: On Windows, you may need to run as Administrator to modify the hosts file")
            import traceback

            traceback.print_exc()

    def update_service(self, all_hosts):
        """Update config.yaml to subscribe to new hosts and reload service"""
        if not self.config_file:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] No config file specified, cannot update service")
            return

        try:
            # Read current config
            with open(self.config_file, "r") as f:
                config = yaml.safe_load(f)

            # Get current subscribe list
            current_subscribe = config.get("subscribe", [])
            current_hosts = set()
            for sub in current_subscribe:
                host = sub.split(":")[0]
                current_hosts.add(host)

            # Add new hosts
            new_hosts = set(all_hosts) - current_hosts
            for host in new_hosts:
                current_subscribe.append(host)  # Subscribe to all interfaces

            # Update config
            config["subscribe"] = current_subscribe

            # Write back
            with open(self.config_file, "w") as f:
                yaml.safe_dump(config, f, default_flow_style=False)

            print(
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Updated config.yaml with new hosts: {list(new_hosts)}"
            )

            # Reload systemd service
            try:
                if not self.dry_run:
                    subprocess.run(["sudo", "systemctl", "restart", "ipsyncer_client"], check=True)
                print(
                    f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Reloaded and restarted ipsyncer_client service"
                )
            except subprocess.CalledProcessError as e:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error reloading service: {e}")

        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error updating service: {e}")
            import traceback

            traceback.print_exc()

    def authenticate(self):
        """Authenticate with server and get token"""
        if not self.password:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] No password set, skipping authentication")
            return True

        try:
            response = requests.post(f"{self.server_url}/auth", json={"password": self.password, "host": self.hostname})
            if response.status_code == 200:
                data = response.json()
                if "token" in data:
                    self.token = data["token"]
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Authentication successful, token received")
                    return True
                else:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Authentication failed: Invalid response")
            else:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Authentication failed: {response.text}")
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Authentication error: {e}")

        return False

    def run(self):
        """Run the client"""
        # Authenticate first
        if not self.authenticate():
            print("Failed to authenticate with server. Exiting.")
            return

        print(f"Starting IP client on {self.os_type.title()} with server: {self.server_url}")
        print(f"Hosts file location: {self.hosts_file}")
        print(f"Publishing interfaces: {self.interfaces}")
        print(f"Subscribing to hosts: {self.subscribe_hosts}")
        print(f"Subscribe to all: {self.subscribe_all}")
        print(f"Hostname mapping: {self.interface_mapping}")

        while True:
            try:
                # Publish local IP
                self.publish_ips()

                # If subscribing to all and no hosts specified, get all hosts first
                if self.subscribe_all and not self.subscribe_hosts:
                    temp_data = {"hosts": []}
                    if self.token:
                        temp_data["token"] = self.token
                    temp_response = requests.post(f"{self.server_url}/subscribe", json=temp_data)
                    if temp_response.status_code == 200:
                        temp_mappings = temp_response.json()
                        if "all_hosts" in temp_mappings:
                            self.subscribe_hosts = {host: None for host in temp_mappings["all_hosts"]}

                # Prepare subscription request data
                subscribe_data = {"hosts": list(self.subscribe_hosts.keys())}

                # Add interface data if specified
                interfaces_data = {}
                for host, interfaces in self.subscribe_hosts.items():
                    if interfaces is not None:
                        interfaces_data[host] = interfaces
                if interfaces_data:
                    subscribe_data["interfaces"] = interfaces_data

                # Add token if authenticated
                if self.token:
                    subscribe_data["token"] = self.token

                # Add subscribe_config if enabled
                if self.subscribe_config:
                    subscribe_data["subscribe_config"] = True

                # Get IPs from other machines
                response = requests.post(f"{self.server_url}/subscribe", json=subscribe_data)
                if response.status_code == 200:
                    host_mappings = response.json()

                    # If subscribing to all, update subscribe_hosts with all known hosts
                    if self.subscribe_all and "all_hosts" in host_mappings:
                        self.subscribe_hosts = {host: None for host in host_mappings["all_hosts"]}

                    # Build host_ips dictionary
                    host_ips = {}
                    for host, info in host_mappings.items():
                        if host in ["new_device_joined", "all_hosts", "config"]:
                            continue  # Skip metadata
                        for interface, interface_info in info["interfaces"].items():
                            # Skip excluded interfaces
                            if is_excluded_interface(interface, self.excluded_interface_patterns):
                                continue
                            hostname = self.get_hostname_for_interface(host, interface)
                            if hostname and not hostname.startswith(self.hostname):
                                host_ips[hostname] = interface_info["ip"]

                    self.update_hosts(host_ips)
                else:
                    print(f"Failed to get host mappings: {response.text}")

                # Handle config if received
                if "config" in host_mappings:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Received config from server")
                    if self.config_file:
                        try:
                            # Read current local config to preserve publish field
                            current_config = {}
                            if os.path.exists(self.config_file):
                                with open(self.config_file, "r") as f:
                                    current_config = yaml.safe_load(f) or {}

                            # Get server config
                            server_config = host_mappings["config"]

                            # Preserve local publish field, update everything else from server
                            if "publish" in current_config:
                                server_config["publish"] = current_config["publish"]

                            # Write merged config
                            with open(self.config_file, "w") as f:
                                yaml.safe_dump(server_config, f, default_flow_style=False)
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Updated config file with server config (preserved local publish field)")
                        except Exception as e:
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error updating config file: {e}")
                    else:
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] No config file specified, config not saved")

                time.sleep(self.update_interval)
            except Exception as e:
                print(f"Error in main loop: {e}")
                import traceback

                traceback.print_exc()
                time.sleep(self.update_interval)


def parse_subscribe_hosts(subscribe_list):
    """Parse subscription hosts string list"""
    subscribe_hosts = {}
    subscribe_all = False
    if subscribe_list:
        for subscribe_str in subscribe_list:
            for item in subscribe_str.split(","):
                if item == "all":
                    subscribe_all = True
                else:
                    parts = item.split(":")
                    host = parts[0]
                    if len(parts) > 1:
                        interfaces = parts[1].split("+")
                        subscribe_hosts[host] = interfaces
                    else:
                        subscribe_hosts[host] = None
    else:
        subscribe_all = True  # Default to subscribe all if no specific hosts provided
    return subscribe_hosts, subscribe_all


def parse_interface_mapping(mapping_list):
    """Parse host and interface to hostname mapping string list"""
    mapping = {}
    if mapping_list:
        for mapping_str in mapping_list:
            for item in mapping_str.split(","):
                # Format: host:interface=target_hostname
                parts = item.split("=")
                if len(parts) == 2:
                    host_interface, target_hostname = parts
                    mapping[host_interface] = target_hostname
    return mapping


def main():

    parser = argparse.ArgumentParser(description="IP Auto-publish and Subscribe Client")
    parser.add_argument(
        "--config",
        type=str,
        help="YAML config file path (overrides all other options if set)",
    )
    parser.add_argument(
        "--server",
        default=None,
        help="Server URL (default: http://localhost:8080)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Update interval in seconds (default: 60)",
    )
    parser.add_argument(
        "--publish",
        help="List of interfaces to publish, comma-separated (e.g., tun0,eth0)",
    )
    parser.add_argument(
        "--subscribe",
        action="append",
        help="Hosts and interfaces to subscribe to, can be used multiple times",
    )
    parser.add_argument(
        "--mapping",
        action="append",
        help="Mapping from host and interface to hostname, can be used multiple times",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode without modifying the actual hosts file",
    )
    parser.add_argument(
        "--password",
        help="Password for server authentication",
    )
    parser.add_argument(
        "--excluded-interface-patterns",
        action="append",
        help="Patterns of interfaces to exclude from publishing and subscribing, can be used multiple times",
    )
    parser.add_argument(
        "--subscribe-config",
        action="store_true",
        help="Subscribe to server config and update local config file",
    )

    args = parser.parse_args()

    config = {}
    if args.config:
        with open(args.config, "r") as f:
            config = yaml.safe_load(f)

    # 优先级: 命令行 > yaml > 默认
    server = args.server or config.get("server", "http://localhost:8080")
    interval = args.interval if args.interval is not None else config.get("interval", 60)
    publish = args.publish or config.get("publish")
    subscribe = args.subscribe or config.get("subscribe")
    mapping = args.mapping or config.get("mapping")
    password = args.password or config.get("password")
    excluded_interface_patterns = args.excluded_interface_patterns or config.get("excluded_interface_patterns")
    subscribe_config = args.subscribe_config or config.get("subscribe_config", False)

    interfaces = publish.split(",") if isinstance(publish, str) else publish
    subscribe_hosts, subscribe_all = parse_subscribe_hosts(subscribe)
    interface_mapping = parse_interface_mapping(mapping)

    client = IPClient(
        server,
        interval,
        interfaces,
        subscribe_hosts,
        interface_mapping,
        args.config,
        args.dry_run,
        subscribe_all,
        password,
        excluded_interface_patterns,
        subscribe_config,
    )
    client.run()


if __name__ == "__main__":
    main()
