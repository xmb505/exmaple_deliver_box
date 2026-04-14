#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
键盘处理器
Keyboard Handler
"""

import logging
import time
from collections import deque

class KeyboardHandler:
    """键盘处理器"""

    def __init__(self, socket_client, config, logger, debug_keyboard=False):
        """
        初始化键盘处理器

        Args:
            socket_client: SocketClient实例
            config: ConfigLoader实例
            logger: Logger实例
            debug_keyboard: 是否启用键盘调试模式
        """
        self.socket_client = socket_client
        self.config = config
        self.logger = logger
        self.debug_keyboard = debug_keyboard

        # 输入缓冲区
        self.input_buffer = ""
        self.max_length = config.get_int('pickup_code', 'pickup_code_length', 6)

        # 超时配置
        self.timeout = config.get_int('keyboard', 'keyboard_input_timeout', 60)
        self.last_input_time = None
        self.input_active = False

        # 事件队列
        self.events = deque()

        # 小键盘key_code到数字的映射
        self.numpad_key_map = {
            82: '0',  # KP_0
            79: '1',  # KP_1
            80: '2',  # KP_2
            81: '3',  # KP_3
            75: '4',  # KP_4
            76: '5',  # KP_5
            77: '6',  # KP_6
            71: '7',  # KP_7
            72: '8',  # KP_8
            73: '9',  # KP_9
        }
        
        # 小键盘回车键key_code
        self.numpad_enter_key = 96  # KP_ENTER

        # 支持的按键
        self.supported_keys = config.get_list('keyboard', 'keyboard_supported_keys', ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'])
        self.numpad_keys = config.get('keyboard', 'keyboard_numpad_keys', '82,79,80,81,75,76,77,71,72,73').split(',')
        self.numpad_keys = [int(k) for k in self.numpad_keys]

        # 功能键
        self.delete_keys = ['BACKSPACE', 'KP_MINUS']
        self.submit_key = 'ENTER'

        self.logger.info("键盘处理器初始化完成")

    def start(self):
        """启动键盘监听"""
        self.logger.info("启动键盘监听...")
        self.socket_client.start_monitoring()

    def stop(self):
        """停止键盘监听"""
        self.logger.info("停止键盘监听...")

    def handle_key_event(self, event):
        """
        处理键盘事件

        Args:
            event: 键盘事件字典
        """
        event_type = event.get('event_type')
        key = event.get('key')
        key_code = event.get('key_code')

        if self.debug_keyboard:
            self.logger.info(f"处理键盘事件: type={event_type}, key={key}, code={key_code}")

        if event_type != 'press':
            if self.debug_keyboard:
                self.logger.info(f"非按下事件，忽略: {event_type}")
            return

        # 处理数字键（主键盘或小键盘）
        digit = None
        if key in self.supported_keys:
            digit = key
        elif key_code in self.numpad_key_map:
            digit = self.numpad_key_map[key_code]
        
        if digit is not None:
            if len(self.input_buffer) < self.max_length:
                self.input_buffer += digit
                self.last_input_time = time.time()
                self.input_active = True
                self.logger.debug(f"输入: {self.input_buffer}")
                
                if self.debug_keyboard:
                    self.logger.info(f"数字键输入: {digit} (key={key}, code={key_code}), 当前缓冲区: {self.input_buffer}")

                # 添加输入事件
                self.events.append({
                    'type': 'input',
                    'value': self.input_buffer
                })

        # 处理删除键
        elif key in self.delete_keys:
            if len(self.input_buffer) > 0:
                self.input_buffer = self.input_buffer[:-1]
                self.last_input_time = time.time()
                self.logger.debug(f"删除: {self.input_buffer}")
                
                if self.debug_keyboard:
                    self.logger.info(f"删除键输入，当前缓冲区: {self.input_buffer}")

                # 添加输入事件
                self.events.append({
                    'type': 'input',
                    'value': self.input_buffer
                })

        # 处理提交键
        elif key == self.submit_key or key_code == self.numpad_enter_key:
            if len(self.input_buffer) == self.max_length:
                code = self.input_buffer
                self.input_buffer = ""
                self.input_active = False
                self.logger.info(f"提交验证码: {code}")
                
                if self.debug_keyboard:
                    self.logger.info(f"提交键输入，验证码: {code}")

                # 添加提交事件
                self.events.append({
                    'type': 'submit',
                    'value': code
                })
            else:
                if self.debug_keyboard:
                    self.logger.info(f"验证码长度不足，当前长度: {len(self.input_buffer)}, 需要: {self.max_length}")

    def check_timeout(self):
        """
        检查输入超时

        Returns:
            bool: 是否超时
        """
        if not self.input_active:
            return False

        if self.last_input_time is None:
            return False

        elapsed = time.time() - self.last_input_time
        if elapsed > self.timeout:
            self.logger.info(f"输入超时: {elapsed}秒")
            self.input_buffer = ""
            self.input_active = False
            self.last_input_time = None

            # 添加超时事件
            self.events.append({
                'type': 'timeout'
            })

            return True

        return False

    def clear_input(self):
        """清空输入缓冲区"""
        self.input_buffer = ""
        self.input_active = False
        self.last_input_time = None
        self.logger.debug("清空输入缓冲区")

    def get_events(self):
        """
        获取所有键盘事件

        Returns:
            list: 键盘事件列表
        """
        events = list(self.events)
        self.events.clear()
        return events