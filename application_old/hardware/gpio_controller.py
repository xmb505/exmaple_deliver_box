#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPIO控制器
GPIO Controller
"""

import logging
import time
from collections import deque

class GPIOController:
    """GPIO控制器"""

    def __init__(self, socket_client, config, logger):
        """
        初始化GPIO控制器

        Args:
            socket_client: SocketClient实例
            config: ConfigLoader实例
            logger: Logger实例
        """
        self.socket_client = socket_client
        self.config = config
        self.logger = logger

        # GPIO状态缓存
        self.current_states = {}

        # GPIO事件队列
        self.events = deque()

        # GPIO映射
        self.ir_sensor1_gpio = 1
        self.ir_sensor2_gpio = 2
        self.init_button_gpio = 3
        self.courier_button_gpio = 4
        self.courier_door_gpio = 5
        self.student_door_gpio = 6

        self.logger.info("GPIO控制器初始化完成")

    def initialize(self):
        """初始化GPIO状态"""
        self.logger.info("正在初始化GPIO状态...")

        # 预设嗡鸣器为停止状态（GPIO 6，高电平=停止）
        self.set_gpio(6, 1)

        # 预设LCD背光为关闭状态（GPIO 1, 2）
        self.set_gpio(1, 0)
        self.set_gpio(2, 0)

        # 预设柜内灯为关闭状态（GPIO 3）
        self.set_gpio(3, 0)

        # 预设门锁为关闭状态（GPIO 4, 5）
        self.set_gpio(4, 0)
        self.set_gpio(5, 0)

        self.logger.info("GPIO状态初始化完成")

    def set_gpio(self, gpio, value):
        """
        设置GPIO电平

        Args:
            gpio: GPIO编号
            value: 值 (0或1)
        """
        # 检查状态是否变化
        if self.current_states.get(gpio) == value:
            return

        # 发送控制命令
        self.socket_client.send_gpio_control(gpio, value)

        # 更新缓存
        self.current_states[gpio] = value

    def get_gpio_state(self, gpio):
        """
        获取GPIO状态

        Args:
            gpio: GPIO编号

        Returns:
            int: GPIO状态 (0或1)
        """
        return self.current_states.get(gpio, None)

    def add_event(self, event):
        """
        添加GPIO事件

        Args:
            event: GPIO事件字典
        """
        self.events.append(event)

    def get_events(self):
        """
        获取所有GPIO事件

        Returns:
            list: GPIO事件列表
        """
        events = list(self.events)
        self.events.clear()
        return events