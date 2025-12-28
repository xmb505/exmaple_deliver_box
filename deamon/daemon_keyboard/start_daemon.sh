#!/bin/bash
# 键盘守护进程启动脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查是否已经运行
if [ -f "/tmp/keyboard.pid" ]; then
    PID=$(cat /tmp/keyboard.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "键盘守护进程已经在运行 (PID: $PID)"
        exit 1
    else
        # 进程不存在，清理旧的PID文件
        rm -f /tmp/keyboard.pid
    fi
fi

# 启动守护进程
echo "启动键盘守护进程..."
nohup python3 daemon_keyboard.py > keyboard_daemon.log 2>&1 &

# 保存PID
echo $! > /tmp/keyboard.pid

echo "键盘守护进程已启动 (PID: $!)"
echo "日志文件: $SCRIPT_DIR/keyboard_daemon.log"