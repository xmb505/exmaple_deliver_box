#!/bin/bash
# daemon_gpio停止脚本

DAEMON_DIR="/home/xmb505/智能外卖柜样机/deamon/daemon_gpio"
PID_FILE="$DAEMON_DIR/daemon_gpio.pid"

# 尝试从PID文件获取进程ID
if [ -f "$PID_FILE" ]; then
    DAEMON_PID=$(cat "$PID_FILE")
    
    if [ ! -z "$DAEMON_PID" ] && ps -p "$DAEMON_PID" > /dev/null; then
        echo "正在停止GPIO守护进程 (PID: $DAEMON_PID)..."
        kill "$DAEMON_PID"
        
        # 等待进程结束
        sleep 2
        
        # 检查进程是否仍在运行
        if ps -p "$DAEMON_PID" > /dev/null; then
            echo "进程仍在运行，强制终止..."
            kill -9 "$DAEMON_PID"
        fi
        
        # 删除PID文件
        rm -f "$PID_FILE"
        echo "GPIO守护进程已停止"
    else
        echo "PID文件中记录的进程不存在"
    fi
else
    echo "未找到PID文件，尝试查找运行中的daemon_gpio进程..."
    
    # 查找运行中的daemon_gpio进程
    DAEMON_PIDS=$(ps aux | grep "[d]aemon_gpio.py" | awk '{print $2}')
    
    if [ ! -z "$DAEMON_PIDS" ]; then
        echo "找到以下daemon_gpio进程:"
        ps aux | grep "[d]aemon_gpio.py"
        
        for pid in $DAEMON_PIDS; do
            echo "正在停止PID $pid..."
            kill "$pid"
            sleep 1
            
            # 如果进程仍在运行，强制终止
            if ps -p "$pid" > /dev/null; then
                kill -9 "$pid"
            fi
        done
        
        echo "已尝试停止所有daemon_gpio进程"
    else
        echo "未找到运行中的daemon_gpio进程"
    fi
fi

# 清理socket文件
if [ -S "/tmp/gpio.sock" ]; then
    rm -f "/tmp/gpio.sock"
    echo "已清理控制Socket文件"
fi

if [ -S "/tmp/gpio_get.sock" ]; then
    rm -f "/tmp/gpio_get.sock"
    echo "已清理状态Socket文件"
fi

echo "清理完成"