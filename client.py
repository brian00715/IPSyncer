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
        # 要发布的网卡列表，如果为 None 则发布所有网卡
        self.interfaces = interfaces
        # 要订阅的主机和网卡信息
        # 格式: {
        #   "hostname": ["interface1", "interface2"],  # 指定网卡
        #   "hostname2": None  # 订阅所有网卡
        # }
        self.subscribe_hosts = subscribe_hosts or {}
        # 主机和网卡到主机名的映射
        # 格式: {
        #   "hostname:interface": "target_hostname"
        # }
        self.interface_mapping = interface_mapping or {}

    def publish_ips(self):
        """发布本机的指定网卡 IP 地址到服务器"""
        interface_ips = parse_ifconfig(
            subprocess.check_output(["ifconfig"]).decode("utf-8"), self.interfaces
        )
        hostname = socket.gethostname()

        # print(f"Publishing IPs for host {hostname}:")
        for interface, ip in interface_ips.items():
            if ip:  # 只发布有 IP 的网卡
                data = {"host": hostname, "ip": ip, "interface": interface}

                try:
                    # print(f"Sending publish request for {interface}: {ip}")
                    response = requests.post(f"{self.server_url}/publish", json=data)
                    if response.status_code == 200:
                        print(f"Published IP {ip} for {hostname} {interface}")
                    else:
                        print(f"Failed to publish IP for {interface}: {response.text}")
                except Exception as e:
                    print(f"Error publishing IP for {interface}: {e}")
            else:
                print(f"No IP found for interface {interface}")

    def get_hostname_for_interface(self, host, interface):
        """根据主机名和网卡名称获取对应的主机名"""
        # 检查是否有特定的映射规则
        mapping_key = f"{host}:{interface}"
        if mapping_key in self.interface_mapping:
            return self.interface_mapping[mapping_key]
        # 如果没有映射规则，使用默认格式
        return f"{host}-{interface}"

    def update_hosts(self, host_ips):
        """更新 hosts 文件"""
        try:
            # 读取现有的 hosts 文件
            with open('/etc/hosts', 'r') as f:
                hosts_lines = f.readlines()
            
            # 创建新的 hosts 内容
            new_hosts_lines = []
            hostname_updated = set()  # 用于跟踪已更新的主机名
            
            # 处理现有行
            for line in hosts_lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    new_hosts_lines.append(line)
                    continue
                
                parts = line.split()
                if len(parts) < 2:
                    new_hosts_lines.append(line)
                    continue
                
                ip = parts[0]
                hostnames = parts[1:]
                
                # 检查是否有需要更新的主机名
                updated = False
                for i, hostname in enumerate(hostnames):
                    if hostname in host_ips:
                        # 更新 IP 地址
                        new_ip = host_ips[hostname]
                        if new_ip != ip:
                            # 替换 IP 地址，保持其他部分不变
                            parts[0] = new_ip
                            line = ' '.join(parts)
                            updated = True
                        hostname_updated.add(hostname)
                
                new_hosts_lines.append(line)
            
            # 添加新的主机名条目
            for hostname, ip in host_ips.items():
                if hostname not in hostname_updated:
                    # 获取映射的主机名（如果有）
                    mapped_hostname = self.get_hostname_for_interface(hostname, None)
                    if mapped_hostname:
                        new_hosts_lines.append(f"{ip} {mapped_hostname}")
                    else:
                        new_hosts_lines.append(f"{ip} {hostname}")
            
            # 写入更新后的 hosts 文件
            with open('/etc/hosts', 'w') as f:
                f.write('\n'.join(new_hosts_lines) + '\n')
            
            print("Updated hosts file")
        except Exception as e:
            print(f"Error updating hosts file: {e}")
            import traceback
            traceback.print_exc()

    def run(self):
        """运行客户端"""
        print(f"Starting IP client with server: {self.server_url}")
        print(f"Publishing interfaces: {self.interfaces}")
        print(f"Subscribing to hosts: {self.subscribe_hosts}")
        print(f"Hostname mapping: {self.interface_mapping}")
        
        while True:
            try:
                # 发布本机 IP
                self.publish_ips()
                
                # 准备订阅请求数据
                subscribe_data = {"hosts": list(self.subscribe_hosts.keys())}
                
                # 如果有指定网卡，添加到请求数据中
                interfaces_data = {}
                for host, interfaces in self.subscribe_hosts.items():
                    if interfaces is not None:
                        interfaces_data[host] = interfaces
                if interfaces_data:
                    subscribe_data["interfaces"] = interfaces_data
                
                # 获取其他机器的 IP
                response = requests.post(
                    f"{self.server_url}/subscribe", json=subscribe_data
                )
                if response.status_code == 200:
                    host_mappings = response.json()
                    
                    # 构建 host_ips 字典
                    host_ips = {}
                    for host, info in host_mappings.items():
                        for interface, interface_info in info["interfaces"].items():
                            hostname = self.get_hostname_for_interface(host, interface)
                            if hostname:
                                host_ips[hostname] = interface_info["ip"]
                    
                    # 更新 hosts 文件
                    self.update_hosts(host_ips)
                else:
                    print(f"Failed to get host mappings: {response.text}")
                
                # 等待下一次更新
                time.sleep(self.update_interval)
            except Exception as e:
                print(f"Error in main loop: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(self.update_interval)


def parse_subscribe_hosts(subscribe_str):
    """解析订阅主机字符串"""
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
    """解析主机和网卡到主机名的映射字符串"""
    mapping = {}
    if mapping_str:
        for item in mapping_str.split(","):
            # 格式: host:interface=target_hostname
            parts = item.split("=")
            if len(parts) == 2:
                host_interface, target_hostname = parts
                mapping[host_interface] = target_hostname
    return mapping


def main():
    parser = argparse.ArgumentParser(description="IP 自动发布和订阅客户端")
    parser.add_argument(
        "--server",
        default="http://localhost:8080",
        help="服务器地址 (默认: http://localhost:8080)",
    )
    parser.add_argument(
        "--interval", type=int, default=60, help="更新间隔（秒） (默认: 60)"
    )
    parser.add_argument(
        "--publish", help="要发布的网卡列表，用逗号分隔 (例如: tun0,eth0)"
    )
    parser.add_argument(
        "--subscribe",
        help="要订阅的主机和网卡，格式: host1:interface1+interface2,host2:interface3+interface4,host3",
    )
    parser.add_argument(
        "--mapping",
        help="主机和网卡到主机名的映射，格式: host1:interface1=target1,host2:interface2=target2 (例如: host1:tun0=vpn1,host2:eth0=lan1)",
    )

    args = parser.parse_args()

    # 解析要发布的网卡列表
    interfaces = args.publish.split(",") if args.publish else None

    # 解析要订阅的主机和网卡
    subscribe_hosts = parse_subscribe_hosts(args.subscribe)

    # 解析主机和网卡到主机名的映射
    interface_mapping = parse_interface_mapping(args.mapping)

    client = IPClient(
        args.server, args.interval, interfaces, subscribe_hosts, interface_mapping
    )
    client.run()


if __name__ == "__main__":
    main()
