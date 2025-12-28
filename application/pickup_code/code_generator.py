#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证码生成器
Pickup Code Generator
"""

import secrets
import random
from datetime import datetime
import logging

class PickupCodeGenerator:
    """验证码生成器"""

    def __init__(self, config, logger):
        """
        初始化验证码生成器

        Args:
            config: ConfigLoader实例
            logger: Logger实例
        """
        self.config = config
        self.logger = logger

        # 验证码配置
        self.code_length = config.get_int('pickup_code', 'pickup_code_length', 6)
        self.code_min = config.get_int('pickup_code', 'pickup_code_min', 100000)
        self.code_max = config.get_int('pickup_code', 'pickup_code_max', 999999)
        self.history_size = config.get_int('pickup_code', 'pickup_code_history_size', 1000)
        self.anti_replay = config.get_bool('pickup_code', 'pickup_code_anti_replay', True)
        self.replay_window = config.get_int('pickup_code', 'pickup_code_replay_window', 300)
        self.validity_period = config.get_int('pickup_code', 'pickup_code_validity_period', 3600)
        self.uniqueness_check = config.get_bool('pickup_code', 'pickup_code_uniqueness_check', True)
        self.random_generator = config.get('pickup_code', 'pickup_code_random_generator', 'secrets')

        # 历史验证码
        self.code_history = []

        # 当前有效验证码
        self.active_codes = {}

        self.logger.info(f"验证码生成器初始化完成 (长度={self.code_length}, 随机生成器={self.random_generator})")

    def generate_code(self):
        """
        生成6位随机验证码

        Returns:
            str: 6位验证码

        Raises:
            RuntimeError: 无法生成唯一验证码
        """
        max_retries = 100

        for retry in range(max_retries):
            # 生成验证码
            if self.random_generator == 'secrets':
                # 使用加密安全的随机数生成器
                code = f"{secrets.randbelow(self.code_max - self.code_min + 1) + self.code_min:06d}"
            else:
                # 使用普通随机数生成器（仅用于测试）
                code = f"{random.randint(self.code_min, self.code_max):06d}"

            # 检查唯一性
            if not self._is_unique(code):
                self.logger.debug(f"验证码 {code} 已存在，重新生成 (重试 {retry + 1}/{max_retries})")
                continue

            # 记录验证码
            timestamp = datetime.now().timestamp()
            self.active_codes[code] = {
                'created': timestamp,
                'used': False
            }

            # 添加到历史记录
            self.code_history.append(code)

            # 限制历史记录大小
            if len(self.code_history) > self.history_size:
                self.code_history.pop(0)

            self.logger.info(f"生成验证码: {code}")
            return code

        # 超过最大重试次数
        error_msg = f"无法生成唯一验证码（已重试 {max_retries} 次）"
        self.logger.error(error_msg)
        raise RuntimeError(error_msg)

    def _is_unique(self, code):
        """
        检查验证码是否唯一

        Args:
            code: 验证码

        Returns:
            bool: 是否唯一
        """
        if not self.uniqueness_check:
            return True

        # 检查是否在历史记录中
        if code in self.code_history:
            return False

        # 检查是否在当前有效验证码中
        if code in self.active_codes:
            return False

        return True

    def mark_as_used(self, code):
        """
        标记验证码为已使用

        Args:
            code: 验证码
        """
        if code in self.active_codes:
            self.active_codes[code]['used'] = True
            self.logger.info(f"验证码 {code} 已标记为已使用")

    def get_code_info(self, code):
        """
        获取验证码信息

        Args:
            code: 验证码

        Returns:
            dict: 验证码信息，如果不存在返回None
        """
        return self.active_codes.get(code)

    def cleanup_expired_codes(self):
        """清理过期验证码"""
        current_time = datetime.now().timestamp()
        expired_codes = []

        for code, info in self.active_codes.items():
            if current_time - info['created'] > self.validity_period:
                expired_codes.append(code)

        for code in expired_codes:
            del self.active_codes[code]
            self.logger.debug(f"清理过期验证码: {code}")

        return len(expired_codes)

    def get_active_codes_count(self):
        """获取当前有效验证码数量"""
        return len(self.active_codes)

    def is_valid(self, code):
        """
        检查验证码是否有效

        Args:
            code: 验证码

        Returns:
            bool: 是否有效
        """
        if code not in self.active_codes:
            return False

        info = self.active_codes[code]
        current_time = datetime.now().timestamp()

        # 检查是否过期
        if current_time - info['created'] > self.validity_period:
            return False

        # 检查是否已使用
        if info['used']:
            return False

        return True