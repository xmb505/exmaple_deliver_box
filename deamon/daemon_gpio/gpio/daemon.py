#!/usr/bin/env python3
"""
GPIO 控制守护进程核心模块
处理Unix Socket通信、GPIO监控、SPI队列等核心逻辑
"""

import json
import socket
import threading
import time
import configparser
import os
import select
import queue
import re


class GPIOControlDaemon:
    """GPIO控制守护进程"""

    def __init__(self, config_path, simulate=False, debug_spi=False):
        self.config = configparser.ConfigParser()
        self.config.read(config_path)

        self.simulate = simulate
        self.debug_spi = debug_spi

        # 控制器
        self.controllers = {}
        self.controller_configs = {}

        # GPIO状态变化缓冲区
        self.gpio_change_buffer = {}
        self.gpio_change_buffer_lock = threading.Lock()
        self.gpio_change_buffer_last_send = time.time()
        self.gpio_change_buffer_send_interval = 0.05

        # 消息ID
        self.message_id_counter = 0
        self.message_id_lock = threading.Lock()

        # GPIO状态跟踪
        self.current_gpio_states = {}

        # 初始化控制器
        self._init_controllers()

        # Socket初始化
        self._init_sockets()

        # SPI队列
        self.spi_queue = queue.Queue()
        self.spi_processing_lock = threading.Lock()
        self.spi_worker_thread = None

        # HTTP/WebSocket配置
        self.http_port = self.config.getint('daemon_config', 'http_port', fallback=0)
        self.http_server = None
        self.http_thread = None
        self.ws_port = self.config.getint('daemon_config', 'ws_port', fallback=0)
        self.ws_server = None
        self.ws_thread = None
        self.ws_clients = []
        self.ws_clients_lock = threading.Lock()

        # GPIO监控状态
        self.gpio_default_states = {}
        self.gpio_last_states = {}
        self.gpio_reporting_active = set()

        self.running = True

        print(f"GPIO守护进程初始化完成 (模拟模式: {simulate}, 调试SPI: {debug_spi})")

    def _init_controllers(self):
        """初始化USB GPIO控制器"""
        from .controller import USBGPIOController

        for section_name in self.config.sections():
            if section_name == 'daemon_config':
                continue

            tty_path = self.config.get(section_name, 'tty_path')
            baudrate = self.config.getint(section_name, 'baudrate', fallback=115200)
            alias = self.config.get(section_name, 'alias')
            mode = self.config.get(section_name, 'mode')

            controller_config = {
                'mode': mode,
                'config': dict(self.config.items(section_name))
            }

            # SPI模式提取引脚配置
            if mode == 'spi':
                spi_pins = {}
                for key, value in controller_config['config'].items():
                    if key in ('clk', 'data') or key.startswith('cs_'):
                        clean_value = value.split('#')[0].strip()
                        if clean_value:
                            try:
                                spi_pins[key] = int(clean_value)
                            except ValueError:
                                print(f"警告: 无法将 '{key}' 的值 '{value}' 转换为整数")
                controller_config['spi_pins'] = spi_pins

            # /dev/null 表示暂不可用
            if tty_path == '/dev/null':
                print(f"设备 {alias} 配置为 /dev/null，跳过初始化")
                self.controller_configs[alias] = controller_config
                continue

            try:
                controller = USBGPIOController(tty_path, baudrate, simulate=self.simulate)
                self.controllers[alias] = controller
                self.controller_configs[alias] = controller_config
            except Exception as e:
                if not self.simulate:
                    print(f"初始化控制器 {alias} 失败: {e}")
                    print("尝试使用模拟模式...")
                    try:
                        controller = USBGPIOController(tty_path, baudrate, simulate=True)
                        self.controllers[alias] = controller
                        self.controller_configs[alias] = controller_config
                    except Exception as e2:
                        print(f"即使在模拟模式下初始化控制器 {alias} 也失败: {e2}")
                        self.controller_configs[alias] = controller_config
                else:
                    print(f"初始化控制器 {alias} 失败: {e}")
                    self.controller_configs[alias] = controller_config

    def _init_sockets(self):
        """初始化Unix Socket"""
        # 控制Socket
        socket_path = self.config.get('daemon_config', 'socket_path', fallback='/tmp/gpio.sock')
        if os.path.exists(socket_path):
            os.unlink(socket_path)
        self.control_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.control_socket.bind(socket_path)
        os.chmod(socket_path, 0o777)

        # 状态监听Socket
        get_status_path = self.config.get('daemon_config', 'get_statu_path', fallback='/tmp/gpio_get.sock')
        if os.path.exists(get_status_path):
            os.unlink(get_status_path)
        self.status_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.status_socket.bind(get_status_path)
        self.status_socket.listen(10)
        os.chmod(get_status_path, 0o777)

        self.status_clients = []
        self.status_clients_lock = threading.Lock()

    # ==================== 命令处理 ====================

    def handle_control_command(self, data, addr):
        """处理控制命令"""
        try:
            command = json.loads(data.decode('utf-8'))
            alias = command.get('alias')
            mode = command.get('mode')

            if hasattr(self, 'debug') and self.debug:
                print(f"调试: 收到命令 - {command}")

            if alias not in self.controller_configs:
                print(f"错误: 未找到别名为 {alias} 的控制器")
                return

            if alias not in self.controllers:
                print(f"错误: 设备 {alias} 暂不可用（未初始化）")
                return

            controller = self.controllers[alias]
            controller_config = self.controller_configs[alias]

            if mode == 'set':
                self._handle_set_command(command, controller)
            elif mode in ('spi', 'spi_multi') and controller_config['mode'] == 'spi':
                self._handle_spi_command(command, controller)

        except json.JSONDecodeError:
            print("错误: 无法解析JSON命令")
        except Exception as e:
            print(f"处理控制命令时发生错误: {e}")

    def _handle_set_command(self, command, controller):
        """处理set命令"""
        if 'gpio' in command and 'value' in command:
            controller.set_gpio({command['gpio']: command['value']})
        elif 'gpios' in command and 'values' in command:
            gpios = command['gpios']
            values = command['values']
            if len(gpios) != len(values):
                print("错误: gpios数组和values数组长度不匹配")
                return
            gpio_states = dict(zip(gpios, values))
            controller.set_gpio(gpio_states)

    def _handle_spi_command(self, command, controller):
        """处理SPI命令"""
        if 'alias' not in command:
            return

        controller_config = self.controller_configs[command['alias']]
        spi_task = {
            'controller': controller,
            'config': controller_config,
            'command': command
        }
        self.spi_queue.put(spi_task)

    # ==================== SPI队列处理 ====================

    def start_spi_worker(self):
        """启动SPI工作线程"""
        self.spi_worker_thread = threading.Thread(target=self.process_spi_queue, daemon=True)
        self.spi_worker_thread.start()
        print("SPI工作线程已启动")

    def process_spi_queue(self):
        """处理SPI队列中的任务"""
        while self.running:
            try:
                spi_task = self.spi_queue.get(timeout=1.0)

                # 获取延迟配置
                controller_alias = spi_task['command']['alias']
                controller_config = self.controller_configs[controller_alias]
                try:
                    lag_time_ms = float(controller_config.get('config', {}).get('lag_time', 1.0))
                    if lag_time_ms <= 0:
                        lag_time_ms = 1.0
                except (ValueError, TypeError):
                    lag_time_ms = 1.0
                lag_time = lag_time_ms / 1000.0

                with self.spi_processing_lock:
                    command = spi_task['command']
                    controller = spi_task['controller']
                    controller_config = spi_task['config']

                    clk_pin = controller_config['spi_pins'].get('clk')
                    data_pin = controller_config['spi_pins'].get('data')

                    if not clk_pin or not data_pin:
                        print("错误: 未找到共享的clk或data引脚配置")
                        self.spi_queue.task_done()
                        continue

                    if command['mode'] == 'spi':
                        self._process_single_spi(command, controller, clk_pin, data_pin, lag_time)
                    elif command['mode'] == 'spi_multi':
                        self._process_multi_spi(command, controller, clk_pin, data_pin, lag_time)

                self.spi_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                print(f"处理SPI队列时发生错误: {e}")

    def _process_single_spi(self, command, controller, clk_pin, data_pin, lag_time):
        """处理单路SPI"""
        spi_num = command.get('spi_num', 1)
        spi_data = command.get('spi_data', '')
        cs_collection = command.get('spi_data_cs_collection', 'down')

        controller_config = self.controller_configs[command['alias']]
        cs_pin = controller_config['spi_pins'].get(f'cs_{spi_num}')

        if cs_pin:
            controller.set_spi(clk_pin, data_pin, cs_pin, spi_data, cs_collection, lag_time, self.debug_spi)
        else:
            print(f"错误: 未找到SPI接口{spi_num}的片选引脚配置")

    def _process_multi_spi(self, command, controller, clk_pin, data_pin, lag_time):
        """处理多路SPI"""
        spis = command.get('spis', [])
        controller_config = self.controller_configs[command['alias']]

        for spi_config in spis:
            spi_num = spi_config.get('spi_num', 1)
            spi_data = spi_config.get('spi_data', '')
            cs_collection = spi_config.get('spi_data_cs_collection', 'down')
            cs_pin = controller_config['spi_pins'].get(f'cs_{spi_num}')

            if cs_pin:
                controller.set_spi(clk_pin, data_pin, cs_pin, spi_data, cs_collection, lag_time, self.debug_spi)

    # ==================== GPIO监控 ====================

    def start_gpio_monitoring(self):
        """启动GPIO状态监控线程"""
        for alias, config in self.controller_configs.items():
            if config['mode'] == 'geter':
                default_bit = int(config['config'].get('default_bit', 0))
                self.gpio_default_states[alias] = default_bit
                self.gpio_last_states[alias] = {}

        for alias, controller in self.controllers.items():
            if self.controller_configs[alias]['mode'] == 'geter':
                self._init_geter_controller(alias, controller)

        while self.running:
            try:
                current_time = time.time()
                if current_time - self.gpio_change_buffer_last_send >= self.gpio_change_buffer_send_interval:
                    self.send_buffered_gpio_status()
                    self.gpio_change_buffer_last_send = current_time

                    time_since_last_send = time.time() - self.gpio_change_buffer_last_send
                    wait_time = max(0.01, self.gpio_change_buffer_send_interval - time_since_last_send)
                    time.sleep(wait_time)
                else:
                    remaining_time = self.gpio_change_buffer_send_interval - (current_time - self.gpio_change_buffer_last_send)
                    wait_time = max(0.01, remaining_time)
                    time.sleep(wait_time)
            except Exception as e:
                print(f"GPIO监控主线程发生错误: {e}")
                time.sleep(1)

    def _init_geter_controller(self, alias, controller):
        """初始化geter控制器并启动监听"""
        default_bit = self.gpio_default_states.get(alias, 0)

        if not controller.simulate:
            if not controller.ser or not controller.ser.is_open:
                try:
                    controller.reconnect()
                except:
                    return

            if default_bit == 0:
                command = bytearray([0x3E, 0xFF])  # 3E指令（拉低模式）
            else:
                command = bytearray([0x3D, 0xFF])  # 3D指令（拉高模式）

            try:
                controller.ser.write(command)
                print(f"已发送GPIO持续上报指令到 {alias} 设备 (default_bit={default_bit})")
                self.gpio_reporting_active.add(alias)
            except Exception as e:
                print(f"发送GPIO持续上报指令失败: {e}")
        else:
            self.gpio_reporting_active.add(alias)

        if not controller.simulate:
            thread = threading.Thread(
                target=self.listen_gpio_controller,
                args=(alias, controller, default_bit),
                daemon=True
            )
            thread.start()
        else:
            thread = threading.Thread(
                target=self.simulate_gpio_controller,
                args=(alias, controller, default_bit),
                daemon=True
            )
            thread.start()

    def listen_gpio_controller(self, alias, controller, default_bit):
        """监听单个GPIO控制器的数据上报"""
        print(f"开始监听GPIO控制器: {alias}")

        while self.running:
            try:
                ready, _, _ = select.select([controller.ser], [], [], 0.1)

                if ready:
                    response_data = controller.ser.read(controller.ser.in_waiting)

                    if response_data:
                        response_str = response_data.decode('ascii', errors='ignore')
                        response_str = response_str.replace('\n', '').replace('\r', '').strip()
                        controller.data_buffer += response_str

                        matches = re.findall(r'CH(\d+):([01])', controller.data_buffer)

                        if matches:
                            gpio_states = {}
                            for gpio_num, state in matches:
                                gpio_num = int(gpio_num)
                                state = int(state)
                                gpio_states[gpio_num] = state

                            if alias not in self.current_gpio_states:
                                self.current_gpio_states[alias] = {}
                            self.current_gpio_states[alias].update(gpio_states)

                            # 清理缓冲区
                            last_match_end = 0
                            for match in re.finditer(r'CH(\d+):([01])', controller.data_buffer):
                                last_match_end = match.end()
                            if last_match_end > 0:
                                controller.data_buffer = controller.data_buffer[last_match_end:]

                            self._process_gpio_states(alias, default_bit, gpio_states)

            except Exception as e:
                print(f"监听GPIO控制器 {alias} 时发生错误: {e}")
                try:
                    controller.reconnect()
                    self.gpio_reporting_active.discard(alias)
                except:
                    pass

    def simulate_gpio_controller(self, alias, controller, default_bit):
        """模拟GPIO控制器的数据上报"""
        import random

        while self.running:
            time.sleep(0.1)

            gpio_states = {}
            for gpio_pin in range(1, 17):
                gpio_states[gpio_pin] = random.randint(0, 1)

            if alias not in self.current_gpio_states:
                self.current_gpio_states[alias] = {}
            self.current_gpio_states[alias].update(gpio_states)

            self._process_gpio_states(alias, default_bit, gpio_states)

    def _process_gpio_states(self, alias, default_bit, gpio_states):
        """处理GPIO状态变化"""
        for gpio_pin, current_state in gpio_states.items():
            last_state = self.gpio_last_states[alias].get(gpio_pin)

            if last_state is not None and last_state != current_state:
                status_data = {
                    "gpios": [{
                        "alias": alias,
                        "default_bit": default_bit,
                        "change_gpio": [{
                            "gpio": gpio_pin,
                            "bit": current_state
                        }]
                    }]
                }
                self.broadcast_gpio_status(status_data)

            self.gpio_last_states[alias][gpio_pin] = current_state

    # ==================== 状态广播 ====================

    def get_next_message_id(self):
        """获取下一个消息ID"""
        with self.message_id_lock:
            self.message_id_counter += 1
            return self.message_id_counter

    def broadcast_gpio_status(self, status_data):
        """将GPIO状态变化添加到缓冲区并广播"""
        with self.gpio_change_buffer_lock:
            for gpio_info in status_data.get('gpios', []):
                alias = gpio_info.get('alias')
                if alias not in self.gpio_change_buffer:
                    self.gpio_change_buffer[alias] = []
                self.gpio_change_buffer[alias].append(gpio_info)

        self.ws_broadcast(status_data)

    def ws_broadcast(self, status_data):
        """通过 WebSocket 广播 GPIO 状态变化"""
        if not hasattr(self, 'ws_clients') or not self.ws_clients:
            return

        message_id = self.get_next_message_id()
        message = {
            "type": "gpio_change",
            "id": message_id,
            "timestamp": time.time(),
            **status_data
        }
        json_data = json.dumps(message)
        frame = self.encode_ws_frame(json_data)

        with self.ws_clients_lock:
            disconnected = []
            for client in self.ws_clients:
                try:
                    client.send(frame)
                except:
                    disconnected.append(client)
            for client in disconnected:
                self.ws_clients.remove(client)

    def encode_ws_frame(self, data):
        """编码 WebSocket 帧"""
        payload = data.encode('utf-8')
        payload_len = len(payload)

        if payload_len <= 125:
            header = bytes([0x81, payload_len])
        elif payload_len <= 65535:
            header = bytes([0x81, 126, (payload_len >> 8) & 0xFF, payload_len & 0xFF])
        else:
            header = bytes([0x81, 127]) + payload_len.to_bytes(8, 'big')

        return header + payload

    def send_buffered_gpio_status(self):
        """发送缓冲区中的GPIO状态变化"""
        with self.gpio_change_buffer_lock:
            if not self.gpio_change_buffer:
                return

            combined_status_data = {"gpios": []}
            for alias, changes in self.gpio_change_buffer.items():
                combined_changes = {
                    "alias": alias,
                    "default_bit": changes[0].get('default_bit', 0),
                    "change_gpio": []
                }
                for change in changes:
                    combined_changes["change_gpio"].extend(change.get('change_gpio', []))
                combined_status_data["gpios"].append(combined_changes)

            self.gpio_change_buffer.clear()

        message_id = self.get_next_message_id()
        message_data = {
            "type": "gpio_change",
            "id": message_id,
            "timestamp": time.time(),
            **combined_status_data
        }

        with self.status_clients_lock:
            disconnected_clients = []
            for client in self.status_clients:
                try:
                    client.send(json.dumps(message_data).encode('utf-8'))
                except Exception as e:
                    print(f"向客户端发送状态失败: {e}")
                    disconnected_clients.append(client)

            for client in disconnected_clients:
                if client in self.status_clients:
                    self.status_clients.remove(client)
                try:
                    client.close()
                except:
                    pass

    def get_current_gpio_status(self):
        """获取当前所有GPIO的状态"""
        current_status = {
            "type": "current_status",
            "timestamp": time.time(),
            "gpios": []
        }

        for alias, config in self.controller_configs.items():
            if config['mode'] == 'geter':
                default_bit = self.gpio_default_states.get(alias, 0)
                available = alias in self.controllers

                current_gpio_states = {}
                if available:
                    current_gpio_states = self.current_gpio_states.get(alias, {}).copy()
                    if not current_gpio_states and alias in self.gpio_last_states:
                        current_gpio_states = self.gpio_last_states[alias].copy()

                current_status["gpios"].append({
                    "alias": alias,
                    "default_bit": default_bit,
                    "available": available,
                    "current_gpio_states": current_gpio_states
                })

        return current_status

    # ==================== 状态客户端处理 ====================

    def handle_status_client(self, client_socket, client_addr):
        """处理状态监听客户端"""
        print(f"新的状态监听客户端连接: {client_addr}")

        with self.status_clients_lock:
            self.status_clients.append(client_socket)

        try:
            while self.running:
                try:
                    client_socket.settimeout(1.0)
                    data = client_socket.recv(1024)
                    if not data:
                        break

                    try:
                        client_msg = json.loads(data.decode('utf-8'))

                        if client_msg.get('type') == 'ack':
                            ack_id = client_msg.get('id')
                            print(f"收到客户端ACK: {ack_id}")

                        elif client_msg.get('type') == 'query_status':
                            current_status = self.get_current_gpio_status()
                            client_socket.send(json.dumps(current_status).encode('utf-8'))

                    except json.JSONDecodeError:
                        pass

                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"接收客户端消息时出错: {e}")
                    break

        except Exception as e:
            print(f"状态监听客户端处理错误: {e}")
        finally:
            with self.status_clients_lock:
                if client_socket in self.status_clients:
                    self.status_clients.remove(client_socket)
            try:
                client_socket.close()
            except:
                pass
            print(f"状态监听客户端断开: {client_addr}")

    def start_status_server(self):
        """启动状态监听服务器"""
        while self.running:
            try:
                client_socket, addr = self.status_socket.accept()
                client_thread = threading.Thread(
                    target=self.handle_status_client,
                    args=(client_socket, addr),
                    daemon=True
                )
                client_thread.start()
            except Exception as e:
                if self.running:
                    print(f"接受状态监听连接时发生错误: {e}")

    # ==================== HTTP服务器 ====================

    def start_http_server(self):
        """启动HTTP服务器"""
        from .server_http import HTTPRequestHandler
        from http.server import HTTPServer

        HTTPRequestHandler.daemon = self
        self.http_server = HTTPServer(('0.0.0.0', self.http_port), HTTPRequestHandler)
        self.http_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
        self.http_thread.start()
        print(f"HTTP服务器已启动，监听端口 {self.http_port}")

    # ==================== WebSocket服务器 ====================

    def start_ws_server(self):
        """启动WebSocket服务器"""
        from .server_ws import WebSocketServer

        self.ws_server = WebSocketServer(self.ws_port, self.ws_clients, self.ws_clients_lock)
        self.ws_thread = threading.Thread(target=self.ws_server.run, daemon=True)
        self.ws_thread.start()
        print(f"WebSocket服务器已启动，监听端口 {self.ws_port}")

    # ==================== 主循环 ====================

    def run(self):
        """运行守护进程"""
        print("GPIO守护进程启动...")

        self.start_spi_worker()

        status_thread = threading.Thread(target=self.start_status_server, daemon=True)
        status_thread.start()

        gpio_monitor_thread = threading.Thread(target=self.start_gpio_monitoring, daemon=True)
        gpio_monitor_thread.start()

        if self.http_port > 0:
            self.start_http_server()

        if self.ws_port > 0:
            self.start_ws_server()

        while self.running:
            try:
                ready_sockets, _, _ = select.select([self.control_socket], [], [], 1.0)

                for sock in ready_sockets:
                    if sock == self.control_socket:
                        data, addr = sock.recvfrom(1024)
                        if data:
                            command_thread = threading.Thread(
                                target=self.handle_control_command,
                                args=(data, addr),
                                daemon=True
                            )
                            command_thread.start()

            except KeyboardInterrupt:
                print("接收到中断信号")
                self.stop()
                break
            except Exception as e:
                print(f"守护进程运行时发生错误: {e}")

        self.stop()

    def stop(self):
        """停止守护进程"""
        print("正在停止GPIO守护进程...")
        self.running = False

        try:
            self.spi_queue.join()
        except:
            pass

        try:
            self.control_socket.close()
        except:
            pass

        try:
            self.status_socket.close()
        except:
            pass

        with self.status_clients_lock:
            for client in self.status_clients:
                try:
                    client.close()
                except:
                    pass
            self.status_clients.clear()

        for controller in self.controllers.values():
            try:
                if controller.ser and controller.ser.is_open:
                    controller.ser.close()
            except:
                pass

        if self.http_server:
            try:
                self.http_server.shutdown()
            except:
                pass

        if self.ws_server:
            try:
                self.ws_server.running = False
            except:
                pass

        socket_path = self.config.get('daemon_config', 'socket_path', fallback='/tmp/gpio.sock')
        get_status_path = self.config.get('daemon_config', 'get_statu_path', fallback='/tmp/gpio_get.sock')

        try:
            if os.path.exists(socket_path):
                os.unlink(socket_path)
                print(f"已清理socket文件: {socket_path}")
        except:
            pass

        try:
            if os.path.exists(get_status_path):
                os.unlink(get_status_path)
                print(f"已清理socket文件: {get_status_path}")
        except:
            pass

        print("GPIO守护进程已停止")