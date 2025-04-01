from flask import Flask, request, jsonify
import time
import json
import os
from datetime import datetime
import threading
import shutil

app = Flask(__name__)

# 配置文件路径
curr_dir = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = "host_ip_data.json"
BACKUP_DIR = curr_dir
BACKUP_INTERVAL = 3600  # 1小时备份一次

# 存储 host:网卡信息 的字典
# 格式: {
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
    """确保备份目录存在"""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)


def load_data():
    """从文件加载数据"""
    global host_ip_map
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                host_ip_map = json.load(f)
            # 确保每个主机记录都有正确的结构
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
    """保存数据到文件"""
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(host_ip_map, f, indent=2)
        print(f"Saved {len(host_ip_map)} hosts to {DATA_FILE}")
    except Exception as e:
        print(f"Error saving data: {e}")


def create_backup():
    """创建数据备份"""
    ensure_backup_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"host_ip_data_{timestamp}.json")
    try:
        shutil.copy2(DATA_FILE, backup_file)
        print(f"Created backup: {backup_file}")
    except Exception as e:
        print(f"Error creating backup: {e}")


def backup_task():
    """定时备份任务"""
    while True:
        time.sleep(BACKUP_INTERVAL)
        create_backup()


@app.route("/publish", methods=["POST"])
def publish_ip():
    """接收客户端发布的 IP 地址"""
    data = request.get_json()
    # print(f"Received publish request: {data}")  # 添加请求数据日志
    
    if not data or "host" not in data or "ip" not in data or "interface" not in data:
        print(f"Invalid request data: {data}")  # 添加错误数据日志
        return jsonify({"error": "Missing host, ip, or interface"}), 400

    host = data["host"]
    ip = data["ip"]
    interface = data["interface"]
    timestamp = datetime.now().isoformat()

    # print(f"Processing publish request for {host} {interface}: {ip}")  # 添加处理日志

    # 初始化 host 数据结构（如果不存在）
    if host not in host_ip_map:
        # print(f"Creating new host entry for {host}")  # 添加新主机日志
        host_ip_map[host] = {
            "interfaces": {},
            "last_updated": timestamp
        }
    elif "interfaces" not in host_ip_map[host]:
        print(f"Adding interfaces dictionary for existing host {host}")  # 添加修复日志
        host_ip_map[host]["interfaces"] = {}

    # 更新网卡 IP 信息
    host_ip_map[host]["interfaces"][interface] = {
        "ip": ip,
        "last_updated": timestamp
    }
    host_ip_map[host]["last_updated"] = timestamp

    # 保存到文件
    save_data()

    print(f"Updated IP for host:{host} interface:{interface} ip:{ip}")
    return jsonify({"status": "success"})


@app.route("/subscribe", methods=["POST"])
def subscribe():
    """返回指定的 host:网卡信息 映射"""
    data = request.get_json()
    if not data or "hosts" not in data:
        return jsonify({"error": "Missing hosts parameter"}), 400

    # 过滤指定的主机和网卡
    filtered_data = {}
    for host in data["hosts"]:
        if host in host_ip_map:
            filtered_data[host] = {
                "interfaces": {},
                "last_updated": host_ip_map[host]["last_updated"]
            }
            
            # 如果指定了网卡，只返回指定的网卡信息
            if "interfaces" in data and host in data["interfaces"]:
                for interface in data["interfaces"][host]:
                    if interface in host_ip_map[host]["interfaces"]:
                        filtered_data[host]["interfaces"][interface] = host_ip_map[host]["interfaces"][interface]
            else:
                # 如果没有指定网卡，返回所有网卡信息
                filtered_data[host]["interfaces"] = host_ip_map[host]["interfaces"]

    return jsonify(filtered_data)


if __name__ == "__main__":
    # 加载现有数据
    load_data()

    # 启动备份线程
    backup_thread = threading.Thread(target=backup_task, daemon=True)
    backup_thread.start()

    # 启动服务器
    app.run(host="0.0.0.0", port=8080)
