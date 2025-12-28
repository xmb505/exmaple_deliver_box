#!/bin/bash
# 停止总守护进程脚本

if [ ! -f /tmp/daemon_all.pid ]; then
    echo "PID文件不存在，守护进程可能未运行"
    exit 1
fi

PID=$(cat /tmp/daemon_all.pid)

if ps -p $PID > /dev/null 2>&1; then
    echo "正在停止总守护进程 (PID: $PID)..."
    kill $PID
    
    # 等待进程结束
    for i in {1..10}; do
        if ! ps -p $PID > /dev/null 2>&1; then
            echo "总守护进程已停止"
            rm /tmp/daemon_all.pid
            exit 0
        fi
        sleep 1
    done
    
    # 强制杀死
    echo "强制停止总守护进程..."
    kill -9 $PID
    rm /tmp/daemon_all.pid
    echo "总守护进程已强制停止"
else
    echo "进程 $PID 不存在"
    rm /tmp/daemon_all.pid
fi