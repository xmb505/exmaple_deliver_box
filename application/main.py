#!/usr/bin/env python3
"""
智能外卖柜 - 主程序入口
"""

import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from state_machine.delivery_box import DeliveryBoxMachine


def main():
    """主函数"""
    print("""
╔═══════════════════════════════════════════════════╗
║                                                   ║
║          智能外卖柜系统 v1.0                      ║
║                                                   ║
║  基于MT7621路由器 + immortalwrt                  ║
║                                                   ║
╚═══════════════════════════════════════════════════╝
    """)

    machine = DeliveryBoxMachine()

    try:
        machine.run()
    except KeyboardInterrupt:
        print("\n\n收到中断信号，正在退出...")
        machine.stop()
    except Exception as e:
        print(f"\n系统错误: {e}")
        import traceback
        traceback.print_exc()
        machine.stop()


if __name__ == "__main__":
    main()
