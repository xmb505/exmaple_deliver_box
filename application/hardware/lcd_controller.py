#!/usr/bin/env python3
"""
LCD控制器 - 通过Unix Socket与daemon_ht1621通信
控制HT1621 LCD显示
"""

import json
import socket
import configparser
import os


class LCDController:
    """LCD控制器类"""

    def __init__(self, config_path=None):
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.ini')

        self.config = configparser.ConfigParser()
        self.config.read(config_path)

        # Socket路径
        self.ht1621_socket = self.config.get('hardware', 'ht1621_socket', fallback='/tmp/ht1621.sock')

        # SPI设备映射
        self.lcd_spi_map = {
            1: self.config.getint('hardware', 'lcd1_spi', fallback=1),
            2: self.config.getint('hardware', 'lcd2_spi', fallback=2),
            3: self.config.getint('hardware', 'lcd3_spi', fallback=3),
            4: self.config.getint('hardware', 'lcd4_spi', fallback=4),
        }

        # 背光引脚映射
        self.backlight_pins = {
            1: self.config.getint('hardware', 'lcd1_backlight', fallback=1),
            2: self.config.getint('hardware', 'lcd2_backlight', fallback=2),
            3: self.config.getint('hardware', 'lcd3_backlight', fallback=3),
            4: self.config.getint('hardware', 'lcd4_backlight', fallback=4),
        }

        # GPIO控制器引用(用于背光控制)
        self.gpio_controller = None

    def set_gpio_controller(self, gpio_controller):
        """设置GPIO控制器引用"""
        self.gpio_controller = gpio_controller

    def send_command(self, device_id, display_data):
        """发送LCD显示命令"""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            command = {
                "device_id": device_id,
                "display_data": display_data
            }
            json_data = json.dumps(command)
            print(f"[LCD] 发送命令: {json_data} 到 {self.ht1621_socket}")
            sock.sendto(json_data.encode(), self.ht1621_socket)
            sock.close()
            return True
        except Exception as e:
            print(f"[LCD] 发送命令失败: {e}")
            return False

    def init_display(self, lcd_id):
        """初始化LCD"""
        spi_id = self.lcd_spi_map.get(lcd_id)
        if spi_id:
            return self.send_command(spi_id, "init")
        return False

    def display(self, lcd_id, text):
        """在LCD上显示文本"""
        spi_id = self.lcd_spi_map.get(lcd_id)
        if spi_id:
            return self.send_command(spi_id, str(text))
        return False

    def clear(self, lcd_id):
        """清空LCD显示"""
        return self.display(lcd_id, "      ")

    def set_backlight(self, lcd_id, on):
        """设置LCD背光"""
        if self.gpio_controller:
            pin = self.backlight_pins.get(lcd_id)
            if pin:
                self.gpio_controller.send_command(pin, 1 if on else 0)
                state = "开" if on else "关"
                print(f"[LCD] LCD{lcd_id}背光{state}")

    def display_pickup_code(self, box_id, code):
        """在柜子对应的LCD上显示取件码"""
        # LCD3对应柜子1，LCD4对应柜子2
        lcd_id = box_id + 2  # box1 -> LCD3, box2 -> LCD4
        self.display(lcd_id, code)
        self.set_backlight(lcd_id, True)
        print(f"[LCD] 柜子{box_id}显示取件码: {code}")

    def display_input(self, text):
        """在学生侧LCD上显示输入内容"""
        # LCD2是学生侧显示
        self.display(2, text)
        self.set_backlight(2, True)
        print(f"[LCD] 学生侧显示: {text}")

    def display_box_id(self, box_id):
        """在外卖侧LCD上显示柜子编号"""
        # LCD1是外卖侧显示，格式为 "1-1" 或 "1-2"
        self.display(1, f"1-{box_id}")
        self.set_backlight(1, True)
        print(f"[LCD] 外卖侧显示柜子编号: 1-{box_id}")

    def init_all(self):
        """初始化所有LCD - 初始化设备并关闭背光"""
        for lcd_id in [1, 2, 3, 4]:
            # 发送初始化指令
            self.init_display(lcd_id)
            # 清空显示
            self.display(lcd_id, "      ")
            # 关闭背光
            self.set_backlight(lcd_id, False)
        print("[LCD] 所有LCD初始化完成，背光已关闭")
