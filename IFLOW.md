# 智能外卖柜样机项目

## 项目概述

这是一个基于MT7621路由器改造的智能外卖柜样机项目，运行在immortalwrt（openwrt分支）系统上。项目实现了双开门外卖柜的核心功能，包括物品存取、验证码生成、LCD显示和键盘输入等。

### 硬件组成
- MT7621路由器 + immortalwrt系统
- 3个USB2GPIO设备（2个3.3V，1个5V）
- 2个HT1621六位八字码LCD屏幕
- 2个继电器、按钮、嗡鸣器、门锁传感器等

### 业务流程
1. 外卖员按下按钮，放入物品，关门
2. 系统生成六位验证码并显示到LCD屏幕
3. 学生到内侧，通过外置USB键盘输入验证码
4. 验证码正确后开门，取物后系统重置为空闲状态

## 项目架构

### 系统架构图
```
应用层 (待实现)
    ↓
Unix Socket接口层
    ↓
守护进程层 (daemon_gpio, daemon_ht1621, daemon_keyboard)
    ↓
硬件抽象层 (USB2GPIO, SPI)
    ↓
硬件层 (HT1621 LCD, 继电器, 传感器)
```

### 核心组件

#### 1. daemon_gpio - GPIO控制守护进程
**位置**: `deamon/daemon_gpio/daemon_gpio.py`

**功能**:
- 将USB2GPIO设备抽象为Unix Socket接口
- 支持三种工作模式：seter（输出控制）、geter（输入监听）、spi（SPI通信）
- 实现GPIO状态缓存优化，避免重复设置相同状态
- 支持多路SPI通信，可独立配置时钟沿触发方式

**配置文件**: `deamon/daemon_gpio/config/config.ini`
- GPIO1_sender: 控制输出设备（继电器、门锁等）
- GPIO2_spi: SPI通信接口，支持5路独立SPI
- GPIO3_geter: 输入监听设备（按钮、传感器等）

#### 2. daemon_ht1621 - LCD显示守护进程
**位置**: `deamon/daemon_ht1621/daemon_ht1621.py`

**功能**:
- 提供HT1621 LCD的高级抽象接口
- 支持多设备映射（device_id 1-5对应5个SPI接口）
- 内置完整的段码表和初始化序列
- 支持数字、字母和特殊字符显示

#### 3. daemon_keyboard - 键盘输入守护进程
**位置**: `deamon/daemon_keyboard/`
**状态**: 待实现

#### 4. daemon_all - 总守护进程
**位置**: `deamon/daemon_all/`
**功能**: 负责启动和管理其他守护进程

## 构建和运行

### 环境要求
- Python 3.x
- pyserial库
- Linux系统（支持Unix Socket）
- immortalwrt/openwrt系统（推荐）

### 启动步骤

#### 1. 启动GPIO守护进程
```bash
cd deamon/daemon_gpio
# 生产模式
python3 daemon_gpio.py

# 模拟模式（无硬件测试）
python3 daemon_gpio.py --simulate

# 使用启动脚本
./start_daemon.sh
```

#### 2. 启动HT1621守护进程
```bash
cd deamon/daemon_ht1621
python3 daemon_ht1621.py
```

#### 3. 验证服务状态
```bash
# 检查Socket文件
ls -la /tmp/gpio.sock /tmp/ht1621.sock

# 检查进程
ps aux | grep daemon
```

### 测试工具

#### 1. 通用Socket发送工具
```bash
cd debug_utils
python3 socket_json_sender.py --socket-path /tmp/gpio.sock --data '{"alias": "sender", "mode": "set", "gpio": 1, "value": 1}'
```

#### 2. HT1621显示测试
```bash
cd deamon/daemon_ht1621
# 显示数字
python3 ht1621_test.py 123456

# 初始化显示
python3 ht1621_test.py init
```

#### 3. 自动化测试脚本
```bash
cd debug_utils
./HT1621UNIXSOCKET_test.sh
```

## 开发约定

### 代码规范
- 使用Python 3.x语法
- 遵循PEP 8代码风格
- 使用中文注释和文档字符串
- 采用模块化设计，每个守护进程独立运行

### 通信协议
- 所有进程间通信使用Unix Socket
- 数据格式统一为JSON
- 控制命令使用UDP Socket，状态监听使用TCP Socket

### GPIO控制协议
```json
// 单个GPIO控制
{
    "alias": "sender",
    "mode": "set",
    "gpio": 1,
    "value": 1
}

// 批量GPIO控制
{
    "alias": "sender", 
    "mode": "set",
    "gpios": [1, 2, 3],
    "values": [1, 0, 1]
}

// SPI数据发送
{
    "alias": "spi",
    "mode": "spi",
    "spi_num": 1,
    "spi_data_cs_collection": "down",
    "spi_data": "10000100"
}
```

### HT1621显示协议
```json
// 显示数据
{
    "device_id": 1,
    "display_data": "123456"
}

// 初始化设备
{
    "device_id": 1,
    "display_data": "init"
}
```

## 配置说明

### GPIO设备配置
**文件**: `deamon/daemon_gpio/config/config.ini`

```ini
[GPIO1_sender]
tty_path = /dev/ttyUSB0
baudrate = 115200
alias = sender
mode = seter

[GPIO2_spi]
tty_path = /dev/ttyUSB1
baudrate = 115200
alias = spi
mode = spi
lag_time = 1

# SPI引脚配置
clk_1 = 1
data_1 = 2
cs_1 = 3
```

### HT1621配置
**文件**: `deamon/daemon_ht1621/config/config.ini`

```ini
[device_mapping]
device_1 = spi:1
device_2 = spi:2

[font_data]
0 = 01111101
1 = 01100000
2 = 00111110

[init_sequence]
init_0 = 10000000000
init_1 = 10001010110
```

## 调试功能

### 模拟模式
```bash
# GPIO守护进程模拟模式
python3 daemon_gpio.py --simulate

# SPI调试模式
python3 daemon_gpio.py --debug-spi
```

### 日志查看
```bash
# 实时查看日志
tail -f gpio_daemon.log

# 查看错误信息
grep -i error gpio_daemon.log
```

## 技术细节

### USB2GPIO通信协议
基于BL-ENV-V1.3硬件模块：
- **3A指令**: 离散GPIO控制
- **3B指令**: 连续GPIO控制  
- **3F指令**: 单GPIO状态查询
- **5A指令**: PWM输出控制

### HT1621 LCD驱动
采用bit-banging方式实现SPI通信：
- **命令格式**: `[100][9-bit命令]`
- **数据格式**: `[101][6-bit地址][8-bit数据]`
- **初始化序列**: 系统配置→偏压设置→振荡器→使能→显示开启

### 性能优化
- GPIO状态缓存：避免重复设置相同状态
- SPI队列处理：确保SPI操作串行执行
- 电平切换优化：只在状态变化时设置GPIO

## 项目状态

### 已完成
- ✅ GPIO抽象层：完全实现
- ✅ HT1621显示层：完全实现  
- ✅ SPI通信：bit-banging实现
- ✅ 进程间通信：Unix Socket + JSON
- ✅ 配置管理：模块化配置文件
- ✅ 测试工具：完整的调试工具集

### 待实现
- ❌ 键盘输入层：daemon_keyboard守护进程
- ❌ 应用层：业务逻辑和用户界面
- ❌ 错误处理：异常恢复机制
- ❌ 日志系统：结构化日志记录
- ❌ 监控功能：系统状态监控

## 故障排除

### 常见问题

#### 1. Socket连接失败
```bash
# 检查Socket文件是否存在
ls -la /tmp/gpio.sock /tmp/ht1621.sock

# 重新启动守护进程
pkill -f daemon_gpio
pkill -f daemon_ht1621
```

#### 2. USB设备权限问题
```bash
# 添加用户到dialout组
sudo usermod -a -G dialout $USER

# 或修改设备权限
sudo chmod 666 /dev/ttyUSB*
```

#### 3. SPI通信错误
- 检查引脚配置是否正确
- 确认lag_time设置合适
- 使用--debug-spi参数查看详细日志

## 扩展开发

### 添加新的守护进程
1. 创建新的守护进程目录
2. 实现Unix Socket接口
3. 添加配置文件支持
4. 编写测试脚本
5. 更新daemon_all启动逻辑

### 添加新的硬件支持
1. 在daemon_gpio中添加新的设备配置
2. 实现对应的控制逻辑
3. 更新配置文件模板
4. 编写硬件抽象层接口

## 联系方式

如有问题或建议，请通过以下方式联系：
- 项目仓库：[Git URL]
- 技术文档：参考`技术细节/`目录下的文档
- 问题反馈：通过Git Issues提交