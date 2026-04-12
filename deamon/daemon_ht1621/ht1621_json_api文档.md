# HT1621 JSON API 文档

## 概述

HT1621守护进程通过Unix Socket提供JSON接口，用于控制HT1621 LCD显示。守护进程将JSON命令转换为SPI信号，通过GPIO守护进程发送到HT1621芯片。

## Socket路径

- **Socket类型**: UDP
- **默认路径**: `/tmp/ht1621.sock`

## JSON命令格式（新格式 - 推荐）

### 显示数据命令

```json
{
    "device_id": 1,
    "command": "display_data",
    "display_data": "123456"
}
```

### 初始化命令

```json
{
    "device_id": 1,
    "command": "init"
}
```

### LCD显示控制命令

```json
{
    "device_id": 1,
    "command": "LCD_display_on"
}
```

```json
{
    "device_id": 1,
    "command": "LCD_display_off"
}
```

### 系统控制命令

```json
{
    "device_id": 1,
    "command": "LCD_sys_on"
}
```

```json
{
    "device_id": 1,
    "command": "LCD_sys_off"
}
```

**参数说明**:
- `device_id`: LCD设备ID (1-5, 根据配置文件映射)
- `command`: 命令类型
  - `"display_data"`: 显示数据，需配合 `display_data` 参数
  - `"init"`: 初始化HT1621
  - `"LCD_display_on"`: 打开LCD显示
  - `"LCD_display_off"`: 关闭LCD显示
  - `"LCD_sys_on"`: 使能HT1621系统
  - `"LCD_sys_off"`: 关闭HT1621系统
- `display_data`: 要显示的字符串 (最多6位，仅在 `command` 为 `"display_data"` 时需要)

## JSON命令格式（旧格式 - 兼容）

为了向后兼容，旧格式仍然支持：

### 显示数据命令

```json
{
    "device_id": 1,
    "display_data": "123456"
}
```

### 初始化命令

```json
{
    "device_id": 1,
    "display_data": "init"
}
```

**注意**: 旧格式中，当 `display_data` 为 `"init"` 时执行初始化，其他值执行显示操作。

## 使用示例

### 1. 初始化LCD

```bash
# 使用socket_json_sender.py工具
cd debug_utils
python3 socket_json_sender.py --socket-path /tmp/ht1621.sock --data '{"device_id": 1, "display_data": "init"}'
```

### 2. 显示数据

```bash
# 显示验证码
python3 socket_json_sender.py --socket-path /tmp/ht1621.sock --data '{"device_id": 1, "display_data": "640327"}'

# 显示学生侧信息
python3 socket_json_sender.py --socket-path /tmp/ht1621.sock --data '{"device_id": 2, "display_data": "123456"}'

# 清空显示
python3 socket_json_sender.py --socket-path /tmp/ht1621.sock --data '{"device_id": 1, "display_data": "      "}'
```

### 3. Python直接发送

```python
import socket
import json

# 创建UDP socket
sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

# 发送初始化命令
init_cmd = {
    "device_id": 1,
    "display_data": "init"
}
sock.sendto(json.dumps(init_cmd).encode('utf-8'), '/tmp/ht1621.sock')

# 发送显示命令
display_cmd = {
    "device_id": 1,
    "display_data": "123456"
}
sock.sendto(json.dumps(display_cmd).encode('utf-8'), '/tmp/ht1621.sock')

sock.close()
```

## 设备ID映射

设备ID映射在配置文件 `config/config.ini` 中定义：

```ini
[device_mapping]
# device_id = gpio_alias:spi_interface_id
device_1 = spi:1    # 外卖员侧LCD
device_2 = spi:2    # 学生侧LCD
device_3 = spi:3    # 预留
device_4 = spi:4    # 预留
device_5 = spi:5    # 预留
```

## 段码表

```ini
[font_data]
# 段码格式: dp-c-b-a-d-e-g-f (从高位到低位)
0 = 01111101    # 数字0
1 = 01100000    # 数字1
2 = 00111110    # 数字2
3 = 01111010    # 数字3
4 = 01100011    # 数字4
5 = 01011011    # 数字5
6 = 01011111    # 数字6
7 = 01110000    # 数字7
8 = 01111111    # 数字8
9 = 01111011    # 数字9
A = 01110111    # 字母A
b = 01001111    # 字母b
C = 00011101    # 字母C
c = 00001110    # 字母c
d = 01101110    # 字母d
E = 00011111    # 字母E
F = 00010111    # 字母F
H = 01100111    # 字母H
h = 01000111    # 字母h
L = 00001101    # 字母L
o = 01001110    # 字母o
P = 00110111    # 字母P
r = 00000110    # 字母r
U = 01101101    # 字母U
u = 01001100    # 字母u
- = 00000010    # 减号
space = 00000000 # 空格
```

## RAM地址映射

```ini
[font_data]
# RAM地址映射 (对应数码管的位0-位5)
ram_address_0 = 0   # 第1位 (最右边)
ram_address_1 = 2   # 第2位
ram_address_2 = 4   # 第3位
ram_address_3 = 6   # 第4位
ram_address_4 = 8   # 第5位
ram_address_5 = 10  # 第6位 (最左边)
```

## 初始化序列

初始化命令会发送以下HT1621命令序列：

```ini
[init_sequence]
init_0 = 10000000000    # SYSDIS: 关闭系统
init_1 = 10001010110    # BIAS: 1/3 Bias, 4 COM
init_2 = 10001100000    # RC256: 使用内部RC振荡器
init_3 = 1000000010     # SYSEN: 使能系统
init_4 = 1000000110     # LCDON: 打开显示输出
```

## 调试模式

启动守护进程时可以使用调试参数：

```bash
# 启用JSON输入调试
python3 daemon_ht1621.py --debug-in

# 启用完整调试
python3 daemon_ht1621.py --debug

# 启动时会自动初始化所有配置的设备
```

## 故障排除

### 1. LCD不显示
- 检查守护进程是否正常运行
- 检查 `/tmp/ht1621.sock` 文件是否存在
- 使用 `--debug-in` 参数查看命令是否正确接收
- 检查GPIO守护进程是否正常运行

### 2. 显示乱码
- 检查段码表配置是否正确
- 确认RAM地址映射是否正确

### 3. 初始化失败
- 确认设备ID在配置文件中存在
- 检查SPI引脚连接是否正确