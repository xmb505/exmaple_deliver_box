#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Socket通信客户端
Socket Communication Client
"""

import socket
import json
import select
import threading
import logging
from queue import Queue

class SocketClient:
    """Socket通信客户端"""

    def __init__(self, config, logger, keyboard_handler=None, debug_keyboard=False):
        """
        初始化Socket客户端

        Args:
            config: ConfigLoader实例
            logger: Logger实例
            keyboard_handler: KeyboardHandler实例（可选）
            debug_keyboard: 是否启用键盘调试模式
        """
        self.config = config
        self.logger = logger
        self.keyboard_handler = keyboard_handler
        self.debug_keyboard = debug_keyboard

        # Socket路径
        self.gpio_control_socket = config.get('daemon_config', 'gpio_control_socket', '/tmp/gpio.sock')
        self.gpio_monitor_socket = config.get('daemon_config', 'gpio_monitor_socket', '/tmp/gpio_get.sock')
        self.ht1621_socket = config.get('daemon_config', 'ht1621_socket', '/tmp/ht1621.sock')
        self.keyboard_monitor_socket = config.get('daemon_config', 'keyboard_monitor_socket', '/tmp/keyboard_get.sock')

        # Socket对象
        self.gpio_control_sock = None  # UDP
        self.gpio_monitor_sock = None  # TCP
        self.ht1621_sock = None  # UDP
        self.keyboard_monitor_sock = None  # UDP

        # 事件队列
        self.gpio_events = Queue()
        self.keyboard_events = Queue()

        # 运行标志
        self.running = False

        # 线程
        self.gpio_monitor_thread = None
        self.keyboard_monitor_thread = None

    def connect(self):
        """连接所有Socket"""
        self.logger.info("正在连接Socket...")

        # 连接GPIO控制Socket (UDP)
        self._connect_udp_socket(self.gpio_control_socket, 'gpio_control')

        # 连接GPIO监听Socket (TCP)
        self._connect_tcp_socket(self.gpio_monitor_socket, 'gpio_monitor')

        # 连接HT1621 Socket (UDP)
        self._connect_udp_socket(self.ht1621_socket, 'ht1621')

        # 连接键盘监听Socket (UDP)
        self._connect_udp_socket(self.keyboard_monitor_socket, 'keyboard_monitor')

        self.logger.info("所有Socket连接成功")
    
    def set_keyboard_handler(self, keyboard_handler):
        """
        设置键盘处理器

        Args:
            keyboard_handler: KeyboardHandler实例
        """
        self.keyboard_handler = keyboard_handler
        self.logger.info("键盘处理器已设置")
        # 处理在设置处理器之前已经接收到的键盘事件
        import queue
        temp_events = []
        while True:
            try:
                event = self.keyboard_events.get_nowait()
                temp_events.append(event)
            except queue.Empty:
                break
        
        for event in temp_events:
            self.keyboard_handler.handle_key_event(event)

    def _connect_udp_socket(self, socket_path, name):
        """连接UDP Socket"""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            
            # 对于keyboard_monitor，使用bind而不是connect
            # 因为daemon_keyboard需要客户端有明确的地址才能广播消息
            if name == 'keyboard_monitor':
                import os
                temp_socket_path = f"{socket_path}_client_{os.getpid()}"
                if os.path.exists(temp_socket_path):
                    os.unlink(temp_socket_path)
                sock.bind(temp_socket_path)
                os.chmod(temp_socket_path, 0o777)
                self.logger.info(f"{name} UDP Socket绑定成功: {temp_socket_path} -> {socket_path}")
            else:
                sock.connect(socket_path)
                self.logger.info(f"{name} UDP Socket连接成功: {socket_path}")
            
            setattr(self, f'{name}_sock', sock)
        except Exception as e:
            self.logger.error(f"{name} UDP Socket连接失败: {e}")
            raise

    def _connect_tcp_socket(self, socket_path, name):
        """连接TCP Socket"""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(socket_path)
            setattr(self, f'{name}_sock', sock)
            self.logger.info(f"{name} TCP Socket连接成功: {socket_path}")
        except Exception as e:
            self.logger.error(f"{name} TCP Socket连接失败: {e}")
            raise

    def disconnect(self):
        """断开所有Socket连接"""
        self.logger.info("正在断开Socket连接...")

        self.running = False

        # 关闭所有Socket
        socks = ['gpio_control_sock', 'gpio_monitor_sock', 'ht1621_sock', 'keyboard_monitor_sock']
        for sock_name in socks:
            sock = getattr(self, sock_name, None)
            if sock:
                try:
                    sock.close()
                except Exception as e:
                    self.logger.error(f"关闭{sock_name}失败: {e}")

        # 清理keyboard_monitor的临时socket文件
        import os
        temp_socket_path = f"{self.keyboard_monitor_socket}_client_{os.getpid()}"
        if os.path.exists(temp_socket_path):
            try:
                os.unlink(temp_socket_path)
            except Exception as e:
                self.logger.error(f"清理临时socket文件失败: {e}")

        # 等待线程结束
        if self.gpio_monitor_thread and self.gpio_monitor_thread.is_alive():
            self.gpio_monitor_thread.join(timeout=2)
        if self.keyboard_monitor_thread and self.keyboard_monitor_thread.is_alive():
            self.keyboard_monitor_thread.join(timeout=2)

        self.logger.info("所有Socket已断开")

    def start_monitoring(self):
        """启动监听线程"""
        self.running = True

        # 启动GPIO监听线程
        self.gpio_monitor_thread = threading.Thread(
            target=self._gpio_monitor_loop,
            name='GPIOMonitor',
            daemon=True
        )
        self.gpio_monitor_thread.start()

        # 启动键盘监听线程
        self.keyboard_monitor_thread = threading.Thread(
            target=self._keyboard_monitor_loop,
            name='KeyboardMonitor',
            daemon=True
        )
        self.keyboard_monitor_thread.start()

        self.logger.info("监听线程已启动")

    def _gpio_monitor_loop(self):
        """GPIO监听循环"""
        self.logger.info("GPIO监听线程启动")

        # 查询初始状态
        self._query_gpio_status()

        while self.running:
            try:
                # 使用select检查是否有数据可读
                readable, _, _ = select.select([self.gpio_monitor_sock], [], [], 1.0)

                if readable:
                    # 接收数据
                    data = self.gpio_monitor_sock.recv(4096)
                    if not data:
                        self.logger.warning("GPIO监听Socket连接断开")
                        break

                    # 解析JSON
                    try:
                        messages = self._parse_json_messages(data.decode('utf-8'))
                        for msg in messages:
                            self._handle_gpio_message(msg)
                    except json.JSONDecodeError as e:
                        self.logger.error(f"解析GPIO消息失败: {e}")

            except Exception as e:
                self.logger.error(f"GPIO监听错误: {e}")

        self.logger.info("GPIO监听线程退出")

    def _keyboard_monitor_loop(self):
        """键盘监听循环"""
        self.logger.info("键盘监听线程启动")

        # 查询初始状态
        self._query_keyboard_status()

        while self.running:
            try:
                # 接收数据
                data, _ = self.keyboard_monitor_sock.recvfrom(4096)
                if not data:
                    continue

                # 解析JSON
                try:
                    msg = json.loads(data.decode('utf-8'))
                    self._handle_keyboard_message(msg)
                except json.JSONDecodeError as e:
                    self.logger.error(f"解析键盘消息失败: {e}")

            except Exception as e:
                self.logger.error(f"键盘监听错误: {e}")

        self.logger.info("键盘监听线程退出")

    def _parse_json_messages(self, data):
        """解析可能粘连的JSON消息"""
        messages = []
        buffer = data.strip()

        while buffer:
            try:
                # 尝试解析第一个JSON对象
                msg = json.loads(buffer)
                messages.append(msg)
                break
            except json.JSONDecodeError:
                # 如果失败，尝试找到下一个可能的JSON开始位置
                idx = buffer.find('{"type":')
                if idx > 0:
                    # 添加之前的部分（可能是完整消息）
                    try:
                        msg = json.loads(buffer[:idx])
                        messages.append(msg)
                        buffer = buffer[idx:]
                    except:
                        break
                else:
                    break

        return messages

    def _handle_gpio_message(self, msg):
        """处理GPIO消息"""
        msg_type = msg.get('type')

        if msg_type == 'gpio_change':
            # GPIO状态变化事件
            self.gpio_events.put(msg)
            self.logger.debug(f"GPIO事件: {msg}")

            # 发送ACK确认
            if 'id' in msg:
                self._send_gpio_ack(msg['id'])

        elif msg_type == 'current_status':
            # 当前GPIO状态
            self.gpio_events.put(msg)
            self.logger.debug(f"GPIO状态: {msg}")

    def _handle_keyboard_message(self, msg):
        """处理键盘消息"""
        msg_type = msg.get('type')

        # 发送ACK确认
        if 'id' in msg:
            self._send_keyboard_ack(msg['id'])

        if msg_type == 'key_event':
            # 键盘事件 - 直接传递给键盘处理器
            if self.debug_keyboard:
                self.logger.info(f"键盘事件: {msg}")
            
            if hasattr(self, 'keyboard_handler') and self.keyboard_handler:
                self.keyboard_handler.handle_key_event(msg)
                if self.debug_keyboard:
                    self.logger.info(f"键盘事件已传递给处理器: {msg.get('key', 'N/A')}")
            else:
                # 如果没有键盘处理器，存储在队列中供后续处理
                self.keyboard_events.put(msg)
                if self.debug_keyboard:
                    self.logger.info(f"键盘处理器未设置，事件已暂存: {msg.get('key', 'N/A')}")
            
            self.logger.debug(f"键盘事件: {msg}")

        elif msg_type == 'current_status':
            # 当前键盘状态
            self.keyboard_events.put(msg)
            if self.debug_keyboard:
                self.logger.info(f"键盘状态: {msg}")
            self.logger.debug(f"键盘状态: {msg}")

    def _send_gpio_ack(self, msg_id):
        """发送GPIO ACK确认"""
        ack_msg = {
            'type': 'ack',
            'id': msg_id
        }
        try:
            self.gpio_monitor_sock.send(json.dumps(ack_msg).encode('utf-8'))
        except Exception as e:
            self.logger.error(f"发送GPIO ACK失败: {e}")

    def _send_keyboard_ack(self, msg_id):
        """发送键盘ACK确认"""
        ack_msg = {
            'type': 'ack',
            'id': msg_id
        }
        try:
            self.keyboard_monitor_sock.sendto(
                json.dumps(ack_msg).encode('utf-8'),
                self.keyboard_monitor_socket
            )
        except Exception as e:
            self.logger.error(f"发送键盘ACK失败: {e}")

    def _query_gpio_status(self):
        """查询GPIO状态"""
        query_msg = {
            'type': 'query_status'
        }
        try:
            self.gpio_monitor_sock.send(json.dumps(query_msg).encode('utf-8'))
            self.logger.info("已发送GPIO状态查询请求")
        except Exception as e:
            self.logger.error(f"发送GPIO状态查询失败: {e}")

    def _query_keyboard_status(self):
        """查询键盘状态"""
        query_msg = {
            'type': 'query_status'
        }
        try:
            self.keyboard_monitor_sock.sendto(
                json.dumps(query_msg).encode('utf-8'),
                self.keyboard_monitor_socket
            )
            self.logger.info("已发送键盘状态查询请求")
        except Exception as e:
            self.logger.error(f"发送键盘状态查询失败: {e}")

    def send_gpio_control(self, gpio, value):
        """
        发送GPIO控制命令

        Args:
            gpio: GPIO编号
            value: 值 (0或1)
        """
        msg = {
            'alias': 'sender',
            'mode': 'set',
            'gpio': gpio,
            'value': value
        }
        try:
            self.gpio_control_sock.send(json.dumps(msg).encode('utf-8'))
            self.logger.debug(f"发送GPIO控制: {msg}")
        except Exception as e:
            self.logger.error(f"发送GPIO控制失败: {e}")

    def send_gpio_batch(self, gpios, values):
        """
        批量发送GPIO控制命令

        Args:
            gpios: GPIO编号列表
            values: 值列表
        """
        msg = {
            'alias': 'sender',
            'mode': 'set',
            'gpios': gpios,
            'values': values
        }
        try:
            self.gpio_control_sock.send(json.dumps(msg).encode('utf-8'))
            self.logger.debug(f"发送GPIO批量控制: {msg}")
        except Exception as e:
            self.logger.error(f"发送GPIO批量控制失败: {e}")

    def send_lcd_display(self, device_id, display_data):
        """
        发送LCD显示命令（新格式）

        Args:
            device_id: 设备ID (1=外卖员侧, 2=学生侧)
            display_data: 显示数据
        """
        # 如果display_data是'init'，使用新格式的init命令，否则使用display_data命令
        if display_data == 'init':
            msg = {
                'device_id': device_id,
                'command': 'init'
            }
        else:
            msg = {
                'device_id': device_id,
                'command': 'display_data',
                'display_data': display_data
            }
        
        try:
            self.ht1621_sock.send(json.dumps(msg).encode('utf-8'))
            self.logger.info(f"发送LCD显示: {msg}")
        except Exception as e:
            self.logger.error(f"发送LCD显示失败: {e}")
    
    def send_lcd_command(self, device_id, command, display_data=None):
        """
        发送LCD命令

        Args:
            device_id: 设备ID (1=外卖员侧, 2=学生侧)
            command: 命令类型 ('init', 'display_data', 'LCD_display_on', 'LCD_display_off', 'LCD_sys_on', 'LCD_sys_off')
            display_data: 显示数据（可选，仅在command='display_data'时使用）
        """
        msg = {
            'device_id': device_id,
            'command': command
        }
        
        if display_data is not None:
            msg['display_data'] = display_data
        
        try:
            self.ht1621_sock.send(json.dumps(msg).encode('utf-8'))
            self.logger.info(f"发送LCD命令: {msg}")
        except Exception as e:
            self.logger.error(f"发送LCD命令失败: {e}")

    def get_gpio_events(self):
        """获取GPIO事件"""
        events = []
        while not self.gpio_events.empty():
            try:
                events.append(self.gpio_events.get_nowait())
            except:
                break
        return events

    def get_keyboard_events(self):
        """获取键盘事件"""
        events = []
        while not self.keyboard_events.empty():
            try:
                events.append(self.keyboard_events.get_nowait())
            except:
                break
        return events