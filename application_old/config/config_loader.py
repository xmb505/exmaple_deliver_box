#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置文件加载器
Configuration File Loader
"""

import configparser
import os
import logging

class ConfigLoader:
    """配置文件加载器"""

    def __init__(self, config_path=None):
        """
        初始化配置加载器

        Args:
            config_path: 配置文件路径，默认为 ../config/config.ini
        """
        if config_path is None:
            # 获取当前文件的目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, '..', 'config', 'config.ini')

        self.config_path = os.path.abspath(config_path)
        self.config = configparser.ConfigParser()
        self.logger = logging.getLogger(__name__)

    def load(self):
        """加载配置文件"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")

        self.config.read(self.config_path, encoding='utf-8')
        self.logger.info(f"配置文件加载成功: {self.config_path}")

    def get(self, section, key, default=None, dtype=str):
        """
        获取配置项

        Args:
            section: 配置节名称
            key: 配置键名称
            default: 默认值
            dtype: 数据类型 (str, int, float, bool)

        Returns:
            配置值
        """
        try:
            if not self.config.has_section(section):
                self.logger.warning(f"配置节不存在: [{section}]")
                return default

            if not self.config.has_option(section, key):
                self.logger.warning(f"配置项不存在: [{section}] {key}")
                return default

            value = self.config.get(section, key)

            # 类型转换
            if dtype == int:
                return int(value)
            elif dtype == float:
                return float(value)
            elif dtype == bool:
                return value.lower() in ('true', '1', 'yes', 'on')
            elif dtype == list:
                # 逗号分隔的列表
                return [item.strip() for item in value.split(',')]
            else:
                return value

        except Exception as e:
            self.logger.error(f"读取配置项失败: [{section}] {key} - {e}")
            return default

    def get_int(self, section, key, default=None):
        """获取整数配置"""
        return self.get(section, key, default, int)

    def get_float(self, section, key, default=None):
        """获取浮点数配置"""
        return self.get(section, key, default, float)

    def get_bool(self, section, key, default=None):
        """获取布尔值配置"""
        return self.get(section, key, default, bool)

    def get_list(self, section, key, default=None):
        """获取列表配置"""
        return self.get(section, key, default, list)

    def get_all(self, section):
        """
        获取配置节的所有配置项

        Args:
            section: 配置节名称

        Returns:
            字典形式的配置项
        """
        if not self.config.has_section(section):
            return {}

        return dict(self.config.items(section))

    def has_section(self, section):
        """检查配置节是否存在"""
        return self.config.has_section(section)

    def has_option(self, section, key):
        """检查配置项是否存在"""
        return self.config.has_option(section, key)