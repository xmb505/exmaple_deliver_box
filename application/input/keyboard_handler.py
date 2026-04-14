#!/usr/bin/env python3
"""
键盘输入处理 - 通过Unix Socket与daemon_keyboard通信
处理学生侧小键盘输入
"""

import json
import socket
import configparser
import os
import select


class KeyboardHandler:
    """键盘输入处理器"""

    def __init__(self, config_path=None):
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.ini')

        self.config = configparser.ConfigParser()
        self.config.read(config_path)

        # Socket路径
        self.keyboard_socket = self.config.get('hardware', 'keyboard_socket', fallback='/tmp/keyboard_get.sock')

        # 键盘socket连接
        self.socket = None

        # 当前输入缓冲
        self.input_buffer = ""

        # 最大输入长度
        self.max_input_length = 6

        # 回调函数
        self.on_digit_callback = None
        self.on_enter_callback = None
        self.on_delete_callback = None

    def connect(self):
        """连接键盘socket"""
        try:
            # 键盘守护进程使用UDP (SOCK_DGRAM)，不是TCP
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            # 绑定一个本地地址以便接收广播
            local_addr = f"/tmp/keyboard_client_{os.getpid()}.sock"
            if os.path.exists(local_addr):
                os.unlink(local_addr)
            self.socket.bind(local_addr)
            self.socket.settimeout(0.1)

            # 发送query_status消息注册到守护进程，否则不会收到广播
            try:
                register_msg = {"type": "query_status"}
                self.socket.sendto(json.dumps(register_msg).encode(), self.keyboard_socket)
                print(f"[键盘] 已发送注册消息到 {self.keyboard_socket}")
            except Exception as e:
                print(f"[键盘] 发送注册消息失败: {e}")

            print("[键盘] 连接成功")
            return True
        except Exception as e:
            print(f"[键盘] 连接失败: {e}")
            return False

    def set_callbacks(self, on_digit=None, on_enter=None, on_delete=None):
        """设置回调函数"""
        self.on_digit_callback = on_digit
        self.on_enter_callback = on_enter
        self.on_delete_callback = on_delete

    def process_event(self, timeout=0.1):
        """处理键盘事件"""
        if not self.socket:
            return None

        try:
            self.socket.settimeout(timeout)
            # UDP使用recvfrom而不是recv
            data, addr = self.socket.recvfrom(4096)
            if data:
                msg = json.loads(data.decode())
                print(f"[键盘] 收到事件: {msg}")

                if msg.get('type') == 'key_event':
                    event_type = msg.get('event_type')
                    key = msg.get('key')

                    # 只处理按键按下事件
                    if event_type == 'press':
                        return self._handle_key(key)

                return msg
        except socket.timeout:
            pass
        except Exception as e:
            print(f"[键盘] 处理事件出错: {e}")
        return None

    def _handle_key(self, key):
        """处理按键"""
        result = {
            'key': key,
            'action': None,
            'buffer': self.input_buffer
        }

        # 数字键 (主键盘数字)
        if key in '0123456789':
            if len(self.input_buffer) < self.max_input_length:
                self.input_buffer += key
                result['action'] = 'digit'
                result['buffer'] = self.input_buffer
                print(f"[键盘] 输入: {key}, 当前: {self.input_buffer}")
                if self.on_digit_callback:
                    self.on_digit_callback(self.input_buffer)
            else:
                print(f"[键盘] 输入已达最大长度")

        # 小键盘数字键 (KP0-KP9)
        elif key in ('KP0', 'KP1', 'KP2', 'KP3', 'KP4', 'KP5', 'KP6', 'KP7', 'KP8', 'KP9'):
            digit = key[-1]  # 提取最后一位数字
            if len(self.input_buffer) < self.max_input_length:
                self.input_buffer += digit
                result['action'] = 'digit'
                result['buffer'] = self.input_buffer
                print(f"[键盘] 小键盘输入: {digit}, 当前: {self.input_buffer}")
                if self.on_digit_callback:
                    self.on_digit_callback(self.input_buffer)
            else:
                print(f"[键盘] 输入已达最大长度")

        # 回车键 (主键盘回车和小键盘回车)
        elif key in ('ENTER', 'KPENTER', '\n'):
            result['action'] = 'enter'
            result['buffer'] = self.input_buffer
            print(f"[键盘] 确认输入: {self.input_buffer}")
            if self.on_enter_callback:
                self.on_enter_callback(self.input_buffer)

        # 删除键 (Backspace 和小键盘点/删除键)
        elif key in ('BACKSPACE', 'DELETE', 'KPDOT'):
            if self.input_buffer:
                self.input_buffer = self.input_buffer[:-1]
                result['action'] = 'delete'
                result['buffer'] = self.input_buffer
                print(f"[键盘] 删除, 当前: {self.input_buffer}")
                if self.on_delete_callback:
                    self.on_delete_callback(self.input_buffer)

        return result

    def clear_buffer(self):
        """清空输入缓冲"""
        self.input_buffer = ""
        print("[键盘] 输入已清空")

    def get_buffer(self):
        """获取当前输入缓冲"""
        return self.input_buffer

    def close(self):
        """关闭连接"""
        if self.socket:
            self.socket.close()
