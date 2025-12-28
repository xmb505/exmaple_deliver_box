#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
门锁控制器
Door Controller
"""

import threading
import time
import logging

class DoorController:
    """门锁控制器"""

    def __init__(self, gpio_controller, config, logger):
        """
        初始化门锁控制器

        Args:
            gpio_controller: GPIOController实例
            config: ConfigLoader实例
            logger: Logger实例
        """
        self.gpio_controller = gpio_controller
        self.config = config
        self.logger = logger

        # GPIO编号
        self.courier_door_gpio = 4  # 外卖员侧门锁
        self.student_door_gpio = 5  # 学生侧门锁

        # 门锁配置
        self.pulse_duration = config.get_float('door_control', 'door_lock_pulse_duration', 1.0)
        self.off_delay = config.get_float('door_control', 'door_lock_off_delay', 0.1)

        self.logger.info("门锁控制器初始化完成")

    def open_courier_door(self):
        """打开外卖员侧门锁"""
        self._open_door(self.courier_door_gpio, "外卖员侧")

    def open_student_door(self):
        """打开学生侧门锁"""
        self._open_door(self.student_door_gpio, "学生侧")

    def _open_door(self, gpio, door_name):
        """
        打开门锁（内部方法）

        Args:
            gpio: GPIO编号
            door_name: 门名称（用于日志）
        """
        self.logger.info(f"正在打开{door_name}门锁...")

        # 使用独立线程确保1秒后自动断电
        def door_lock_thread():
            try:
                # 打开门锁（通电）
                self.gpio_controller.set_gpio(gpio, 1)
                self.logger.info(f"{door_name}门锁已通电（开门）")

                # 等待1秒
                time.sleep(self.pulse_duration)

                # 关闭门锁（断电）
                self.gpio_controller.set_gpio(gpio, 0)
                self.logger.info(f"{door_name}门锁已断电（1秒脉冲结束）")

            except Exception as e:
                self.logger.error(f"{door_name}门锁控制失败: {e}")

        thread = threading.Thread(target=door_lock_thread, daemon=True)
        thread.start()