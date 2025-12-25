#!/usr/bin/env python3
"""
键盘守护进程
监听键盘输入事件并通过Unix Socket广播
"""

import json
import socket
import threading
import time
import os
import select
import queue
from pathlib import Path
import configparser


def find_keyboard_devices():
    """
    自动查找系统中的键盘设备
    返回键盘设备路径列表
    """
    import glob
    
    keyboard_devices = []
    
    # 遍历所有输入事件设备
    for event_path in glob.glob('/dev/input/event*'):
        try:
            # 读取设备信息来判断是否为键盘
            device_name_path = event_path.replace('/dev/input/', '/sys/class/input/') + '/device/name'
            if os.path.exists(device_name_path):
                with open(device_name_path, 'r') as f:
                    device_name = f.read().strip().lower()
                    
                # 检查设备名称是否包含键盘相关关键词
                if any(keyword in device_name for keyword in ['keyboard', 'key', 'atkbd', 'usb keyboard', 'usbkeyboard']):
                    keyboard_devices.append(event_path)
                    print(f"发现键盘设备: {event_path} ({device_name})")
        
        except Exception:
            # 如果无法读取设备信息，跳过该设备
            continue
    
    if not keyboard_devices:
        print("警告: 未找到键盘设备，将尝试使用默认设备 /dev/input/event0")
        keyboard_devices = ['/dev/input/event0']
    
    return keyboard_devices


class KeyboardEventDaemon:
    """键盘事件守护进程"""
    
    def __init__(self, config_path, simulate=False):
        self.config = configparser.ConfigParser()
        self.config.read(config_path)
        
        # 是否使用模拟模式
        self.simulate = simulate
        
        # 存储当前按键状态（跟踪所有按键的按下/释放状态）
        self.current_keys = {}  # {key_name: state}，state为True表示按下，False表示释放
        
        # 存储当前按键状态时间戳
        self.current_keys_timestamp = {}
        
        # 自动查找键盘设备
        self.keyboard_devices = find_keyboard_devices()
        
        # 创建控制Socket
        socket_path = self.config.get('daemon_config', 'socket_path', fallback='/tmp/keyboard.sock')
        if os.path.exists(socket_path):
            os.unlink(socket_path)
        
        self.control_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.control_socket.bind(socket_path)
        os.chmod(socket_path, 0o777)  # 设置权限以便其他进程访问
        
        # 创建状态监听Socket（改为UDP以支持广播）
        get_status_path = self.config.get('daemon_config', 'get_statu_path', fallback='/tmp/keyboard_get.sock')
        if os.path.exists(get_status_path):
            os.unlink(get_status_path)
        
        self.status_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)  # 改为UDP
        self.status_socket.bind(get_status_path)
        os.chmod(get_status_path, 0o777)
        
        # 存储客户端地址（用于回复查询）
        self.client_addresses = set()
        self.client_addresses_lock = threading.Lock()
        
        # 键盘事件队列
        self.key_event_queue = queue.Queue()
        
        # 消息ID计数器
        self.message_id_counter = 0
        self.message_id_lock = threading.Lock()
        
        # 运行标志
        self.running = True
        
        print(f"键盘守护进程初始化完成 (模拟模式: {simulate})")
        print(f"发现 {len(self.keyboard_devices)} 个键盘设备: {self.keyboard_devices}")
    
    def get_next_message_id(self):
        """获取下一个消息ID"""
        with self.message_id_lock:
            self.message_id_counter += 1
            return self.message_id_counter
    
    def handle_control_command(self, data, addr):
        """处理控制命令"""
        try:
            command = json.loads(data.decode('utf-8'))
            # 目前键盘守护进程主要作用是监听和广播键盘事件
            # 可以扩展支持一些控制命令
            
        except json.JSONDecodeError:
            print("错误: 无法解析JSON命令")
        except Exception as e:
            print(f"处理控制命令时发生错误: {e}")
    
    def broadcast_key_event(self, event_data):
        """向所有已知的客户端广播键盘事件"""
        # 添加消息ID和时间戳
        message_id = self.get_next_message_id()
        
        # 创建包含当前所有按键状态的消息
        message_data = {
            "type": "key_event",
            "id": message_id,
            "timestamp": time.time(),
            "current_keys": dict(self.current_keys),  # 包含所有当前按键状态
            **{k: v for k, v in event_data.items() if k not in ['type', 'id', 'timestamp']}
        }
        
        with self.client_addresses_lock:
            disconnected_clients = []
            for addr in self.client_addresses:
                if addr is None:  # 跳过None地址
                    disconnected_clients.append(addr)
                    continue
                try:
                    self.status_socket.sendto(json.dumps(message_data).encode('utf-8'), addr)
                except Exception as e:
                    print(f"向客户端 {addr} 发送键盘事件失败: {e}")
                    disconnected_clients.append(addr)
            
            # 移除断开的客户端
            for addr in disconnected_clients:
                if addr in self.client_addresses:
                    self.client_addresses.remove(addr)
    
    def send_current_status(self, client_addr):
        """向指定客户端发送当前键盘状态"""
        # 确保client_addr不是None
        if client_addr is None:
            print("错误: 客户端地址为None，无法发送状态")
            return
            
        current_status = {
            "type": "current_status",
            "id": self.get_next_message_id(),
            "timestamp": time.time(),
            "current_keys": dict(self.current_keys),
            "current_keys_timestamp": dict(self.current_keys_timestamp)
        }
        
        try:
            self.status_socket.sendto(json.dumps(current_status).encode('utf-8'), client_addr)
            print(f"已向客户端 {client_addr} 发送当前键盘状态")
        except Exception as e:
            print(f"向客户端 {client_addr} 发送状态失败: {e}")
    
    def handle_status_messages(self):
        """处理状态监听端口的消息（客户端查询等）"""
        while self.running:
            try:
                data, addr = self.status_socket.recvfrom(1024)
                
                try:
                    # 解析客户端发送的消息
                    client_msg = json.loads(data.decode('utf-8'))
                    
                    # 记录客户端地址以便后续广播（仅在收到有效消息时）
                    with self.client_addresses_lock:
                        self.client_addresses.add(addr)
                    
                    # 处理ACK消息
                    if client_msg.get('type') == 'ack':
                        ack_id = client_msg.get('id')
                        # 可以在这里添加ACK处理逻辑
                        print(f"收到客户端ACK: {ack_id}")
                    
                    # 处理状态查询请求
                    elif client_msg.get('type') == 'query_status':
                        self.send_current_status(addr)
                        
                except json.JSONDecodeError:
                    # 不是JSON格式的消息，可能是其他协议
                    pass
                        
            except socket.timeout:
                # 超时是正常的，继续循环
                continue
            except Exception as e:
                # 可能是socket被关闭了
                if self.running:
                    print(f"接收客户端消息时出错: {e}")
                break
    
    def keyboard_monitoring(self):
        """键盘监控线程"""
        import random
        import string
        
        if self.simulate:
            # 模拟键盘事件
            while self.running:
                # 模拟键盘输入事件
                if random.random() < 0.3:  # 30% 概率触发事件
                    key_char = random.choice(string.ascii_letters + string.digits)
                    event_type = random.choice(['press', 'release'])
                    
                    # 更新当前按键状态
                    if event_type == 'press':
                        self.current_keys[key_char] = True
                        self.current_keys_timestamp[key_char] = time.time()
                    else:
                        self.current_keys[key_char] = False
                        if key_char in self.current_keys_timestamp:
                            del self.current_keys_timestamp[key_char]
                    
                    # 创建键盘事件数据
                    event_data = {
                        "event_type": event_type,
                        "key": key_char,
                        "timestamp": time.time()
                    }
                    
                    print(f"模拟键盘事件: {event_data}")
                    self.broadcast_key_event(event_data)
                
                time.sleep(1)
        else:
            # 使用evdev库监听实际键盘事件
            try:
                import struct
                import select
                
                # 打开所有检测到的键盘设备
                device_fds = []
                for device_path in self.keyboard_devices:
                    try:
                        fd = open(device_path, 'rb')
                        device_fds.append((fd, device_path))
                        print(f"已打开键盘设备: {device_path}")
                    except Exception as e:
                        print(f"无法打开设备 {device_path}: {e}")
                
                if not device_fds:
                    print("错误: 无法打开任何键盘设备")
                    return
                
                # 将所有设备文件描述符设置为非阻塞模式
                for fd, device_path in device_fds:
                    import fcntl
                    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
                
                # 使用select来同时监控所有设备
                while self.running:
                    # 等待设备输入
                    ready_fds, _, _ = select.select([fd for fd, _ in device_fds], [], [], 0.1)
                    
                    for ready_fd, device_path in device_fds:
                        if ready_fd in ready_fds:
                            # 一次性读取所有可用的数据
                            try:
                                # 持续读取直到没有更多数据
                                while True:
                                    try:
                                        # 读取输入事件 (Linux input event结构体: 24字节)
                                        data = ready_fd.read(24)
                                        if not data or len(data) < 24:
                                            break
                                        
                                        # 解析input_event结构体
                                        # struct input_event {
                                        #     struct timeval time;  // 16 bytes total (64位系统上是两个long)
                                        #     unsigned short type;  // 2 bytes
                                        #     unsigned short code;  // 2 bytes
                                        #     unsigned int value;   // 4 bytes
                                        # };
                                        # 总共24字节: 8 + 8 + 2 + 2 + 4 = 24
                                        tv_sec, tv_usec, event_type, code, value = struct.unpack('llHHi', data)
                                        
                                        # 检查是否是键盘事件
                                        if event_type == 1:  # EV_KEY
                                            # 尝试将键码转换为可读的键名
                                            key_name = self.get_key_name(code)
                                            
                                            # 确定事件类型
                                            if value == 1:
                                                event_type_str = "press"
                                                # 更新当前按键状态
                                                self.current_keys[key_name] = True
                                                self.current_keys_timestamp[key_name] = time.time()
                                            elif value == 0:
                                                event_type_str = "release"
                                                # 更新当前按键状态
                                                self.current_keys[key_name] = False
                                                if key_name in self.current_keys_timestamp:
                                                    del self.current_keys_timestamp[key_name]
                                            else:
                                                event_type_str = "repeat"
                                            
                                            # 创建键盘事件数据
                                            event_data = {
                                                "event_type": event_type_str,
                                                "key": key_name,
                                                "key_code": code,
                                                "device": device_path,
                                                "timestamp": time.time()
                                            }
                                            
                                            # 只广播按键按下和释放事件，忽略重复事件
                                            if event_type_str in ['press', 'release']:
                                                self.broadcast_key_event(event_data)
                                                print(f"键盘事件: {event_data}")
                                                
                                    except BlockingIOError:
                                        # 没有更多数据可读，跳出内部循环
                                        break
                                    except Exception as e:
                                        # 其他错误，可能设备已断开
                                        print(f"读取设备 {device_path} 时出错: {e}")
                                        break
                                        
                            except Exception as e:
                                # 设备可能已断开，尝试重新打开
                                print(f"读取设备 {device_path} 时出错: {e}")
                                try:
                                    ready_fd.close()
                                    # 尝试重新打开设备
                                    new_fd = open(device_path, 'rb')
                                    # 将新文件描述符也设为非阻塞
                                    import fcntl
                                    fl = fcntl.fcntl(new_fd, fcntl.F_GETFL)
                                    fcntl.fcntl(new_fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
                                    # 替换文件描述符
                                    for i, (fd, path) in enumerate(device_fds):
                                        if path == device_path:
                                            device_fds[i] = (new_fd, path)
                                            break
                                except Exception as reopen_error:
                                    print(f"重新打开设备 {device_path} 失败: {reopen_error}")
                                    # 从列表中移除该设备
                                    device_fds = [(fd, path) for fd, path in device_fds if path != device_path]
                
            except ImportError:
                print("错误: 未安装必要库，无法监听键盘事件")
                print("请运行: pip install evdev (可选)")
                # 作为备选方案，尝试使用keyboard库
                try:
                    import keyboard
                    
                    def on_key_event(event):
                        # 确定事件类型
                        if event.event_type == "down":
                            event_type_str = "press"
                            # 更新当前按键状态
                            self.current_keys[event.name] = True
                            self.current_keys_timestamp[event.name] = time.time()
                        elif event.event_type == "up":
                            event_type_str = "release"
                            # 更新当前按键状态
                            self.current_keys[event.name] = False
                            if event.name in self.current_keys_timestamp:
                                del self.current_keys_timestamp[event.name]
                        else:
                            event_type_str = event.event_type
                        
                        # 创建键盘事件数据
                        event_data = {
                            "event_type": event_type_str,
                            "key": event.name,
                            "timestamp": time.time()
                        }
                        
                        self.broadcast_key_event(event_data)
                        print(f"键盘事件: {event_data}")
                    
                    # 注册键盘事件监听器
                    keyboard.hook(on_key_event)
                    
                    # 保持线程运行
                    while self.running:
                        time.sleep(0.1)
                        
                except ImportError:
                    print("错误: 未安装keyboard库，无法监听键盘事件")
                    print("请运行: pip install keyboard")
                    time.sleep(5)  # 等待5秒后退出
                except Exception as e:
                    print(f"键盘监听错误: {e}")
                    time.sleep(1)  # 出错后等待1秒再重试
    
    def get_key_name(self, key_code):
        """将键码转换为可读的键名"""
        # Linux键码映射表（部分常用键）
        key_map = {
            1: 'ESC', 2: '1', 3: '2', 4: '3', 5: '4', 6: '5', 7: '6', 8: '7', 9: '8', 10: '9', 11: '0',
            12: '-', 13: '=', 14: 'BACKSPACE', 15: 'TAB', 16: 'q', 17: 'w', 18: 'e', 19: 'r', 20: 't',
            21: 'y', 22: 'u', 23: 'i', 24: 'o', 25: 'p', 26: '[', 27: ']', 28: 'ENTER', 29: 'LEFT_CTRL',
            30: 'a', 31: 's', 32: 'd', 33: 'f', 34: 'g', 35: 'h', 36: 'j', 37: 'k', 38: 'l', 39: ';',
            40: "'", 41: '`', 42: 'LEFT_SHIFT', 43: '\\', 44: 'z', 45: 'x', 46: 'c', 47: 'v', 48: 'b',
            49: 'n', 50: 'm', 51: ',', 52: '.', 53: '/', 54: 'RIGHT_SHIFT', 55: 'PRINT_SCREEN', 56: 'ALT',
            57: 'SPACE', 58: 'CAPS_LOCK', 59: 'F1', 60: 'F2', 61: 'F3', 62: 'F4', 63: 'F5', 64: 'F6',
            65: 'F7', 66: 'F8', 67: 'F9', 68: 'F10', 69: 'NUM_LOCK', 70: 'SCROLL_LOCK', 71: 'HOME', 72: 'UP',
            73: 'PAGE_UP', 74: 'MINUS', 75: 'LEFT', 76: 'CENTER', 77: 'RIGHT', 78: 'PLUS', 79: 'END',
            80: 'DOWN', 81: 'PAGE_DOWN', 82: 'INSERT', 83: 'DELETE', 86: '|', 87: 'F11', 88: 'F12'
        }
        
        return key_map.get(key_code, f'KEY_{key_code}')
    
    def run(self):
        """运行守护进程"""
        print("键盘守护进程启动...")
        
        # 启动状态消息处理线程（UDP）
        status_thread = threading.Thread(target=self.handle_status_messages, daemon=True)
        status_thread.start()
        
        # 启动键盘监控线程
        keyboard_thread = threading.Thread(target=self.keyboard_monitoring, daemon=True)
        keyboard_thread.start()
        
        # 主循环 - 处理控制命令
        while self.running:
            try:
                # 使用select来实现非阻塞的socket监听
                ready_sockets, _, _ = select.select([self.control_socket], [], [], 1.0)
                
                for sock in ready_sockets:
                    if sock == self.control_socket:
                        data, addr = sock.recvfrom(1024)
                        if data:
                            # 使用线程处理命令，避免阻塞主循环
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
        print("正在停止键盘守护进程...")
        self.running = False
        
        # 关闭控制Socket
        try:
            self.control_socket.close()
        except:
            pass
        
        # 关闭状态Socket
        try:
            self.status_socket.close()
        except:
            pass
        
        # 清理socket文件
        socket_path = self.config.get('daemon_config', 'socket_path', fallback='/tmp/keyboard.sock')
        get_status_path = self.config.get('daemon_config', 'get_statu_path', fallback='/tmp/keyboard_get.sock')
        
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
        
        print("键盘守护进程已停止")


if __name__ == '__main__':
    import sys
    
    # 检查命令行参数
    simulate = '--simulate' in sys.argv or '-s' in sys.argv
    
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.ini')
    daemon = KeyboardEventDaemon(config_path, simulate=simulate)
    daemon.run()