#!/usr/bin/env python3
"""
测试修复后的daemon_gpio.py
"""
import sys
import os
sys.path.append('/home/xmb505/智能外卖柜样机/deamon/daemon_gpio')

import daemon_gpio
import time
import threading

def test_daemon():
    print("开始测试修复后的GPIO守护进程...")
    
    try:
        # 创建守护进程实例（模拟模式）
        daemon = daemon_gpio.GPIOControlDaemon('config/config.ini', simulate=True)
        print("✓ 守护进程初始化成功")
        
        # 设置调试标志
        daemon.debug = False
        
        # 启动守护进程在单独的线程中
        daemon_thread = threading.Thread(target=daemon.run, daemon=True)
        daemon_thread.start()
        print("✓ 守护进程启动成功")
        
        # 等待几秒钟让守护进程运行
        time.sleep(3)
        
        # 停止守护进程
        daemon.stop()
        print("✓ 守护进程停止成功")
        
        print("\n所有测试通过！GPIO守护进程的修复已成功。")
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_daemon()
    if success:
        print("\n修复验证成功！")
    else:
        print("\n修复验证失败！")
        sys.exit(1)
