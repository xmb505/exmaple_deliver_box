#!/usr/bin/env python3
"""
GPIO控制器 - 通过Unix Socket与daemon_gpio通信
"""

import json
import socket
import configparser
import os
import threading
import time


class GPIOController:
    """GPIO控制器类"""

    def __init__(self, config_path=None):
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.ini')

        self.config = configparser.ConfigParser()
        self.config.read(config_path)

        # Socket路径
        self.gpio_socket = self.config.get('hardware', 'gpio_socket', fallback='/tmp/gpio.sock')
        self.gpio_get_socket = self.config.get('hardware', 'gpio_get_socket', fallback='/tmp/gpio_get.sock')

        # 输出引脚映射
        self.output_pins = {
            'lcd1_backlight': self.config.getint('hardware', 'lcd1_backlight', fallback=1),
            'lcd2_backlight': self.config.getint('hardware', 'lcd2_backlight', fallback=2),
            'lcd3_backlight': self.config.getint('hardware', 'lcd3_backlight', fallback=3),
            'lcd4_backlight': self.config.getint('hardware', 'lcd4_backlight', fallback=4),
            'box1_outer_door': self.config.getint('hardware', 'box1_outer_door', fallback=5),
            'box1_inner_door': self.config.getint('hardware', 'box1_inner_door', fallback=6),
            'box2_outer_door': self.config.getint('hardware', 'box2_outer_door', fallback=7),
            'box2_inner_door': self.config.getint('hardware', 'box2_inner_door', fallback=8),
        }

        # 输入引脚映射
        self.input_pins = {
            'box1_outer_door_sensor': self.config.getint('hardware', 'box1_outer_door_sensor', fallback=1),
            'box1_inner_door_sensor': self.config.getint('hardware', 'box1_inner_door_sensor', fallback=2),
            'box2_outer_door_sensor': self.config.getint('hardware', 'box2_outer_door_sensor', fallback=3),
            'box2_inner_door_sensor': self.config.getint('hardware', 'box2_inner_door_sensor', fallback=4),
            'box1_ir_sensor': self.config.getint('hardware', 'box1_ir_sensor', fallback=5),
            'box2_ir_sensor': self.config.getint('hardware', 'box2_ir_sensor', fallback=6),
        }

        # 存件按钮
        self.store_button_gpio = self.config.getint('hardware', 'store_button_gpio', fallback=16)

        # 状态监听socket
        self.status_socket = None
        self.current_states = {}

        # 电磁锁自动关闭定时器 (保护线圈不被烧毁)
        self.door_lock_timers = {}  # {pin: timer}

    def connect_status_socket(self):
        """连接状态监听socket"""
        try:
            self.status_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.status_socket.connect(self.gpio_get_socket)
            self.status_socket.settimeout(1.0)
            # 查询当前状态
            self.query_status()
            return True
        except Exception as e:
            print(f"[GPIO] 连接状态socket失败: {e}")
            return False

    def send_command(self, gpio, value):
        """发送GPIO控制命令"""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            command = {
                "alias": "sender",
                "mode": "set",
                "gpio": gpio,
                "value": value
            }
            sock.sendto(json.dumps(command).encode(), self.gpio_socket)
            sock.close()
            return True
        except Exception as e:
            print(f"[GPIO] 发送命令失败: {e}")
            return False

    def send_commands(self, gpios, values):
        """批量发送GPIO控制命令"""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            command = {
                "alias": "sender",
                "mode": "set",
                "gpios": gpios,
                "values": values
            }
            sock.sendto(json.dumps(command).encode(), self.gpio_socket)
            sock.close()
            return True
        except Exception as e:
            print(f"[GPIO] 批量发送命令失败: {e}")
            return False

    def query_status(self):
        """查询当前GPIO状态"""
        try:
            if self.status_socket:
                command = {"type": "query_status"}
                self.status_socket.send(json.dumps(command).encode())
        except Exception as e:
            print(f"[GPIO] 查询状态失败: {e}")

    def receive_status(self, timeout=0.1):
        """接收状态更新"""
        if not self.status_socket:
            return None
        try:
            self.status_socket.settimeout(timeout)
            data = self.status_socket.recv(4096)
            if data:
                msg = json.loads(data.decode())
                if msg.get('type') == 'gpio_change':
                    # 更新状态
                    for gpio_info in msg.get('gpios', []):
                        for change in gpio_info.get('change_gpio', []):
                            gpio_num = change.get('gpio')
                            bit = change.get('bit')
                            # 统一使用整数作为键
                            self.current_states[int(gpio_num)] = bit
                elif msg.get('type') == 'current_status':
                    # 初始状态
                    for gpio_info in msg.get('gpios', []):
                        states = gpio_info.get('current_gpio_states', {})
                        for gpio_str, bit in states.items():
                            self.current_states[int(gpio_str)] = bit
                return msg
        except socket.timeout:
            pass
        except Exception as e:
            pass
        return None

    def get_sensor_state(self, sensor_name):
        """获取传感器状态"""
        gpio_num = self.input_pins.get(sensor_name)
        if gpio_num is None:
            return None
        return self.current_states.get(gpio_num)

    def get_store_button_state(self):
        """获取存件按钮状态"""
        return self.current_states.get(self.store_button_gpio)

    # 便捷控制方法
    def _open_door_with_auto_close(self, pin, box_id, door_type):
        """开门并启动1秒自动关闭保护（防止电磁锁烧毁）"""
        # 取消之前的定时器（如果有）
        if pin in self.door_lock_timers:
            self.door_lock_timers[pin].cancel()

        # 发送开门命令
        self.send_command(pin, 1)
        print(f"[GPIO] 打开柜子{box_id}{door_type}门（1秒后自动关闭）")

        # 启动1秒后自动关闭的定时器
        timer = threading.Timer(1.0, lambda: self._auto_close_door(pin, box_id, door_type))
        timer.daemon = True
        timer.start()
        self.door_lock_timers[pin] = timer

    def _auto_close_door(self, pin, box_id, door_type):
        """自动关闭门（保护电磁锁线圈）"""
        self.send_command(pin, 0)
        print(f"[GPIO] 柜子{box_id}{door_type}门已自动关闭（电磁锁保护）")
        if pin in self.door_lock_timers:
            del self.door_lock_timers[pin]

    def open_box_outer_door(self, box_id):
        """打开外侧门（1秒后自动关闭）"""
        pin_name = f'box{box_id}_outer_door'
        pin = self.output_pins.get(pin_name)
        if pin:
            self._open_door_with_auto_close(pin, box_id, "外侧")

    def close_box_outer_door(self, box_id):
        """关闭外侧门"""
        pin_name = f'box{box_id}_outer_door'
        pin = self.output_pins.get(pin_name)
        if pin:
            # 取消自动关闭定时器
            if pin in self.door_lock_timers:
                self.door_lock_timers[pin].cancel()
                del self.door_lock_timers[pin]
            self.send_command(pin, 0)
            print(f"[GPIO] 关闭柜子{box_id}外侧门")

    def open_box_inner_door(self, box_id):
        """打开内侧门（1秒后自动关闭）"""
        pin_name = f'box{box_id}_inner_door'
        pin = self.output_pins.get(pin_name)
        if pin:
            self._open_door_with_auto_close(pin, box_id, "内侧")

    def close_box_inner_door(self, box_id):
        """关闭内侧门"""
        pin_name = f'box{box_id}_inner_door'
        pin = self.output_pins.get(pin_name)
        if pin:
            # 取消自动关闭定时器
            if pin in self.door_lock_timers:
                self.door_lock_timers[pin].cancel()
                del self.door_lock_timers[pin]
            self.send_command(pin, 0)
            print(f"[GPIO] 关闭柜子{box_id}内侧门")

    def is_outer_door_closed(self, box_id):
        """检测外侧门是否关闭"""
        sensor_name = f'box{box_id}_outer_door_sensor'
        return self.get_sensor_state(sensor_name) == 1

    def is_inner_door_closed(self, box_id):
        """检测内侧门是否关闭"""
        sensor_name = f'box{box_id}_inner_door_sensor'
        return self.get_sensor_state(sensor_name) == 1

    def has_item(self, box_id):
        """检测柜内是否有物品(红外对射)"""
        sensor_name = f'box{box_id}_ir_sensor'
        # 无遮挡=高电平，有遮挡=低电平
        return self.get_sensor_state(sensor_name) == 0

    def close(self):
        """关闭连接"""
        if self.status_socket:
            self.status_socket.close()
