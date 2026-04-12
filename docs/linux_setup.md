# Zapret2 on Linux — Setup Guide

## Overview

Zapret2 now supports Linux via `nfqws2` (NFQUEUE-based DPI bypass) instead of `winws2.exe` (WinDivert-based).

## Prerequisites

### Required packages

```bash
# Debian/Ubuntu
sudo apt install python3 python3-pip iptables netfilter-persistent

# Fedora
sudo dnf install python3 python3-pip iptables

# Arch Linux
sudo pacman -S python python-pip iptables
```

### Python dependencies

```bash
pip3 install PyQt6 qfluentwidgets qtawesome psutil
```

### nfqws2 binary

Download the Linux version of nfqws from [bol-van/zapret](https://github.com/bol-van/zapret):

```bash
# Download and extract nfqws2
wget https://github.com/bol-van/zapret/releases/latest/download/nfqws-linux-amd64.tar.gz
tar -xzf nfqws-linux-amd64.tar.gz

# Copy to Zapret2 bin folder
cp nfqws2 /path/to/zapret2/bin/
chmod +x /path/to/zapret2/bin/nfqws2
```

## Running Zapret2 on Linux

### 1. Privilege escalation

Zapret2 requires root privileges to:
- Manage iptables rules
- Run nfqws2 (needs CAP_NET_ADMIN)

On first launch, the app will prompt for root via `pkexec` (PolicyKit).

### 2. Start the application

```bash
cd /path/to/zapret2
python3 src/main.py
```

### 3. System tray

On Linux, Zapret2 uses `QSystemTrayIcon` which integrates with:
- **GNOME**: Requires `AppIndicator` extension
- **KDE Plasma**: Native support
- **XFCE**: Native support

If tray icon doesn't appear, install the appropriate system tray extension for your desktop environment.

## How it works

### Windows vs Linux architecture

| Component | Windows | Linux |
|-----------|---------|-------|
| DPI bypass binary | `winws2.exe` | `nfqws2` |
| Packet capture | WinDivert driver | NFQUEUE (netfilter) |
| Traffic redirect | Automatic (WinDivert filter) | iptables mangle rules |
| Config storage | Windows Registry | `~/.config/zapret2/registry_config.json` |
| Single instance | CreateMutex | fcntl file lock |
| Privilege escalation | UAC (ShellExecuteW "runas") | pkexec (PolicyKit) |
| System tray | Win32 Shell_NotifyIcon | QSystemTrayIcon (Qt) |
| Process kill | WinAPI (OpenProcess/TerminateProcess) | os.kill / pkill |

### iptables flow

1. Zapret2 parses the preset file for `--filter-tcp-port` and `--filter-udp-port` directives
2. Sets up iptables mangle rules to redirect matching traffic to NFQUEUE (queue-num=200)
3. Launches nfqws2 which reads from NFQUEUE and applies DPI bypass strategies
4. On shutdown, removes all iptables rules

Example iptables rules created:
```bash
iptables -t mangle -I OUTPUT -p tcp --dport 443 -j NFQUEUE --queue-num 200 --queue-bypass
iptables -t mangle -I OUTPUT -p tcp --dport 80 -j NFQUEUE --queue-num 200 --queue-bypass
ip6tables -t mangle -I OUTPUT -p tcp --dport 443 -j NFQUEUE --queue-num 200 --queue-bypass
ip6tables -t mangle -I OUTPUT -p tcp --dport 80 -j NFQUEUE --queue-num 200 --queue-bypass
```

### Preset compatibility

Preset files (`.txt`) are **fully compatible** between Windows and Linux versions. The same strategy definitions work on both platforms.

## Troubleshooting

### nfqws2 fails to start

```bash
# Check if iptables rules were created
sudo iptables -t mangle -L -n -v

# Check nfqws2 permissions
ls -l /path/to/zapret2/bin/nfqws2
# Should be executable: chmod +x nfqws2

# Test nfqws2 manually
sudo /path/to/zapret2/bin/nfqws2 --queue-num 200
```

### iptables permission denied

Zapret2 must run as root. Use `pkexec` or run with `sudo`:

```bash
pkexec python3 src/main.py
# or
sudo python3 src/main.py
```

### System tray icon missing

Install AppIndicator support:

```bash
# GNOME
sudo apt install gnome-shell-extension-appindicator

# KDE (usually works out of the box)
sudo dnf install libappindicator-gtk3

# XFCE
sudo apt install xfce4-indicator-plugin
```

### Cleanup stale iptables rules

If Zapret2 crashes and leaves rules behind:

```bash
# Flush mangle table
sudo iptables -t mangle -F
sudo ip6tables -t mangle -F
```

## NixOS support

For NixOS, add to your `configuration.nix`:

```nix
environment.systemPackages = with pkgs; [
  iptables
  python3
  python3Packages.pyqt6
];

# Allow nfqws to use NFQUEUE
networking.firewall.extraCommands = ''
  iptables -t mangle -N ZAPRET 2>/dev/null || true
  iptables -t mangle -A OUTPUT -j ZAPRET
'';
```
