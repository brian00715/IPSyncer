# IPSyncer

用于自动同步多台机器的 IP，避免因 DHCP或网络环境导致的 IP 混乱，只需记住 hostname即可轻松访问所有机器。

## 特点

- 自动发布指定网卡的 IP 到服务器
- 选择性订阅其他机器的 IP
- 自动更新本地 hosts 文件
- 支持hostname自定义映射

## 安装

```bash
git clone https://github.com/brian00715/IPSyncer
cd IPSyncer
pip install -r requirements.txt
```

### Systemd 服务安装

根据对应的安装目录和自定义配置编辑`.service`文件，然后
```bash
sudo cp ipsyncer_<server/client>.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ipsyncer_<server/client>

```


## 使用方法

### 启动服务器


```python
python server.py --host 0.0.0.0 --port 8080
```

```shell
sudo systemctl start ipsyncer_server
```


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
5. 使用 systemd 服务时，确保服务目录权限正确

## 许可证

MIT License
