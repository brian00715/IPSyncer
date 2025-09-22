# IPSyncer

用于自动同步多台机器的 IP和 `/etc/hosts`，避免因 DHCP或网络环境导致的 IP 混乱，只需记住 hostname即可轻松访问所有机器。

## 特性

- 自动发布指定网卡的 IP 到服务器
- 选择性订阅其他机器的 IP
- 自动更新本地 hosts 文件
- 支持hostname自定义映射

- [ ] 借助第三方网盘实现同步

## 安装

```bash
git clone https://github.com/brian00715/IPSyncer
cd IPSyncer
pip install -r requirements.txt
```

### Systemd 服务安装

根据对应的安装目录和自定义配置编辑 `.service`文件，然后

```bash
sudo ln -s <REPO DIR>/service/ipsyncer_<server/client>.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ipsyncer_<server/client>

```

## 使用方法

### 启动服务器

```python
python server.py --host 0.0.0.0 --port 8080 --backup-interval 7200
```

```shell
sudo systemctl start ipsyncer_server
```

### 启动客户端

#### 推荐方式：基于 YAML 配置文件

1. 编辑 `src/config.yaml`，填写你的发布、订阅和映射需求。例如：

```yaml
server: "http://xxx.com:10086"
interval: 3600
publish: ["wlp132s0", "enp131s0", "cscotun0"]
subscribe:
    - "simon-omen-ubuntu:tun0+wlp0s20f3"
    - "unitree-go2:wlan0+eth0"
mapping:
    - "simon-omen-ubuntu:tun0=simon-omen-nus-vpn"
```

2. 使用 systemd 启动（推荐）：

```bash
sudo systemctl start ipsyncer_client
```

或手动运行：

```bash
sudo python client.py --config config.yaml
```

> 命令行参数依然支持，且优先级高于 YAML 配置。例如：
>
> ```bash
> sudo python client.py --config config.yaml --interval 120
> ```

#### 兼容旧参数

仍可直接用命令行参数（不推荐）：

```bash
sudo python client.py --server http://localhost:8080 --publish tun0,en0 --subscribe host1:en0+eth0 --mapping host1:en0=lan1
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
4. 使用 systemd 服务时，确保服务目录权限正确

## 许可证

MIT License
