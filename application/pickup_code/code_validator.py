#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证码验证器
Pickup Code Validator
"""

from datetime import datetime
import logging

class PickupCodeValidator:
    """验证码验证器"""

    def __init__(self, code_generator, config, logger):
        """
        初始化验证码验证器

        Args:
            code_generator: PickupCodeGenerator实例
            config: ConfigLoader实例
            logger: Logger实例
        """
        self.code_generator = code_generator
        self.config = config
        self.logger = logger

        self.logger.info("验证码验证器初始化完成")

    def verify_code(self, code):
        """
        验证取件码

        Args:
            code: 验证码

        Returns:
            tuple: (是否成功, 错误码或成功消息)
        """
        current_time = datetime.now().timestamp()

        # 1. 检查格式（6位纯数字）
        if not code.isdigit() or len(code) != 6:
            self.logger.warning(f"验证码格式错误: {code}")
            return False, "Err001"

        # 2. 检查是否存在
        if code not in self.code_generator.active_codes:
            self.logger.warning(f"验证码不存在: {code}")
            return False, "Err002"

        code_info = self.code_generator.active_codes[code]

        # 3. 检查是否已使用
        if code_info['used']:
            self.logger.warning(f"验证码已使用: {code}")
            return False, "Err004"

        # 验证成功，标记为已使用
        code_info['used'] = True
        self.logger.info(f"验证码验证成功: {code}")

        return True, "验证成功"