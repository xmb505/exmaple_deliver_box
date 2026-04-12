#!/bin/bash
# daemon_gpio启动脚本

DAEMON_DIR="/home/xmb505/智能外卖柜样机/deamon/daemon_gpio"
DAEMON_FILE="$DAEMON_DIR/daemon_gpio.py"
CONFIG_FILE="$DAEMON_DIR/config/config.ini"

# 检查配置文件是否存在
if [ ! -f "$CONFIG_FILE" ]; then
    echo "错误: 配置文件不存在 $CONFIG_FILE"
    exit 1
fi

# 检查是否已经有守护进程在运行
if [ -S "/tmp/gpio.sock" ] || [ -S "/tmp/gpio_get.sock" ]; then
    echo "警告: GPIO守护进程socket文件已存在，可能已有实例在运行"
    read -p "是否继续启动? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "启动GPIO守护进程..."

# 启动守护进程（使用模拟模式）
python3 "$DAEMON_FILE" --simulate &
DAEMON_PID=$!

echo "GPIO守护进程已启动，PID: $DAEMON_PID"

# 将PID写入文件以便后续管理
echo $DAEMON_PID > "$DAEMON_DIR/daemon_gpio.pid"

echo "守护进程已启动并正在后台运行"
echo "控制Socket: /tmp/gpio.sock"
echo "状态Socket: /tmp/gpio_get.sock"