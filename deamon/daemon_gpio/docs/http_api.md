# GPIO Daemon HTTP 接口文档

## 概述

GPIO 守护进程支持通过 HTTP 接口远程控制 GPIO，JSON 格式与 Unix Socket 完全一致，便于主从机架构部署。

## 基础配置

编辑 `deamon/daemon_gpio/config/config.ini`：

```ini
[daemon_config]
# HTTP 控制接口端口（0 = 禁用）
http_port = 8080
# WebSocket 状态推送端口（0 = 禁用）
ws_port = 8081
```

## HTTP API

### 1. GPIO 控制

**POST** `/gpio`

发送 GPIO 控制命令。

**请求体**（JSON）：
```json
{
  "alias": "sender",
  "mode": "set",
  "gpio": 1,
  "value": 1
}
```

**响应**：
```json
{"success": true, "alias": "sender", "gpio": 1, "value": 1}
```

**批量设置**：
```json
{
  "alias": "sender",
  "mode": "set",
  "gpios": [1, 2, 3],
  "values": [1, 0, 1]
}
```

### 2. SPI 通信

**POST** `/gpio`

```json
{
  "alias": "spi",
  "mode": "spi",
  "spi_num": 1,
  "spi_data": "10000100",
  "spi_data_cs_collection": "down"
}
```

**多路 SPI**：
```json
{
  "alias": "spi",
  "mode": "spi_multi",
  "spis": [
    {"spi_num": 1, "spi_data": "10000100"},
    {"spi_num": 2, "spi_data": "11110000"}
  ]
}
```

### 3. 查询状态

**GET** `/status`

查询所有 geter 模式 GPIO 的当前状态。

**响应**：
```json
{
  "type": "current_status",
  "timestamp": 1234567890.123,
  "gpios": [
    {
      "alias": "geter",
      "default_bit": 0,
      "current_gpio_states": {"1": 0, "2": 1, "3": 0}
    }
  ]
}
```

## WebSocket API

连接地址：`ws://<host>:<ws_port>/`

当 GPIO 状态发生变化时，服务器主动推送：

```json
{
  "type": "gpio_change",
  "id": 123,
  "timestamp": 1234567890.123,
  "gpios": [
    {
      "alias": "geter",
      "default_bit": 0,
      "change_gpio": [
        {"gpio": 1, "bit": 0}
      ]
    }
  ]
}
```

## 使用示例

### curl

```bash
# 设置单个 GPIO
curl -X POST http://localhost:8080/gpio \
  -H "Content-Type: application/json" \
  -d '{"alias": "sender", "mode": "set", "gpio": 1, "value": 1}'

# 批量设置
curl -X POST http://localhost:8080/gpio \
  -H "Content-Type: application/json" \
  -d '{"alias": "sender", "mode": "set", "gpios": [1, 2], "values": [1, 0]}'

# 查询状态
curl http://localhost:8080/status
```

### Python

```python
import requests

# 控制 GPIO
requests.post('http://localhost:8080/gpio', json={
    'alias': 'sender',
    'mode': 'set',
    'gpio': 1,
    'value': 1
})

# 查询状态
status = requests.get('http://localhost:8080/status').json()
```

### JavaScript + WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8081');

ws.onopen = () => {
    console.log('WebSocket 已连接');
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'gpio_change') {
        console.log('GPIO 变化:', data.gpios);
    }
};
```

## 错误响应

| HTTP 状态码 | 说明 |
|-------------|------|
| 200 | 成功 |
| 400 | JSON 格式错误 |
| 500 | 服务器内部错误 |

**错误格式**：
```json
{"error": "Unknown alias: invalid", "available": ["sender", "spi", "geter"]}
```

## 主从机架构示例

**主机（直接控制）**：
```bash
python3 daemon_gpio.py --simulate
```

**从机（HTTP 控制主机）**：
```python
import requests

# 通过 HTTP 控制主机 GPIO
requests.post('http://192.168.1.100:8080/gpio', json={
    'alias': 'sender',
    'mode': 'set',
    'gpio': 5,
    'value': 1
})
```

## 依赖

```bash
pip install websocket-client
```
