现在client主动连接server，server广播给所有连接的client

# 监听GPIO状态变化的JSON格式说明

## 单个GPIO设备监听
- 支持单个GPIO设备的状态监听
- default_bit用于指定查询电平指令集：1使用3D指令（拉高GPIO后检测），0使用3E指令（拉低GPIO后检测）

{
    "type": "gpio_change",
    "id": 1,
    "timestamp": 1234567890.123456,
    "gpios": [
        {
            "alias": "geter",
            "default_bit": 1,
            "change_gpio": [
                {
                    "gpio": 1,
                    "bit": 0
                },
                {
                    "gpio": 2,
                    "bit": 0
                }
            ]
        }
    ]
}

## 多个GPIO设备监听
- 支持同时监听多个GPIO设备的状态变化
- 每个设备可以独立设置查询电平指令集

{
    "type": "gpio_change",
    "id": 2,
    "timestamp": 1234567890.123456,
    "gpios": [
        {
            "alias": "geter",
            "default_bit": 1,
            "change_gpio": [
                {
                    "gpio": 1,
                    "bit": 0
                },
                {
                    "gpio": 2,
                    "bit": 0
                }
            ]
        },
        {
            "alias": "sensor1",
            "default_bit": 0,
            "change_gpio": [
                {
                    "gpio": 1,
                    "bit": 1
                }
            ]
        },
        {
            "alias": "sensor2",
            "default_bit": 1,
            "change_gpio": [
                {
                    "gpio": 3,
                    "bit": 0
                }
            ]
        }
    ]
}

## 查询电平指令集说明
- default_bit: 1 - 使用3D指令集（拉高GPIO后检测）：系统将所有GPIO拉高，然后检测哪些GPIO被外部信号拉低
- default_bit: 0 - 使用3E指令集（拉低GPIO后检测）：系统将所有GPIO拉低，然后检测哪些GPIO被外部信号拉高
- 无论使用哪种指令集，系统都会报告所有状态变化（0到1和1到0的变化都会被报告）

## 消息类型说明

### 1. GPIO状态变化消息 (服务器发送)
- type: "gpio_change"
- id: 消息唯一ID，用于ACK确认
- timestamp: 消息发送时间戳
- (其余为GPIO变化数据)

### 2. 当前GPIO状态消息 (服务器发送，响应查询)
- type: "current_status"
- timestamp: 状态获取时间戳
- (其余为当前GPIO状态数据)

## 客户端到服务器的消息格式

### 1. ACK确认消息
当客户端收到带ID的GPIO变化消息时，需要发送ACK确认：
{
    "type": "ack",
    "id": 1
}

### 2. 状态查询请求
客户端主动查询当前GPIO状态的请求格式：
{
    "type": "query_status"
}

**注意**：发送此请求后，服务器会立即回复当前所有GPIO的状态信息。

## 服务器对查询请求的响应格式

当服务器收到状态查询请求后，会发送以下格式的响应：
{
    "type": "current_status",
    "timestamp": 1234567890.123456,
    "gpios": [
        {
            "alias": "geter",
            "default_bit": 0,
            "current_gpio_states": {
                "1": 0,
                "2": 1,
                "3": 0,
                "4": 1
            }
        }
    ]
}

**字段说明**：
- type: "current_status" - 表示这是当前GPIO状态响应
- timestamp: 服务器响应的时间戳
- gpios: 包含所有geter模式GPIO设备的状态
  - alias: GPIO设备的别名
  - default_bit: 该设备的查询电平指令集设置
  - current_gpio_states: 当前GPIO引脚的状态，键为GPIO编号，值为电平状态(0或1)

## 完整的查询交互流程

### 1. 客户端发送查询请求
```json
{
    "type": "query_status"
}
```

### 2. 服务器响应当前GPIO状态
```json
{
    "type": "current_status",
    "timestamp": 1703123456.789012,
    "gpios": [
        {
            "alias": "geter",
            "default_bit": 0,
            "current_gpio_states": {
                "1": 0,
                "2": 1,
                "3": 0
            }
        }
    ]
}
```

### 3. 开发上层应用的实现示例

在您的应用程序中，可以按以下步骤实现GPIO状态查询：

1. 连接到GPIO状态监听Socket (/tmp/gpio_get.sock)
2. 发送查询请求：`{"type": "query_status"}`
3. 接收服务器响应，解析GPIO状态
4. 保存当前GPIO状态到本地缓存
5. 继续监听后续的GPIO变化事件

## 实际应用中的使用场景

### 场景1：应用启动时获取初始状态
```python
# 连接Socket后立即查询当前GPIO状态
socket.send('{"type": "query_status"}'.encode())
# 接收并处理响应...
```

### 场景2：定期同步GPIO状态
```python
import time

while True:
    # 发送查询请求
    socket.send('{"type": "query_status"}'.encode())
    # 处理响应...
    time.sleep(30)  # 每30秒同步一次
```

### 场景3：在特定业务逻辑中查询
```python
def check_door_status():
    """检查门锁状态"""
    socket.send('{"type": "query_status"}'.encode())
    # 解析响应，获取门锁对应的GPIO状态
```

## 使用方法
- 客户端连接后会持续接收GPIO状态变化通知
- 客户端收到带ID的消息后应发送ACK确认
- 客户端可发送query_status请求获取当前GPIO状态

## 应对开机状态未知的策略
当系统刚启动时，由于没有GPIO状态变化事件发生，客户端无法知道当前GPIO的实际状态。
为此，客户端可以采用以下几种策略来获取当前状态：

### 1. 连接时立即查询
客户端在连接到服务器后立即发送一次状态查询请求，获取当前GPIO状态：
{
    "type": "query_status"
}

### 2. 定期查询
客户端可以设置定时任务，定期发送状态查询请求，确保始终了解当前GPIO状态。
例如，每30秒查询一次：
{
    "type": "query_status"
}

### 3. 使用增强版gpio_read.py工具
新版gpio_read.py工具支持--query-interval参数，可自动定期查询当前GPIO状态：
```bash
# 连接后立即查询一次，然后每30秒查询一次当前GPIO状态
./debug_utils/gpio_read.py --socket_path /tmp/gpio_get.sock --query-interval 30
```

### 4. 响应式查询
在某些业务逻辑需要时，客户端可以主动查询当前GPIO状态，例如在应用程序启动时或用户请求时。

## 客户端实现建议
建议在客户端程序中实现以下逻辑：
1. 连接服务器后立即发送一次query_status请求
2. 实现定时查询机制，确保状态信息不过时
3. 收到状态查询响应后，更新本地GPIO状态缓存
4. 对于实时性要求高的场景，可缩短查询间隔