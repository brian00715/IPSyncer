# IPSyncer

A tool for automatically synchronizing LAN device IP addresses across multiple machines in a local network cluster. Each device maintains awareness of other devices' internal IP addresses, facilitating convenient management of LAN cluster devices. Simply remember the hostname to easily access any machine in your network.

## Features

- Automatically publish IP addresses of specified network interfaces to the server
- Selectively subscribe to other machines' IPs, or subscribe to all hosts
- Automatically update local hosts file
- Support custom hostname mapping
- Auto-add new host mode: automatically update subscription list when new devices join
- Support password authentication to protect server-client communication
- Support dry-run mode for testing without modifying hosts file

## Installation

```bash
git clone https://github.com/brian00715/IPSyncer
cd IPSyncer
pip install -r requirements.txt
```

### Systemd Service Installation

Edit the `.service` files according to your installation directory and custom configuration, then:

```bash
sudo ln -s <REPO DIR>/service/ipsyncer_<server/client>.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ipsyncer_<server/client>
```

## Usage

### Start Server

```python
python server.py --host 0.0.0.0 --port 8080 --backup-interval 7200 --password your_password
```

```bash
sudo systemctl start ipsyncer_server
```

### Start Client

#### Recommended: YAML Configuration File

1. Edit `src/config.yaml` and fill in your publish, subscribe, and mapping requirements. For example:

```yaml
server: "http://xxx.com:10086"
interval: 3600
password: "your_password"  # Optional, for authentication
publish: ["wlp132s0", "enp131s0", "cscotun0"]  # Leave empty to publish all interfaces
subscribe:  # Use 'all' or leave empty to subscribe to all hosts
    - "simon-omen-ubuntu:tun0+wlp0s20f3"
    - "unitree-go2:wlan0+eth0"
mapping:
    - "simon-omen-ubuntu:tun0=simon-omen-nus-vpn"
```

2. Start with systemd (recommended):

```bash
sudo systemctl start ipsyncer_client
```

Or run manually:

```bash
sudo python client.py --config config.yaml
```

> Command line parameters still take precedence over YAML configuration. For example:
>
> ```bash
> sudo python client.py --config config.yaml --interval 120 --dry-run --password your_password
> ```

#### Legacy Parameters (Not Recommended)

You can still use command line parameters directly:

```bash
sudo python client.py --server http://localhost:8080 --publish tun0,en0 --subscribe host1:en0+eth0 --mapping host1:en0=lan1 --password your_password --dry-run
```

## Data Formats

### Authentication Request

```json
{
    "password": "your_password"
}
```

### Authentication Response

```json
{
    "token": "uuid-token-string"
}
```

### Client Authentication Request

```json
{
    "password": "your_password",
    "host": "hostname"
}
```

### Authentication Response

```json
{
    "token": "generated_token"
}
```

### Publish Request

```json
{
    "host": "hostname",
    "ip": "192.168.1.100",
    "interface": "en0",
    "token": "your_token"
}
```

### Subscribe Request

```json
{
    "hosts": ["host1", "host2"],
    "interfaces": {
        "host1": ["en0"],
        "host2": ["tun0"]
    },
    "token": "your_token"
}
```

### Subscribe Response

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
    },
    "new_device_joined": true,
    "all_hosts": ["host1", "host2", "new_host"]
}
```

## Testing

The project includes a test script `tests/simulate_new_device.py` for simulating new devices joining the network, triggering the client's automatic subscription update feature.

### Usage

```bash
python tests/simulate_new_device.py --server http://localhost:8080 --host new-device --ip 192.168.1.100 --interface eth0
```

### Parameters

- `--server`: Server URL (default: http://localhost:8080)
- `--host`: Device hostname (default: new-device-test)
- `--ip`: Device IP address (default: 192.168.1.100)
- `--interface`: Network interface (default: eth0)

## Notes

1. The client requires root privileges to modify the hosts file
2. Ensure network connectivity between server and clients is normal
3. It is recommended to use a virtual environment to isolate dependencies
4. When using systemd services, ensure service directory permissions are correct

## License

MIT License

---

[中文版 README](README_zh.md)
