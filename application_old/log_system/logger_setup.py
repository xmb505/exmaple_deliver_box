#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志系统设置
Logging System Setup
"""

import logging
import os

def setup_logging(config):
    """
    设置日志系统

    Args:
        config: ConfigLoader实例

    Returns:
        logger实例
    """
    # 获取日志配置
    log_level = config.get('logging', 'log_level', 'INFO')
    log_file = config.get('logging', 'log_file', '/var/log/delivery_box.log')
    log_format = config.get('logging', 'log_format',
                          '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 创建日志目录
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except PermissionError:
            # 如果无法创建/var/log目录，使用当前目录
            log_file = 'delivery_box.log'

    # 配置根日志记录器
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # 清除现有的处理器
    logger.handlers.clear()

    # 创建格式化器
    formatter = logging.Formatter(log_format)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器
    try:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except (PermissionError, IOError) as e:
        # 如果无法写入日志文件，只使用控制台输出
        logger.warning(f"无法创建日志文件: {e}")

    return logger