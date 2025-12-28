#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LCD控制器
LCD Controller
"""

import logging

class LCDController:
    """LCD控制器"""

    def __init__(self, socket_client, config, logger):
        """
        初始化LCD控制器

        Args:
            socket_client: SocketClient实例
            config: ConfigLoader实例
            logger: Logger实例
        """
        self.socket_client = socket_client
        self.config = config
        self.logger = logger

        # LCD设备ID
        self.courier_lcd_id = config.get_int('lcd', 'courier_lcd_device_id', 1)
        self.student_lcd_id = config.get_int('lcd', 'student_lcd_device_id', 2)

        # 背光GPIO
        self.courier_backlight_gpio = config.get_int('lcd', 'courier_lcd_backlight_gpio', 1)
        self.student_backlight_gpio = config.get_int('lcd', 'student_lcd_backlight_gpio', 2)

        # 背光状态
        self.courier_backlight_on = False
        self.student_backlight_on = False

        self.logger.info("LCD控制器初始化完成")

    def initialize(self):
        """初始化LCD"""
        self.logger.info("正在初始化LCD...")

        # 初始化外卖员侧LCD
        self.socket_client.send_lcd_display(self.courier_lcd_id, "init")

        # 初始化学生侧LCD
        self.socket_client.send_lcd_display(self.student_lcd_id, "init")

        # 显示启动消息
        self.socket_client.send_lcd_display(self.courier_lcd_id, "1")
        self.socket_client.send_lcd_display(self.student_lcd_id, "2")

        # 关闭背光
        self.set_courier_backlight(False)
        self.set_student_backlight(False)

        self.logger.info("LCD初始化完成")
    
    def reinitialize_lcd(self, device_id):
        """
        重新初始化指定LCD（重新使能系统和显示）
        
        Args:
            device_id: 设备ID
        """
        import time
        
        # 关闭显示和系统
        self.set_lcd_display_off(device_id)
        time.sleep(0.1)
        self.set_lcd_sys_off(device_id)
        time.sleep(0.1)
        
        # 重新使能系统和显示
        self.set_lcd_sys_on(device_id)
        time.sleep(0.1)
        self.set_lcd_display_on(device_id)
        time.sleep(0.1)
        
        self.logger.info(f"LCD设备 {device_id} 重新初始化完成")
    
    def reinitialize_courier_lcd(self):
        """重新初始化外卖员侧LCD"""
        self.reinitialize_lcd(self.courier_lcd_id)
    
    def reinitialize_student_lcd(self):
        """重新初始化学生侧LCD"""
        self.reinitialize_lcd(self.student_lcd_id)
    
    def set_lcd_display_on(self, device_id):
        """
        打开指定LCD显示

        Args:
            device_id: 设备ID
        """
        if device_id == self.courier_lcd_id:
            self.socket_client.send_lcd_command(device_id, 'LCD_display_on')
        elif device_id == self.student_lcd_id:
            self.socket_client.send_lcd_command(device_id, 'LCD_display_on')
        else:
            self.socket_client.send_lcd_command(device_id, 'LCD_display_on')
    
    def set_lcd_display_off(self, device_id):
        """
        关闭指定LCD显示

        Args:
            device_id: 设备ID
        """
        if device_id == self.courier_lcd_id:
            self.socket_client.send_lcd_command(device_id, 'LCD_display_off')
        elif device_id == self.student_lcd_id:
            self.socket_client.send_lcd_command(device_id, 'LCD_display_off')
        else:
            self.socket_client.send_lcd_command(device_id, 'LCD_display_off')
    
    def set_lcd_sys_on(self, device_id):
        """
        使能指定LCD系统

        Args:
            device_id: 设备ID
        """
        if device_id == self.courier_lcd_id:
            self.socket_client.send_lcd_command(device_id, 'LCD_sys_on')
        elif device_id == self.student_lcd_id:
            self.socket_client.send_lcd_command(device_id, 'LCD_sys_on')
        else:
            self.socket_client.send_lcd_command(device_id, 'LCD_sys_on')
    
    def set_lcd_sys_off(self, device_id):
        """
        关闭指定LCD系统

        Args:
            device_id: 设备ID
        """
        if device_id == self.courier_lcd_id:
            self.socket_client.send_lcd_command(device_id, 'LCD_sys_off')
        elif device_id == self.student_lcd_id:
            self.socket_client.send_lcd_command(device_id, 'LCD_sys_off')
        else:
            self.socket_client.send_lcd_command(device_id, 'LCD_sys_off')
    
    def set_courier_display_on(self):
        """打开外卖员侧LCD显示"""
        self.set_lcd_display_on(self.courier_lcd_id)
    
    def set_courier_display_off(self):
        """关闭外卖员侧LCD显示"""
        self.set_lcd_display_off(self.courier_lcd_id)
    
    def set_student_display_on(self):
        """打开学生侧LCD显示"""
        self.set_lcd_display_on(self.student_lcd_id)
    
    def set_student_display_off(self):
        """关闭学生侧LCD显示"""
        self.set_lcd_display_off(self.student_lcd_id)

    def display_courier(self, data):
        """
        在外卖员侧LCD显示数据

        Args:
            data: 显示数据（6位字符串）
        """
        self.socket_client.send_lcd_display(self.courier_lcd_id, data)

    def display_student(self, data):
        """
        在学生侧LCD显示数据

        Args:
            data: 显示数据（6位字符串）
        """
        self.socket_client.send_lcd_display(self.student_lcd_id, data)

    def set_courier_backlight(self, on):
        """
        设置外卖员侧LCD背光

        Args:
            on: 是否开启
        """
        gpio_value = 1 if on else 0
        self.socket_client.send_gpio_control(self.courier_backlight_gpio, gpio_value)
        self.courier_backlight_on = on
        self.logger.debug(f"外卖员侧背光: {'开启' if on else '关闭'}")

    def set_student_backlight(self, on):
        """
        设置学生侧LCD背光

        Args:
            on: 是否开启
        """
        gpio_value = 1 if on else 0
        self.socket_client.send_gpio_control(self.student_backlight_gpio, gpio_value)
        self.student_backlight_on = on
        self.logger.debug(f"学生侧背光: {'开启' if on else '关闭'}")

    def clear_courier(self):
        """清空外卖员侧LCD"""
        self.display_courier("      ")

    def clear_student(self):
        """清空学生侧LCD"""
        self.display_student("      ")