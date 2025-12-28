# 智能外卖柜应用层

## 概述

这是智能外卖柜样机的应用层程序，负责实现完整的业务逻辑。

## 目录结构

```
application/
├── main.py                 # 主程序入口
├── test.py                 # 测试脚本
├── start.sh                # 启动脚本
├── config/                 # 配置文件
│   ├── __init__.py
│   └── config_loader.py   # 配置加载器
├── log_system/             # 日志系统
│   ├── __init__.py
│   └── logger_setup.py    # 日志设置
├── communication/          # 通信模块
│   ├── __init__.py
│   └── socket_client.py   # Socket客户端
├── pickup_code/            # 验证码模块
│   ├── __init__.py
│   ├── code_generator.py  # 验证码生成器
│   └── code_validator.py  # 验证码验证器
├── hardware/               # 硬件控制
│   ├── __init__.py
│   ├── gpio_controller.py # GPIO控制器
│   ├── lcd_controller.py  # LCD控制器
│   ├── buzzer_controller.py # 嗡鸣器控制器
│   └── door_controller.py # 门锁控制器
├── input/                  # 输入处理
│   ├── __init__.py
│   └── keyboard_handler.py # 键盘处理器
└── state_machine/          # 状态机
    ├── __init__.py
    └── state_machine.py   # 状态机实现
```

## 前置要求

1. **守护进程运行**: 确保以下守护进程已启动：
   - `daemon_gpio` (GPIO控制)
   - `daemon_ht1621` (LCD显示)
   - `daemon_keyboard` (键盘输入)

2. **Python 3.x**: 需要Python 3.6或更高版本

3. **Socket文件**: 确保以下Socket文件存在：
   - `/tmp/gpio.sock`
   - `/tmp/gpio_get.sock`
   - `/tmp/ht1621.sock`
   - `/tmp/keyboard_get.sock`

## 启动步骤

### 1. 启动守护进程

```bash
# 启动GPIO守护进程
cd /home/xmb505/智能外卖柜样机/deamon/daemon_gpio
python3 daemon_gpio.py

# 启动HT1621守护进程
cd /home/xmb505/智能外卖柜样机/deamon/daemon_ht1621
python3 daemon_ht1621.py

# 启动键盘守护进程
cd /home/xmb505/智能外卖柜样机/deamon/daemon_keyboard
python3 daemon_keyboard.py
```

### 2. 启动应用层

```bash
cd /home/xmb505/智能外卖柜样机/application
./start.sh
```

或直接运行：

```bash
python3 main.py
```

## 测试

运行测试脚本验证基础功能：

```bash
cd /home/xmb505/智能外卖柜样机/application
python3 test.py
```

测试包括：
- ✓ 配置加载
- ✓ 日志系统
- ✓ 验证码生成器

## 业务流程

### 系统启动流程

1. **BOOT**: 启动初始化
2. **WAITING_INIT**: 等待初始化按钮长按5秒
3. **INITIALIZING**: 初始化（播放提示音）
4. **CHECKING**: 检查柜内物品

### 正常运行流程

#### 存物流程（外卖员）
1. 系统处于IDLE状态
2. 外卖员按下外部按钮
3. 打开外卖员门
4. 外卖员放入物品，关门
5. 检测到物品，生成6位验证码
6. 在外卖员LCD显示验证码

#### 取物流程（学生）
1. 系统处于OCCUPIED状态
2. 学生通过键盘输入验证码
3. 验证正确后打开学生门
4. 学生取物，关门
5. 检测柜内状态
   - 有物品：嗡鸣器提示，重新开门
   - 无物品：进入IDLE状态

## 配置文件

配置文件位于 `config/config.ini`，包含以下主要配置：

- **daemon_config**: 守护进程Socket路径
- **state_machine**: 状态机配置
- **door_control**: 门锁控制配置（1秒限制）
- **ir_sensor**: 红外传感器配置（2秒稳定时间）
- **buzzer**: 嗡鸣器配置
- **lcd**: LCD显示配置
- **pickup_code**: 验证码配置
- **keyboard**: 键盘输入配置
- **logging**: 日志配置

## 状态定义

| 状态 | 说明 |
|------|------|
| BOOT | 启动初始化 |
| WAITING_INIT | 等待初始化按钮 |
| INITIALIZING | 初始化中 |
| CHECKING | 检查柜内物品 |
| CLEARING | 清理柜内物品 |
| IDLE | 空闲状态 |
| OCCUPIED | 占用状态 |
| PICKING | 取物中 |

## 错误码

| 错误码 | 说明 |
|--------|------|
| Err001 | 格式错误 |
| Err002 | 验证码不存在 |
| Err003 | 验证码已过期 |
| Err004 | 验证码已使用 |
| Err005 | 验证码重复使用 |
| Err007 | 输入超时 |
| Err008 | 门锁故障 |
| Err009 | 红外传感器异常 |
| Err099 | 系统错误 |

## 日志

日志文件位置：
- 默认: `/var/log/delivery_box.log`
- 如无权限: `./delivery_box.log`

日志级别可通过配置文件调整。

## 注意事项

1. **门锁安全**: 门锁通电时间严格限制为1秒，超过会烧坏门锁
2. **嗡鸣器初始化**: 系统启动时必须将GPIO6预设为1（停止状态）
3. **红外稳定**: 检测到触发后等待2秒再进行状态判断
4. **验证码安全**: 使用加密安全的随机数生成器，防重放攻击

## 故障排除

### Socket连接失败

检查守护进程是否启动：

```bash
ps aux | grep daemon
```

检查Socket文件是否存在：

```bash
ls -la /tmp/*.sock
```

### 配置文件错误

检查配置文件路径和格式：

```bash
python3 -c "from config.config_loader import ConfigLoader; c = ConfigLoader(); c.load()"
```

### 测试失败

运行测试脚本查看详细错误：

```bash
python3 test.py
```

## 开发者

- 作者: xmb505
- 日期: 2025-12-28
- 版本: v1.0