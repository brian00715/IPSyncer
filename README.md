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

- server

  ```bash
  git clone https://github.com/brian00715/IPSyncer ./IPSyncer
  cd IPSyncer/service
  cp ipsyncer_server_example.service ipsyncer_server.service

  vim ipsyncer_server.service # adapt to your needs

  sudo ln -s $(realpath ipsyncer_server.service) /etc/systemd/system/

  sudo systemctl daemon-reload
  sudo systemctl enable ipsyncer_server.service
  sudo systemctl start ipsyncer_server.service
  ```
- client

  ```bash
  git clone https://github.com/brian00715/IPSyncer ./IPSyncer
  cd IPSyncer/service
  cp ipsyncer_client_example.service ipsyncer_client.service

  vim ipsyncer_client.service # adapt to your needs

  sudo ln -s $(realpath ipsyncer_client.service) /etc/systemd/system/
  cd ../src
  cp config-example.yaml config.yaml

  vim config.yaml # adapt to your needs

  sudo systemctl daemon-reload
  sudo systemctl enable ipsyncer_client.service
  sudo systemctl start ipsyncer_client.service
  ```

## Usage

### Server

Run (example):

```python
python server.py --host 0.0.0.0 --port 8080 --backup-interval 7200 --password your_password
```

Systemd example:

```bash
sudo systemctl start ipsyncer_server
```

Server command-line parameters (short form):

- `--host` (string) - Host/IP to bind the server to. Default: `0.0.0.0`.
- `--port` (int) - Port to listen on. Default: `8080`.
- `--backup-interval` (int) - Seconds between automatic backups of server state. Default: `7200`.
- `--password` (string) - Password required for client authentication. Optional but recommended for remote deployments.

Equivalent YAML fields (when using a YAML-driven server startup wrapper):

- `host: "0.0.0.0"`
- `port: 8080`
- `backup_interval: 7200`
- `password: "your_password"`

### Client

Recommended: use the YAML configuration file at `src/config.yaml` or pass parameters on the command line. Example YAML (copy `config-example.yaml` to `config.yaml` and edit):

```yaml
server: "http://xxx.com:8000"
interval: 3600
password: "your_password" # Optional, for authentication
publish: ["wlp132s0", "enp131s0", "cscotun0"] # Leave empty to publish all interfaces
subscribe: # Use 'all' or leave empty to subscribe to all hosts
  - "simon-omen-ubuntu:tun0+wlp0s20f3"
  - "unitree-go2:wlan0+eth0"
mapping:
  - "simon-omen-ubuntu:tun0=simon-omen-nus-vpn"
```

Client command-line examples:

Start with systemd (recommended):

```bash
sudo systemctl start ipsyncer_client
```

Run manually:

```bash
sudo python client.py --config config.yaml
```

Client command-line parameters (short form):

- `--config` (path) - Path to YAML configuration file. Default: `config.yaml` in the current directory.
- `--server` (string) - Server URL, e.g. `http://localhost:8080`. Overrides `server` in YAML.
- `--interval` (int) - Poll/publish interval in seconds. Overrides `interval` in YAML.
- `--password` (string) - Password for authentication. Overrides `password` in YAML.
- `--publish` (comma-separated list) - Interfaces to publish. Overrides `publish` in YAML.
- `--subscribe` (comma-separated list or the literal `all`) - Hosts and interfaces to subscribe to. Overrides `subscribe` in YAML.
- `--mapping` (comma-separated list) - Custom hostname mapping rules. Overrides `mapping` in YAML.
- `--dry-run` (flag) - If present, the client will not modify the local hosts file; it will only log changes.

Note on precedence: command-line parameters take precedence over YAML configuration values. Example:

```bash
sudo python client.py --config config.yaml --interval 120 --dry-run --password your_password
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
