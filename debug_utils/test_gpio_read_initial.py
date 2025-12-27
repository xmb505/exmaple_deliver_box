#!/usr/bin/env python3
"""
测试gpio_read.py的初始状态查询功能
"""

import sys
import os
sys.path.append('/home/xmb505/智能外卖柜样机/debug_utils')

# 首先启动GPIO守护进程
import subprocess
import time

print("启动GPIO守护进程...")
daemon_process = subprocess.Popen(
    ['python3', 'daemon_gpio.py', '--simulate'],
    cwd='/home/xmb505/智能外卖柜样机/deamon/daemon_gpio',
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

time.sleep(2)  # 等待守护进程启动

print("启动gpio_read.py工具...")
read_process = subprocess.Popen(
    ['python3', 'gpio_read.py', '--socket_path', '/tmp/gpio_get.sock'],
    cwd='/home/xmb505/智能外卖柜样机/debug_utils',
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

time.sleep(3)  # 等待gpio_read运行并发送初始查询

print("停止所有进程...")
read_process.terminate()
daemon_process.terminate()

print("\n=== gpio_read.py 输出 ===")
stdout, stderr = read_process.communicate(timeout=5)
if stdout:
    print(stdout)
if stderr:
    print("错误输出:", stderr)

print("\n测试完成")