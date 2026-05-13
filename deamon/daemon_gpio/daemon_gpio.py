#!/usr/bin/env python3
"""
GPIO守护进程入口
将USB2GPIO设备抽象为UNIX Socket接口，便于进程间通信
采用JSON数据格式进行命令传输

模块结构:
- gpio.controller: USB GPIO控制器
- gpio.daemon: 守护进程核心逻辑
- gpio.server_http: HTTP服务器
- gpio.server_ws: WebSocket服务器
"""

import sys
import os

# 添加当前目录到路径，以便导入gpio子模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gpio.daemon import GPIOControlDaemon


def main():
    """主函数"""
    # 检查命令行参数
    simulate = '--simulate' in sys.argv or '-s' in sys.argv
    debug_spi = '--debug-spi' in sys.argv
    debug = '--debug' in sys.argv or '-d' in sys.argv

    config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.ini')

    # 创建守护进程
    daemon = GPIOControlDaemon(config_path, simulate=simulate, debug_spi=debug_spi)
    daemon.debug = debug

    # 运行守护进程
    daemon.run()


if __name__ == '__main__':
    main()