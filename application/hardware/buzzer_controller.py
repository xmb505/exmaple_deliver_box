#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
嗡鸣器控制器
Buzzer Controller
"""

import logging
import time

class BuzzerController:
    """嗡鸣器控制器"""

    def __init__(self, gpio_controller, config, logger):
        """
        初始化嗡鸣器控制器

        Args:
            gpio_controller: GPIOController实例
            config: ConfigLoader实例
            logger: Logger实例
        """
        self.gpio_controller = gpio_controller
        self.config = config
        self.logger = logger

        # 嗡鸣器GPIO
        self.buzzer_gpio = 6

        # 初始化电平
        self.initial_level = config.get_int('buzzer', 'buzzer_initial_level', 1)

        # 提示音配置
        self.init_duration = config.get_float('buzzer', 'buzzer_init_duration', 1.0)

        # 物品未取完提示配置
        self.flash_count = config.get_int('buzzer', 'buzzer_item_not_taken_flash_count', 5)
        self.flash_duration = config.get_float('buzzer', 'buzzer_item_not_taken_flash_duration', 1.0)
        self.flash_interval = config.get_float('buzzer', 'buzzer_item_not_taken_flash_interval', 0.5)

        self.logger.info("嗡鸣器控制器初始化完成")

    def initialize(self):
        """初始化嗡鸣器"""
        self.logger.info("正在初始化嗡鸣器...")
        self.gpio_controller.set_gpio(self.buzzer_gpio, self.initial_level)
        self.logger.info("嗡鸣器初始化完成")

    def beep(self, duration=None):
        """
        单次提示音

        Args:
            duration: 持续时间（秒），默认使用配置值
        """
        if duration is None:
            duration = self.init_duration

        self.logger.info(f"嗡鸣器提示音: {duration}秒")

        # 低电平触发
        self.gpio_controller.set_gpio(self.buzzer_gpio, 0)
        time.sleep(duration)
        self.gpio_controller.set_gpio(self.buzzer_gpio, 1)

    def flash_item_not_taken(self):
        """物品未取完闪烁提示"""
        self.logger.info(f"物品未取完提示: 闪烁{self.flash_count}次")

        for i in range(self.flash_count):
            self.gpio_controller.set_gpio(self.buzzer_gpio, 0)
            time.sleep(self.flash_duration)
            self.gpio_controller.set_gpio(self.buzzer_gpio, 1)
            if i < self.flash_count - 1:
                time.sleep(self.flash_interval)

    def flash_error(self):
        """错误提示：短促闪烁3次"""
        self.logger.info("错误提示: 闪烁3次")

        for i in range(3):
            self.gpio_controller.set_gpio(self.buzzer_gpio, 0)
            time.sleep(0.2)  # 短促提示
            self.gpio_controller.set_gpio(self.buzzer_gpio, 1)
            if i < 2:
                time.sleep(0.2)