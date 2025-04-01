import requests
import subprocess
import time
import socket
import os
from datetime import datetime
import argparse


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


class IPClient:
    def __init__(
        self,
        server_url,
        update_interval=60,
        interfaces=None,
        subscribe_hosts=None,
        interface_mapping=None,
    ):
        self.server_url = server_url
        self.update_interval = update_interval
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

    def publish_ips(self):
        """Publish specified interface IP addresses to server"""
        interface_ips = parse_ifconfig(
            subprocess.check_output(["ifconfig"]).decode("utf-8"), self.interfaces
        )
        hostname = socket.gethostname()

        for interface, ip in interface_ips.items():
            if ip:  # Only publish interfaces with IP
                data = {"host": hostname, "ip": ip, "interface": interface}

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
                    print(
                        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error publishing IP for {interface}: {e}"
                    )
            else:
                print(
                    f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] No IP found for interface {interface}"
                )

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
            with open("/etc/hosts", "r") as f:
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
                        hostname_updated.add(hostname)

                new_hosts_lines.append(line)

            # Add new hostname entries
            for hostname, ip in host_ips.items():
                if hostname not in hostname_updated:
                    # Get mapped hostname (if any)
                    mapped_hostname = self.get_hostname_for_interface(hostname, None)
                    if mapped_hostname:
                        new_hosts_lines.append(f"{ip} {mapped_hostname}")
                    else:
                        new_hosts_lines.append(f"{ip} {hostname}")

            # Write updated hosts file
            with open("/etc/hosts", "w") as f:
                f.write("\n".join(new_hosts_lines) + "\n")

            print(
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Updated hosts file"
            )
        except Exception as e:
            print(
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error updating hosts file: {e}"
            )
            import traceback

            traceback.print_exc()

    def run(self):
        """Run the client"""
        print(f"Starting IP client with server: {self.server_url}")
        print(f"Publishing interfaces: {self.interfaces}")
        print(f"Subscribing to hosts: {self.subscribe_hosts}")
        print(f"Hostname mapping: {self.interface_mapping}")

        while True:
            try:
                # Publish local IP
                self.publish_ips()

                # Prepare subscription request data
                subscribe_data = {"hosts": list(self.subscribe_hosts.keys())}

                # Add interface data if specified
                interfaces_data = {}
                for host, interfaces in self.subscribe_hosts.items():
                    if interfaces is not None:
                        interfaces_data[host] = interfaces
                if interfaces_data:
                    subscribe_data["interfaces"] = interfaces_data

                # Get IPs from other machines
                response = requests.post(
                    f"{self.server_url}/subscribe", json=subscribe_data
                )
                if response.status_code == 200:
                    host_mappings = response.json()

                    # Build host_ips dictionary
                    host_ips = {}
                    for host, info in host_mappings.items():
                        for interface, interface_info in info["interfaces"].items():
                            hostname = self.get_hostname_for_interface(host, interface)
                            if hostname:
                                host_ips[hostname] = interface_info["ip"]

                    self.update_hosts(host_ips)
                else:
                    print(f"Failed to get host mappings: {response.text}")

                time.sleep(self.update_interval)
            except Exception as e:
                print(f"Error in main loop: {e}")
                import traceback

                traceback.print_exc()
                time.sleep(self.update_interval)


def parse_subscribe_hosts(subscribe_str):
    """Parse subscription hosts string"""
    subscribe_hosts = {}
    if subscribe_str:
        for item in subscribe_str.split(","):
            parts = item.split(":")
            host = parts[0]
            if len(parts) > 1:
                interfaces = parts[1].split("+")
                subscribe_hosts[host] = interfaces
            else:
                subscribe_hosts[host] = None
    return subscribe_hosts


def parse_interface_mapping(mapping_str):
    """Parse host and interface to hostname mapping string"""
    mapping = {}
    if mapping_str:
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
        "--server",
        default="http://localhost:8080",
        help="Server URL (default: http://localhost:8080)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Update interval in seconds (default: 60)",
    )
    parser.add_argument(
        "--publish",
        help="List of interfaces to publish, comma-separated (e.g., tun0,eth0)",
    )
    parser.add_argument(
        "--subscribe",
        help="Hosts and interfaces to subscribe to, format: host1:interface1+interface2,host2:interface3+interface4,host3",
    )
    parser.add_argument(
        "--mapping",
        help="Mapping from host and interface to hostname, format: host1:interface1=target1,host2:interface2=target2 (e.g., host1:tun0=vpn1,host2:eth0=lan1)",
    )

    args = parser.parse_args()

    interfaces = args.publish.split(",") if args.publish else None
    subscribe_hosts = parse_subscribe_hosts(args.subscribe)
    interface_mapping = parse_interface_mapping(args.mapping)

    client = IPClient(
        args.server, args.interval, interfaces, subscribe_hosts, interface_mapping
    )
    client.run()


if __name__ == "__main__":
    main()
