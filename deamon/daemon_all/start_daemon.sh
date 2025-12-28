#!/bin/bash
# 启动总守护进程脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查是否已经在运行
if [ -f /tmp/daemon_all.pid ]; then
    PID=$(cat /tmp/daemon_all.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "总守护进程已在运行 (PID: $PID)"
        exit 1
    else
        rm /tmp/daemon_all.pid
    fi
fi

# 启动守护进程
nohup python3 ./daemon_all.py > /dev/null 2>&1 &
echo $! > /tmp/daemon_all.pid

echo "总守护进程已启动 (PID: $(cat /tmp/daemon_all.pid))"