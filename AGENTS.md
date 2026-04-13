# AGENTS.md

This file provides guidance to Qoder (qoder.com) when working with code in this repository.

## Project Overview

This is a smart delivery locker system based on MT7621 router running immortalwrt (OpenWrt fork). The system implements a dual-door delivery locker with GPIO control, LCD display, keyboard input, and verification code generation.

## System Architecture

```
Application Layer (application/)
    ↓ Unix Socket (JSON)
Daemon Layer (deamon/)
    - daemon_gpio: GPIO abstraction (seter/geter/spi modes)
    - daemon_ht1621: HT1621 LCD display driver
    - daemon_keyboard: Keyboard input events
    - daemon_all: Master daemon managing all services
    ↓
Hardware Abstraction (USB2GPIO, SPI, Input Events)
    ↓
Hardware (HT1621 LCD, relays, sensors, keyboard)
```

## Key Technologies

- **USB2GPIO**: BL-ENV-V1.3 modules via USB-to-serial (/dev/USB2GPIO*)
- **SPI**: Bit-banging implementation via GPIO (shared clk/data, 14 CS lines)
- **HT1621**: 6-digit 8-segment LCD driver with custom segment mapping
- **Communication**: Unix Domain Sockets (SOCK_DGRAM) with JSON protocol
- **Event-driven**: Uses `select` for I/O multiplexing, no polling loops

## Common Commands

### Start/Stop System

```bash
# Start all services (recommended)
cd deamon/daemon_all
./start_daemon.sh

# Stop all services
cd deamon/daemon_all
./stop_daemon.sh

# Debug mode (shows application logs in console)
cd deamon/daemon_all
./daemon_all.py --debug-application
```

### Manual Service Start

```bash
# GPIO daemon
cd deamon/daemon_gpio
python3 daemon_gpio.py

# HT1621 LCD daemon
cd deamon/daemon_ht1621
python3 daemon_ht1621.py

# Keyboard daemon
cd deamon/daemon_keyboard
python3 daemon_keyboard.py

# Application layer
cd application
python3 main.py
```

### Debug Tools

```bash
cd debug_utils

# Monitor GPIO state changes
python3 gpio_read.py --socket_path /tmp/gpio_get.sock

# Query GPIO status periodically
python3 gpio_read.py --socket_path /tmp/gpio_get.sock --query-interval 30

# Monitor keyboard input
python3 keyboard_read.py --socket_path /tmp/keyboard_get.sock

# Send raw JSON to socket
python3 socket_json_sender.py --socket-path /tmp/gpio.sock --data '{"alias": "sender", "mode": "set", "gpio": 1, "value": 1}'

# HT1621 display test
cd deamon/daemon_ht1621
python3 ht1621_test.py 123456
python3 ht1621_test.py init
```

### Check System Status

```bash
# Check socket files
ls -la /tmp/gpio.sock /tmp/gpio_get.sock /tmp/ht1621.sock /tmp/keyboard_get.sock

# Check running processes
ps aux | grep -E "daemon|application"

# Check USB devices
ls -la /dev/USB2GPIO* /dev/ttyUSB*

# View logs
tail -f /var/log/delivery_box.log
tail -f /var/log/daemon_all.log
```

## Configuration Files

### GPIO Configuration
**File**: `deamon/daemon_gpio/config/config.ini`

Key sections:
- `[GPIO1_sender]`: Output control (/dev/USB2GPIO1, mode=seter)
- `[GPIO2_spi]`: SPI interface (/dev/USB2GPIO2, mode=spi, 14 CS lines)
- `[GPIO3_geter]`: Input listener (/dev/USB2GPIO3, mode=geter, default_bit=0/1)

### HT1621 Configuration
**File**: `deamon/daemon_ht1621/config/config.ini`

- `device_mapping`: Maps device_id to SPI interface (device_1 = spi:1)
- `font_data`: 7-segment encoding (format: dp-c-b-a-d-e-g-f)
- `init_sequence`: HT1621 power-on initialization commands

### Master Daemon Configuration
**File**: `deamon/daemon_all/config/config.ini`

- `listen_gpio_alias`: GPIO alias to monitor for initialization trigger
- `listen_gpio_num`: GPIO pin number for init button
- `listen_ok_timeout`: Seconds to hold button for initialization

## Communication Protocols

### GPIO Control
```json
{"alias": "sender", "mode": "set", "gpio": 1, "value": 1}
{"alias": "sender", "mode": "set", "gpios": [1,2,3], "values": [1,0,1]}
{"alias": "spi", "mode": "spi", "spi_num": 1, "spi_data_cs_collection": "down", "spi_data": "10000100"}
```

### GPIO Status Events
```json
{"type": "gpio_change", "id": 1, "timestamp": 1234567890.123, "gpios": [{"alias": "geter", "change_gpio": [{"gpio": 1, "bit": 0}]}]}
{"type": "query_status"}  // Request current status
```

### HT1621 Display
```json
{"device_id": 1, "display_data": "123456"}
{"device_id": 1, "display_data": "init"}
```

### Keyboard Events
```json
{"type": "key_event", "event_type": "press", "key": "a", "key_code": 30, "current_keys": {"a": true}}
```

## USB2GPIO Commands

- `3A`: Discrete GPIO control
- `3B`: Continuous GPIO control
- `3D`: Query all GPIO status (pull-up mode, continuous output)
- `3E`: Query all GPIO status (pull-down mode, continuous output)
- `3F`: Single GPIO status query
- `5A`: PWM output control

## Important Notes

- **USB Device Mapping**: USB2GPIO devices are identified by insertion order. The geter (input) device should be inserted last to ensure correct mapping.
- **SPI CS Lines**: GPIO2_spi supports 14 independent chip select lines (GPIO 3-16)
- **Event-driven**: All daemons use `select()` for I/O - no polling loops
- **State Caching**: GPIO daemon caches states to avoid redundant writes
- **Segment Mapping**: HT1621 uses custom segment order (dp-c-b-a-d-e-g-f)
- **Init Trigger**: System requires holding GPIO16 for 10 seconds to initialize
