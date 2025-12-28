# 智能外卖柜样机项目

基于 MT7621 路由器改造的双开门智能外卖柜系统，运行在 immortalwrt 系统上。

## 项目简介

本项目实现了一个完整的智能外卖柜系统，包括硬件控制、LCD显示、键盘输入、验证码生成等功能。系统采用模块化设计，通过 Unix Socket 进行进程间通信，支持事件驱动的 GPIO 状态监听，针对 MIPS 低性能平台进行了优化。

## 功能特性

### 核心功能
- ✅ **GPIO 抽象层**：支持输出控制、输入监听、SPI 通信三种模式
- ✅ **HT1621 LCD 显示**：支持多设备映射，内置完整段码表
- ✅ **键盘输入**：自动检测键盘设备，支持主键盘和小键盘
- ✅ **验证码系统**：6位随机验证码生成和验证
- ✅ **状态机管理**：完整的业务流程状态管理
- ✅ **LCD 实时显示**：学生侧 LCD 实时显示输入的验证码
- ✅ **背光控制**：自动控制 LCD 背光开关
- ✅ **取物逻辑完善**：等待门稳定、物品检测、嗡鸣器提示

### 技术特性
- ✅ **事件驱动机制**：使用 select 实现，避免轮询开销
- ✅ **性能优化**：针对 MIPS 平台优化，减少 CPU 占用
- ✅ **初始状态查询**：启动时自动获取 GPIO 初始状态
- ✅ **总守护进程**：统一管理所有服务的启动和监控
- ✅ **Debug 模式**：支持输出应用层日志到控制台

## 系统架构

```
应用层
    ↓
Unix Socket 接口层
    ↓
守护进程层 (daemon_gpio, daemon_ht1621, daemon_keyboard)
    ↓
硬件抽象层 (USB2GPIO, SPI, Input Events)
    ↓
硬件层 (HT1621 LCD, 继电器, 传感器, 键盘)
```

## 硬件要求

- MT7621 路由器
- immortalwrt/openwrt 系统
- 3 个 USB2GPIO 设备（2 个 3.3V，1 个 5V）
- 2 个 HT1621 六位八字码 LCD 屏幕
- 2 个继电器、按钮、嗡鸣器、门锁传感器
- USB 键盘

## 软件要求

- Python 3.x
- pyserial 库
- Linux 系统（支持 Unix Socket 和 Input Events）

## 快速开始

### 方式一：使用总守护进程（推荐）

```bash
cd deamon/daemon_all

# 正常模式启动
./start_daemon.sh

# Debug 模式启动（输出 application 日志到控制台）
./daemon_all.py --debug-application

# 停止所有服务
./stop_daemon.sh
```

### 方式二：手动启动各个守护进程

```bash
# 1. 启动 GPIO 守护进程
cd deamon/daemon_gpio
python3 daemon_gpio.py

# 2. 启动 HT1621 守护进程
cd deamon/daemon_ht1621
python3 daemon_ht1621.py

# 3. 启动键盘守护进程
cd deamon/daemon_keyboard
python3 daemon_keyboard.py

# 4. 启动应用层
cd application
python3 main.py
```

## 业务流程

### 系统启动流程
1. **BOOT**: 启动初始化
2. **WAITING_INIT**: 等待初始化按钮长按 5 秒
3. **INITIALIZING**: 初始化（播放提示音）
4. **CHECKING**: 检查柜内物品

### 正常运行流程

#### 存物流程（外卖员）
1. 系统处于 IDLE 状态
2. 外卖员按下外部按钮
3. 打开外卖员门
4. 外卖员放入物品，关门
5. 检测到物品，生成 6 位验证码
6. 在外卖员 LCD 显示验证码

#### 取物流程（学生）
1. 系统处于 OCCUPIED 状态
2. 学生通过键盘输入验证码
3. 验证正确后打开学生门
4. 学生取物，关门
5. 检测柜内状态
   - 有物品：嗡鸣器提示，重新开门
   - 无物品：进入 IDLE 状态

## 测试工具

### GPIO 状态监听

```bash
cd debug_utils

# 基本监听（启动时会自动获取初始 GPIO 状态）
python3 gpio_read.py --socket_path /tmp/gpio_get.sock

# 定期查询当前状态（每 30 秒）
python3 gpio_read.py --socket_path /tmp/gpio_get.sock --query-interval 30
```

### 键盘输入监听

```bash
cd debug_utils
python3 keyboard_read.py --socket_path /tmp/keyboard_get.sock
```

### HT1621 显示测试

```bash
cd deamon/daemon_ht1621

# 显示数字
python3 ht1621_test.py 123456

# 初始化显示
python3 ht1621_test.py init
```

### 通用 Socket 发送工具

```bash
cd debug_utils
python3 socket_json_sender.py --socket-path /tmp/gpio.sock --data '{"alias": "sender", "mode": "set", "gpio": 1, "value": 1}'
```

## 项目结构

```
智能外卖柜样机/
├── deamon/              # 守护进程
│   ├── daemon_gpio/     # GPIO 控制守护进程
│   ├── daemon_ht1621/   # LCD 显示守护进程
│   ├── daemon_keyboard/ # 键盘输入守护进程
│   └── daemon_all/      # 总守护进程
├── application/         # 应用层
│   ├── communication/   # Socket 通信模块
│   ├── hardware/        # 硬件控制器
│   ├── input/           # 输入处理
│   ├── pickup_code/     # 验证码模块
│   ├── state_machine/   # 状态机实现
│   └── log_system/      # 日志系统
├── debug_utils/         # 调试工具
├── 技术细节/            # 技术文档
├── IFLOW.md             # 完整项目文档
└── README.md            # 本文件
```

## 配置说明

### GPIO 配置

编辑 `deamon/daemon_gpio/config/config.ini`：

```ini
[GPIO1_sender]
tty_path = /dev/USB2GPIO1
mode = seter

[GPIO2_spi]
tty_path = /dev/USB2GPIO2
mode = spi

[GPIO3_geter]
tty_path = /dev/USB2GPIO3
mode = geter
default_bit = 1
```

### HT1621 配置

编辑 `deamon/daemon_ht1621/config/config.ini`：

```ini
[device_mapping]
device_1 = spi:1
device_2 = spi:2
```

### 总守护进程配置

编辑 `deamon/daemon_all/config/config.ini`：

```ini
[gpio_service]
work_dir = ../daemon_gpio
work_command = ./daemon_gpio.py

[service_ht1621]
service_name = daemon_ht1621
work_dir = ../daemon_ht1621
work_command = ./daemon_ht1621.py

[service_keyboard]
service_name = daemon_keyboard
work_dir = ../daemon_keyboard
work_command = ./daemon_keyboard.py

[service_application]
service_name = application
work_dir = ../../application
work_command = python3 main.py
```

## 通信协议

### GPIO 控制

```json
{
    "alias": "sender",
    "mode": "set",
    "gpio": 1,
    "value": 1
}
```

### GPIO 状态查询

```json
{
    "type": "query_status"
}
```

### HT1621 显示

```json
{
    "device_id": 1,
    "display_data": "123456"
}
```

### 键盘事件

```json
{
    "type": "key_event",
    "current_keys": {
        "a": true,
        "ENTER": false
    },
    "event_type": "press",
    "key": "a",
    "key_code": 30
}
```

## 性能优化

- 使用 `select` 系统调用监听串口数据，避免轮询
- GPIO 状态缓存，避免重复设置相同状态
- SPI 队列处理，确保操作串行执行
- 动态计算等待时间，减少不必要的 CPU 占用

## 故障排除

### Socket 连接失败

```bash
ls -la /tmp/gpio.sock /tmp/ht1621.sock /tmp/keyboard.sock
```

### USB 设备权限问题

```bash
sudo usermod -a -G dialout $USER
# 或
sudo chmod 666 /dev/ttyUSB*
```

### GPIO 状态监听无响应

- 确认已发送持续上报指令（3D 或 3E）
- 检查 default_bit 配置是否正确
- 使用 gpio_read.py 工具测试连接

### Application 启动失败

```bash
# 检查守护进程是否启动
ps aux | grep daemon

# 检查 Socket 文件是否存在
ls -la /tmp/*.sock

# 查看 application 日志
tail -f /var/log/delivery_box.log
```

### 学生侧 LCD 不显示数字

- 确认守护进程已启动
- 检查键盘输入是否正常
- 查看 application 日志，确认 LCD 初始化是否成功

## 开发文档

详细的技术文档和开发指南请参考：

- [IFLOW.md](./IFLOW.md) - 完整项目文档
- [技术细节/](./技术细节/) - 硬件技术文档
- [application/README.md](./application/README.md) - 应用层文档

## 项目状态

- ✅ GPIO 抽象层
- ✅ HT1621 显示层
- ✅ 键盘输入层
- ✅ SPI 通信
- ✅ 进程间通信
- ✅ 测试工具
- ✅ 应用层
- ✅ 总守护进程
- ✅ 小键盘支持
- ✅ LCD 实时显示
- ✅ 取物逻辑完善

## 版本历史

- **v1.3** - 完成应用层开发，实现总守护进程，支持小键盘，完善取物逻辑
- **v1.2** - 新增应用层目录，gpio_read.py 初始状态查询
- **v1.1** - 新增键盘输入守护进程，事件驱动机制
- **v1.0** - 初始版本

## 许可证

本项目采用 [LICENSE](./LICENSE) 许可证。

## 联系方式

- 项目仓库：git@github.com:xmb505/exmaple_deliver_box.git
- 问题反馈：通过 Git Issues 提交

---

**注意**：本项目为样机项目，仅供学习和参考使用。