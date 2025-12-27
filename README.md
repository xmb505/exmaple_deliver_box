# 智能外卖柜样机项目

基于 MT7621 路由器改造的双开门智能外卖柜系统，运行在 immortalwrt 系统上。

## 项目简介

本项目实现了一个完整的智能外卖柜系统，包括硬件控制、LCD显示、键盘输入等功能。系统采用模块化设计，通过 Unix Socket 进行进程间通信，支持事件驱动的 GPIO 状态监听，针对 MIPS 低性能平台进行了优化。

## 功能特性

- ✅ **GPIO 抽象层**：支持输出控制、输入监听、SPI 通信三种模式
- ✅ **HT1621 LCD 显示**：支持多设备映射，内置完整段码表
- ✅ **键盘输入**：自动检测键盘设备，监听按键事件
- ✅ **事件驱动机制**：使用 select 实现，避免轮询开销
- ✅ **性能优化**：针对 MIPS 平台优化，减少 CPU 占用
- ✅ **初始状态查询**：启动时自动获取 GPIO 初始状态

## 系统架构

```
应用层 (开发中)
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

### 1. 启动守护进程

```bash
# 启动 GPIO 守护进程
cd deamon/daemon_gpio
python3 daemon_gpio.py --simulate  # 模拟模式
# 或
python3 daemon_gpio.py             # 生产模式

# 启动 HT1621 守护进程
cd deamon/daemon_ht1621
python3 daemon_ht1621.py

# 启动键盘守护进程
cd deamon/daemon_keyboard
python3 daemon_keyboard.py
```

### 2. 测试工具

```bash
# 监听 GPIO 状态变化
cd debug_utils
python3 gpio_read.py --socket_path /tmp/gpio_get.sock

# 监听键盘输入
python3 keyboard_read.py

# 测试 HT1621 显示
cd deamon/daemon_ht1621
python3 ht1621_test.py 123456
```

## 项目结构

```
智能外卖柜样机/
├── deamon/              # 守护进程
│   ├── daemon_gpio/     # GPIO 控制守护进程
│   ├── daemon_ht1621/   # LCD 显示守护进程
│   ├── daemon_keyboard/ # 键盘输入守护进程
│   └── daemon_all/      # 总守护进程（待实现）
├── debug_utils/         # 调试工具
├── application/         # 应用层（开发中）
├── 技术细节/            # 技术文档
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

## 开发文档

详细的技术文档和开发指南请参考：

- [IFLOW.md](./IFLOW.md) - 完整项目文档
- [技术细节/](./技术细节/) - 硬件技术文档

## 项目状态

- ✅ GPIO 抽象层
- ✅ HT1621 显示层
- ✅ 键盘输入层
- ✅ SPI 通信
- ✅ 进程间通信
- ✅ 测试工具
- 🔄 应用层（开发中）

## 版本历史

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