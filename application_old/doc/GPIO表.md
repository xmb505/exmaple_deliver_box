# 智能外卖柜样机 - GPIO映射表

## 一、SPI设备映射表

| SPI编号 | 设备名称 | 用途 | 守护进程配置 |
|---------|----------|------|--------------|
| 1 | 外卖员侧LCD | 显示取件码、状态信息 | daemon_ht1621: device_1 |
| 2 | 学生侧LCD | 显示验证码输入、错误提示 | daemon_ht1621: device_2 |

**说明**:
- SPI接口通过daemon_gpio的bit-banging实现
- 每个SPI接口对应一个HT1621 LCD控制器
- LCD为6位8段数码管显示

**配置文件**: `deamon/daemon_ht1621/config/config.ini`

---

## 二、输入GPIO表（geter）

**设备**: GPIO3_geter (`/dev/USB2GPIO3`)
**模式**: 输入监听
**默认电平**: 1（未触发），0表示触发

| GPIO编号 | 信号名称 | 功能描述 | 电平定义 | 用途 |
|----------|----------|----------|----------|------|
| 1 | 红外传感器1 | 检测柜内是否有物品 | 1=无物品<br>0=有物品 | 物品检测 |
| 2 | 红外传感器2 | 检测柜内是否有物品（冗余） | 1=无物品<br>0=有物品 | 物品检测 |
| 3 | 学生侧内部按钮 | 紧急开门按钮 | 0=按下<br>1=抬起 | 系统初始化、紧急开门 |
| 4 | 外卖员侧外部按钮 | 存物按钮 | 0=按下<br>1=抬起 | 触发存物流程 |
| 5 | 外卖员侧门传感器 | 检测门开关状态 | 0=关闭<br>1=打开 | 门状态检测 |
| 6 | 学生侧门传感器 | 检测门开关状态 | 0=关闭<br>1=打开 | 门状态检测 |

**注意**:
- 红外传感器1和2为冗余配置，任一触发即判断为有物品
- 红外传感器需要2秒稳定时间（亚克力材料震动导致电平跳变）
- 门传感器用于检测门是否完全关闭

**配置文件**: `deamon/daemon_gpio/config/config.ini` → `[GPIO3_geter]`

---

## 三、输出GPIO表（seter）

**设备**: GPIO1_sender (`/dev/USB2GPIO1`)
**模式**: 输出控制
**默认电平**: 0（关闭），1表示开启

| GPIO编号 | 信号名称 | 功能描述 | 电平定义 | 特殊要求 |
|----------|----------|----------|----------|----------|
| 1 | 外卖侧LCD背光 | 控制外卖员侧LCD背光 | 0=关闭<br>1=开启 | 常开 |
| 2 | 学生侧LCD背光 | 控制学生侧LCD背光 | 0=关闭<br>1=开启 | 常开 |
| 3 | 柜内照明灯 | 柜内照明 | 0=关闭<br>1=开启 | 门开时开启 |
| 4 | 外卖侧门锁 | 控制外卖员侧门锁 | 0=关闭<br>1=开启 | **脉冲1秒** |
| 5 | 学生侧门锁 | 控制学生侧门锁 | 0=关闭<br>1=开启 | **脉冲1秒** |
| 6 | 嗡鸣器 | 提示音 | 0=触发<br>1=停止 | **低电平触发，预设为1** |

**重要说明**:

### 3.1 门锁控制（GPIO 4、5）

**约束**: 门锁通电时间**严格限制为1秒**，超过会烧坏门锁

**实现要求**:
```python
def open_door(door_gpio):
    """开门方法，确保门锁通电不超过1秒"""
    set_gpio(door_gpio, 1)  # 开门
    # 必须使用定时器或异步任务，1秒后自动断电
    Timer(1.0, lambda: set_gpio(door_gpio, 0)).start()
```

**注意事项**:
- 门锁控制必须封装为独立方法
- 严禁在门锁控制方法中执行其他耗时操作
- 门锁命令发送后立即启动定时器断电

---

### 3.2 嗡鸣器控制（GPIO 6）

**特性**: 低电平触发（0=响，1=停）

**初始化要求**:
```python
# 系统启动时必须将嗡鸣器预设为1（停止状态）
set_gpio(6, 1)
```

**使用模式**:
```python
def beep(duration=1.0):
    """单次提示音"""
    set_gpio(6, 0)  # 触发
    time.sleep(duration)
    set_gpio(6, 1)  # 停止

def flash_beep(count=5, duration=1.0):
    """闪烁提示"""
    for i in range(count):
        set_gpio(6, 0)
        time.sleep(duration)
        set_gpio(6, 1)
        time.sleep(0.5)
```

**配置文件**: `deamon/daemon_gpio/config/config.ini` → `[GPIO1_sender]`

---

## 四、硬件连接图

```
USB2GPIO1 (seter - 输出控制)
├── GPIO 1 → 外卖侧LCD背光
├── GPIO 2 → 学生侧LCD背光
├── GPIO 3 → 柜内照明灯
├── GPIO 4 → 外卖侧门锁 (脉冲1秒)
├── GPIO 5 → 学生侧门锁 (脉冲1秒)
└── GPIO 6 → 嗡鸣器 (低电平触发，预设为1)

USB2GPIO2 (spi - SPI通信)
├── SPI 1 → 外卖员侧HT1621 LCD
└── SPI 2 → 学生侧HT1621 LCD

USB2GPIO3 (geter - 输入监听)
├── GPIO 1 → 红外传感器1 (1=无物品, 0=有物品)
├── GPIO 2 → 红外传感器2 (1=无物品, 0=有物品)
├── GPIO 3 → 学生侧内部按钮 (0=按下, 1=抬起)
├── GPIO 4 → 外卖员侧外部按钮 (0=按下, 1=抬起)
├── GPIO 5 → 外卖员侧门传感器 (0=关闭, 1=打开)
└── GPIO 6 → 学生侧门传感器 (0=关闭, 1=打开)
```

---

## 五、通信协议

### 5.1 GPIO控制协议（seter）

**Socket**: `/tmp/gpio.sock` (UDP)

**单个GPIO控制**:
```json
{
    "alias": "sender",
    "mode": "set",
    "gpio": 4,
    "value": 1
}
```

**批量GPIO控制**:
```json
{
    "alias": "sender",
    "mode": "set",
    "gpios": [4, 5, 6],
    "values": [1, 0, 1]
}
```

### 5.2 GPIO状态监听协议（geter）

**Socket**: `/tmp/gpio_get.sock` (TCP)

**状态查询请求**:
```json
{
    "type": "query_status"
}
```

**GPIO状态变化事件**:
```json
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
                }
            ]
        }
    ]
}
```

### 5.3 HT1621显示协议

**Socket**: `/tmp/ht1621.sock` (UDP)

**显示数据**:
```json
{
    "device_id": 1,
    "display_data": "123456"
}
```

**初始化设备**:
```json
{
    "device_id": 1,
    "display_data": "init"
}
```

---

## 六、调试工具

### 6.1 GPIO状态监听

```bash
cd debug_utils
python3 gpio_read.py --socket_path /tmp/gpio_get.sock
```

**功能**:
- 实时监听GPIO状态变化
- 启动时自动获取初始状态
- 支持定期状态查询

### 6.2 GPIO控制测试

```bash
cd debug_utils
python3 socket_json_sender.py --socket-path /tmp/gpio.sock \
    --data '{"alias": "sender", "mode": "set", "gpio": 4, "value": 1}'
```

### 6.3 HT1621显示测试

```bash
cd deamon/daemon_ht1621
# 显示数字
python3 ht1621_test.py 123456

# 初始化显示
python3 ht1621_test.py init
```

---

## 七、注意事项

### 7.1 硬件安全

1. **门锁保护**: 严禁超过1秒通电，必须使用定时器自动断电
2. **嗡鸣器初始化**: 系统启动时必须将GPIO6预设为1（停止状态）
3. **红外稳定**: 检测到触发后等待2秒再进行状态判断

### 7.2 软件实现

1. **门锁方法封装**: 门锁控制必须封装为独立方法，确保1秒后自动断电
2. **红外去抖动**: 使用2秒稳定时间或去抖动算法
3. **状态同步**: GPIO状态变化通过事件驱动机制实时同步

### 7.3 测试验证

1. **门锁时序测试**: 验证门锁通电时间精确为1秒
2. **红外稳定测试**: 验证2秒稳定时间有效
3. **嗡鸣器测试**: 验证低电平触发和预设状态

---

## 八、版本历史

| 版本 | 日期 | 修改内容 |
|------|------|----------|
| v1.0 | 2025-12-28 | 初始版本，定义完整GPIO映射表和通信协议 |
| v1.1 | 2025-12-28 | 添加硬件连接图、调试工具说明和注意事项 |