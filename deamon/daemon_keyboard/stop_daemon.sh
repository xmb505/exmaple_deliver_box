#!/bin/bash
# 键盘守护进程停止脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查PID文件是否存在
if [ ! -f "/tmp/keyboard.pid" ]; then
    echo "键盘守护进程未运行"
    exit 0
fi

# 读取PID
PID=$(cat /tmp/keyboard.pid)

# 检查进程是否存在
if ! ps -p $PID > /dev/null 2>&1; then
    echo "键盘守护进程未运行 (清理PID文件)"
    rm -f /tmp/keyboard.pid
    exit 0
fi

# 停止进程
echo "停止键盘守护进程 (PID: $PID)..."
kill $PID

# 等待进程结束
for i in {1..10}; do
    if ! ps -p $PID > /dev/null 2>&1; then
        echo "键盘守护进程已停止"
        rm -f /tmp/keyboard.pid
        exit 0
    fi
    sleep 1
done

# 如果进程仍在运行，强制终止
echo "强制停止键盘守护进程..."
kill -9 $PID
rm -f /tmp/keyboard.pid
echo "键盘守护进程已强制停止"