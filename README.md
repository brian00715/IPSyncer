# IPSyncer

用于自动同步多台机器的 IP，避免因 DHCP或网络环境导致的 IP 混乱，只需记住 hostname即可轻松访问所有机器。

## 功能特点

- 自动发布指定网卡的 IP 地址到服务器
- 支持订阅其他机器的 IP 地址
- 自动更新本地 hosts 文件
- 支持网卡到主机名的自定义映射
- 支持调试模式
- 支持 macOS 和 Linux 系统
- 支持 systemd 服务管理

## 安装

### 手动安装

1. 克隆仓库：
```bash
git clone https://github.com/brian00715/IPSync
cd IPSync
```

2. 创建并激活虚拟环境：
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate  # Windows
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

### Systemd 服务安装（Linux）

1. 将服务文件复制到 systemd 目录：
```bash
sudo cp ip-server.service /etc/systemd/system/
```

2. 创建服务目录并复制文件：
```bash
sudo mkdir -p /opt/ip-server
sudo cp -r * /opt/ip-server/
sudo chown -R $USER:$USER /opt/ip-server
```

3. 重新加载 systemd 配置：
```bash
sudo systemctl daemon-reload
```

4. 启用并启动服务：
```bash
sudo systemctl enable ip-server
sudo systemctl start ip-server
```

5. 检查服务状态：
```bash
sudo systemctl status ip-server
```

6. 查看服务日志：
```bash
sudo journalctl -u ip-server -f
```

## 使用方法

### 启动服务器

#### 手动启动
```bash
python server.py
```

#### 使用 Systemd（Linux）
```bash
# 启动服务
sudo systemctl start ip-server

# 停止服务
sudo systemctl stop ip-server

# 重启服务
sudo systemctl restart ip-server

# 查看状态
sudo systemctl status ip-server

# 查看日志
sudo journalctl -u ip-server -f
```

服务器将在 http://localhost:8080 上运行。

### 启动客户端

客户端支持以下参数：

- `--server`: 服务器地址（默认：http://localhost:8080）
- `--interval`: 更新间隔（秒）（默认：60）
- `--publish`: 要发布的网卡列表，用逗号分隔
- `--subscribe`: 要订阅的主机和网卡
- `--mapping`: 主机和网卡到主机名的映射

#### 示例

1. 发布所有网卡的 IP 地址：

```bash
python client.py
```

2. 发布指定网卡的 IP 地址：

```bash
python client.py --publish tun0,en0
```

3. 订阅其他机器的 IP 地址：

```bash
python client.py --subscribe host1:en0,host2:tun0
```

4. 使用自定义主机名映射：

```bash
python client.py --mapping host1:en0=lan1,host2:tun0=vpn1
```

5. 完整示例：

```bash
python client.py \
    --server http://localhost:8080 \
    --interval 30 \
    --publish tun0,en0 \
    --subscribe host1:en0,host2:tun0 \
    --mapping host1:en0=lan1,host2:tun0=vpn1
```

## 数据格式

### 发布请求

```json
{
    "host": "hostname",
    "ip": "192.168.1.100",
    "interface": "en0"
}
```

### 订阅请求

```json
{
    "hosts": ["host1", "host2"],
    "interfaces": {
        "host1": ["en0"],
        "host2": ["tun0"]
    }
}
```

### 订阅响应

```json
{
    "host1": {
        "interfaces": {
            "en0": {
                "ip": "192.168.1.100",
                "last_updated": "2024-03-21T10:00:00"
            }
        }
    },
    "host2": {
        "interfaces": {
            "tun0": {
                "ip": "10.0.0.100",
                "last_updated": "2024-03-21T10:00:00"
            }
        }
    }
}
```

## 注意事项

1. 客户端需要 root 权限来修改 hosts 文件
2. 确保服务器和客户端之间的网络连接正常
3. 建议使用虚拟环境来隔离依赖
4. 调试模式需要安装 debugpy 包
5. 使用 systemd 服务时，确保服务目录权限正确
6. 服务日志可以通过 journalctl 查看

## 许可证

MIT License
