#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能外卖柜样机 - 应用层主程序
Smart Delivery Cabinet - Application Layer Main Program

作者: xmb505
日期: 2025-12-28
"""

import sys
import os
import signal
import logging
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.config_loader import ConfigLoader
from communication.socket_client import SocketClient
from pickup_code.code_generator import PickupCodeGenerator
from pickup_code.code_validator import PickupCodeValidator
from state_machine.state_machine import CabinetStateMachine
from hardware.gpio_controller import GPIOController
from hardware.lcd_controller import LCDController
from hardware.buzzer_controller import BuzzerController
from hardware.door_controller import DoorController
from input.keyboard_handler import KeyboardHandler
from log_system.logger_setup import setup_logging

class DeliveryBoxApp:
    """智能外卖柜应用主类"""

    def __init__(self):
        """初始化应用"""
        # 加载配置
        self.config = ConfigLoader()
        self.config.load()

        # 设置日志
        self.logger = setup_logging(self.config)
        self.logger.info("=" * 60)
        self.logger.info("智能外卖柜应用启动")
        self.logger.info("=" * 60)

        # 检查命令行参数是否启用键盘调试
        import sys
        debug_keyboard = '--debug-keyboard' in sys.argv or '-dk' in sys.argv

        # 初始化Socket通信客户端
        self.socket_client = SocketClient(self.config, self.logger, debug_keyboard=debug_keyboard)

        # 初始化硬件控制器
        self.gpio_controller = GPIOController(self.socket_client, self.config, self.logger)
        self.lcd_controller = LCDController(self.socket_client, self.config, self.logger)
        self.buzzer_controller = BuzzerController(self.gpio_controller, self.config, self.logger)
        self.door_controller = DoorController(self.gpio_controller, self.config, self.logger)

        # 初始化验证码生成器和验证器
        self.code_generator = PickupCodeGenerator(self.config, self.logger)
        self.code_validator = PickupCodeValidator(self.code_generator, self.config, self.logger)

        # 初始化键盘处理器
        self.keyboard_handler = KeyboardHandler(self.socket_client, self.config, self.logger, debug_keyboard=debug_keyboard)

        # 初始化状态机
        self.state_machine = CabinetStateMachine(
            self.config,
            self.gpio_controller,
            self.lcd_controller,
            self.buzzer_controller,
            self.door_controller,
            self.code_generator,
            self.code_validator,
            self.keyboard_handler,
            self.logger
        )

        # 运行标志
        self.running = False

        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """信号处理函数"""
        self.logger.info(f"收到信号 {signum}，准备关闭应用...")
        self.stop()

    def start(self):
        """启动应用"""
        try:
            self.logger.info("正在启动应用...")

            # 连接Socket
            self.socket_client.connect()

            # 启动Socket监听线程
            self.socket_client.start_monitoring()

            # 初始化硬件
            self._initialize_hardware()

            # 启动状态机
            self.state_machine.start()

            # 设置SocketClient的键盘处理器引用
            self.socket_client.set_keyboard_handler(self.keyboard_handler)
            
            # 启动键盘监听
            self.keyboard_handler.start()

            # 设置运行标志
            self.running = True

            self.logger.info("应用启动成功！")
            self.logger.info("进入主循环...")

            # 主循环
            self._main_loop()

        except Exception as e:
            self.logger.error(f"应用启动失败: {e}", exc_info=True)
            self.stop()
            sys.exit(1)

    def _initialize_hardware(self):
        """初始化硬件"""
        self.logger.info("正在初始化硬件...")

        # 初始化嗡鸣器（预设为停止状态）
        self.buzzer_controller.initialize()

        # 初始化LCD
        self.lcd_controller.initialize()

        # 初始化GPIO状态
        self.gpio_controller.initialize()

        self.logger.info("硬件初始化完成")

    def _main_loop(self):
        """主循环"""
        while self.running:
            try:
                # 处理GPIO事件
                self._process_gpio_events()

                # 处理键盘事件
                self._process_keyboard_events()

                # 状态机更新
                self.state_machine.update()

                # 短暂休眠
                import time
                interval = float(self.config.get('performance', 'event_loop_interval', 0.01))
                time.sleep(interval)

            except Exception as e:
                self.logger.error(f"主循环错误: {e}", exc_info=True)

    def _process_gpio_events(self):
        """处理GPIO事件"""
        events = self.socket_client.get_gpio_events()
        if events:
            self.logger.info(f"收到 {len(events)} 个GPIO事件")
            for event in events:
                self.state_machine.handle_gpio_event(event)

    def _process_keyboard_events(self):
        """处理键盘事件"""
        events = self.keyboard_handler.get_events()
        for event in events:
            self.state_machine.handle_keyboard_event(event)

    def stop(self):
        """停止应用"""
        if not self.running:
            return

        self.logger.info("正在停止应用...")
        self.running = False

        # 停止状态机
        if hasattr(self, 'state_machine'):
            self.state_machine.stop()

        # 停止键盘监听
        if hasattr(self, 'keyboard_handler'):
            self.keyboard_handler.stop()

        # 断开Socket连接
        if hasattr(self, 'socket_client'):
            self.socket_client.disconnect()

        self.logger.info("应用已停止")

def main():
    """主函数"""
    app = DeliveryBoxApp()
    app.start()

if __name__ == "__main__":
    main()