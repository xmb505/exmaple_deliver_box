#!/usr/bin/env python3
"""
GPIO守护进程
将USB2GPIO设备抽象为UNIX Socket接口，便于进程间通信
采用JSON数据格式进行命令传输
"""

import json
import socket
import threading
import time
import serial
import configparser
import struct
import os
import select
from pathlib import Path
import queue


class USBGPIOController:
    """USB GPIO控制器类"""
    
    def __init__(self, tty_path, baudrate=115200, simulate=False, debug=False):
        self.tty_path = tty_path
        self.baudrate = baudrate
        self.ser = None
        self.simulate = simulate
        self.debug = debug  # 添加调试标志
        self.gpio_states = {}  # 用于模拟模式下的GPIO状态
        
        # 添加一个状态跟踪字典，记录当前各GPIO引脚的状态
        self.current_gpio_states = {}
        
        # 添加数据缓冲区，用于累积流式数据避免截断
        self.data_buffer = ""
        
        if not simulate:
            self.connect()
        else:
            print(f"USB GPIO控制器运行在模拟模式，设备: {self.tty_path}")
    
    def connect(self):
        """连接到USB GPIO设备"""
        try:
            self.ser = serial.Serial(self.tty_path, self.baudrate, timeout=0.001)
            print(f"成功连接到 {self.tty_path}")
        except Exception as e:
            print(f"错误: 无法连接到设备 {self.tty_path}: {e}")
            raise
    
    def reconnect(self):
        """重新连接到设备"""
        if self.ser:
            try:
                self.ser.close()
            except:
                pass
        time.sleep(1)
        self.connect()
    
    def send_command(self, command):
        """发送命令到USB GPIO设备"""
        
        # 调试：打印发送的指令
        if hasattr(self, 'debug') and self.debug:
            print(f"调试: 发送指令 - {[hex(b) for b in command]}")
        
        if self.simulate:
            # 模拟模式：解析命令并更新GPIO状态
            if command[0] == 0x3A:  # GPIO设置命令
                # 解析命令格式: 3A [pin1] [state1] [pin2] [state2] ...
                i = 1
                while i < len(command):
                    if i + 1 < len(command):
                        pin = command[i]
                        state = command[i + 1]
                        self.gpio_states[pin] = state
                        self.current_gpio_states[pin] = state  # 同时更新当前状态
                        i += 2
                    else:
                        break
            elif command[0] == 0x3F:  # GPIO读取命令
                # 模拟返回值
                pin = command[1]
                state = self.gpio_states.get(pin, 0)
                # 在模拟模式下，我们不实际发送返回值
            return True
        
        if not self.ser or not self.ser.is_open:
            try:
                self.reconnect()
            except:
                return False
        
        try:
            self.ser.write(command)
            return True
        except Exception as e:
            print(f"发送命令失败: {e}")
            try:
                self.reconnect()
            except:
                pass
            return False
    
    def set_gpio(self, gpio_states):
        """
        设置GPIO状态，gpio_states为字典 {pin: state, ...}
        优化：只对状态发生变化的GPIO引脚发送命令
        """
        # 筛选出状态真正发生变化的GPIO
        changed_states = {}
        for pin, new_state in gpio_states.items():
            # 确保GPIO引脚和状态是整数
            gpio_pin = int(pin)
            state = int(new_state)
            
            # 检查是否是第一次设置或者状态是否发生了变化
            current_state = self.current_gpio_states.get(gpio_pin)
            if current_state is None or current_state != state:
                changed_states[gpio_pin] = state
                self.current_gpio_states[gpio_pin] = state  # 更新当前状态
        
        if not changed_states:
            # 如果没有状态变化，直接返回
            return True
        
        # 发送实际发生变化的GPIO状态
        command = bytearray([0x3A])
        for gpio_pin, state in changed_states.items():
            command.append(gpio_pin)
            command.append(state)
        return self.send_command(bytes(command))
    
    def read_gpio(self, gpio_pin):
        """读取单个GPIO状态"""
        if self.simulate:
            # 模拟模式下返回存储的状态，如果没有则随机返回0或1
            return self.gpio_states.get(gpio_pin, 0)
        
        command = bytearray([0x3F, gpio_pin])
        if not self.send_command(bytes(command)):
            return None
        
        # 等待响应
        time.sleep(0.01)
        if self.ser.in_waiting >= 3:
            response = self.ser.read(3)
            if len(response) == 3 and response[0] == 0x2F and response[1] == gpio_pin:
                return response[2]
        return None
    
    def set_spi(self, clk_pin, data_pin, cs_pin, data, cs_collection="down", lag_time=0.001, debug_spi=False):
        """使用bit-banging方式实现SPI通信，支持任意比特数，优化GPIO设置"""
        import time
        
        start_time = time.time()
        
        if debug_spi:
            lag_time_ms = lag_time * 1000  # 转换为毫秒用于显示
            print(f"[SPI调试] 开始SPI传输 - CLK:{clk_pin}, DATA:{data_pin}, CS:{cs_pin}, 数据长度:{len(data)}, CS触发方式:{cs_collection}, 每次操作延迟:{lag_time_ms:.3f}ms")
        
        if self.simulate:
            # 模拟SPI通信
            if debug_spi:
                lag_time_ms = lag_time * 1000  # 转换为毫秒用于显示
                print(f"模拟SPI通信: CLK={clk_pin}, DATA={data_pin}, CS={cs_pin}, DATA={data}, CS_COLLECTION={cs_collection}, 每次操作延迟={lag_time_ms:.3f}ms")
            
            # 模拟实际的操作延迟
            total_ops = 3 + len(data) * 3  # CS拉低 + (每个数据位的DATA设置+时钟下降沿+时钟拉高) + CS拉高
            total_delay = total_ops * lag_time
            time.sleep(total_delay)  # 模拟总体延迟
            
            if debug_spi:
                end_time = time.time()
                actual_time = end_time - start_time
                print(f"[SPI调试] 模拟传输完成，理论延迟: {total_delay:.6f}s，实际耗时: {actual_time:.6f}s")
            return
        
        # 拉低CS（开始传输）
        if debug_spi:
            print(f"[SPI调试] 设置CS({cs_pin}) = 0 (开始传输)")
        set_start = time.time()
        self.set_gpio({cs_pin: 0})
        time.sleep(lag_time)
        set_end = time.time()
        if debug_spi:
            print(f"[SPI调试] CS设置耗时: {set_end - set_start:.6f}s")
        
        # 发送数据（每一位），优化：避免不必要的电平切换
        last_data_state = None
        last_clk_state = None
        
        for i, bit in enumerate(data):
            bit_start_time = time.time()
            
            # 跳过空格字符
            if bit == ' ':
                continue
                
            # 设置数据位（仅在状态变化时设置）
            bit = int(bit)
            if last_data_state is None or last_data_state != bit:
                if debug_spi:
                    print(f"[SPI调试] 设置DATA({data_pin}) = {bit} (第{i+1}位)")
                set_start = time.time()
                self.set_gpio({data_pin: bit})
                time.sleep(lag_time)
                set_end = time.time()
                if debug_spi:
                    print(f"[SPI调试] DATA设置耗时: {set_end - set_start:.6f}s")
                last_data_state = bit
            else:
                # 数据位状态未变化，但仍需要保持延迟
                time.sleep(lag_time)
                if debug_spi:
                    print(f"[SPI调试] DATA({data_pin}) = {bit} 保持不变 (第{i+1}位)")
            
            # 时钟脉冲 - 优化时钟线状态切换
            if cs_collection == "down":
                # 对于下降沿触发，先拉高时钟，再拉低
                # 设置CLK为高电平（仅在状态变化时设置）
                if last_clk_state is None or last_clk_state != 1:
                    if debug_spi:
                        print(f"[SPI调试] 设置CLK({clk_pin}) = 1")
                    set_start = time.time()
                    self.set_gpio({clk_pin: 1})
                    last_clk_state = 1
                    set_end = time.time()
                    if debug_spi:
                        print(f"[SPI调试] CLK拉高耗时: {set_end - set_start:.6f}s")
                else:
                    time.sleep(lag_time)  # 保持延迟
                    if debug_spi:
                        print(f"[SPI调试] CLK({clk_pin}) = 1 保持不变")
                
                time.sleep(lag_time)
                
                # 设置CLK为低电平（仅在状态变化时设置） - 下降沿采样
                if last_clk_state != 0:
                    if debug_spi:
                        print(f"[SPI调试] 设置CLK({clk_pin}) = 0 (下降沿采样)")
                    set_start = time.time()
                    self.set_gpio({clk_pin: 0})
                    last_clk_state = 0
                    set_end = time.time()
                    if debug_spi:
                        print(f"[SPI调试] CLK拉低耗时: {set_end - set_start:.6f}s")
                else:
                    time.sleep(lag_time)  # 保持延迟
                    if debug_spi:
                        print(f"[SPI调试] CLK({clk_pin}) = 0 保持不变")
            else:
                # 对于上升沿触发，先拉低时钟，再拉高
                # 设置CLK为低电平（仅在状态变化时设置）
                if last_clk_state is None or last_clk_state != 0:
                    if debug_spi:
                        print(f"[SPI调试] 设置CLK({clk_pin}) = 0")
                    set_start = time.time()
                    self.set_gpio({clk_pin: 0})
                    last_clk_state = 0
                    set_end = time.time()
                    if debug_spi:
                        print(f"[SPI调试] CLK拉低耗时: {set_end - set_start:.6f}s")
                else:
                    time.sleep(lag_time)  # 保持延迟
                    if debug_spi:
                        print(f"[SPI调试] CLK({clk_pin}) = 0 保持不变")
                
                time.sleep(lag_time)
                
                # 设置CLK为高电平（仅在状态变化时设置） - 上升沿采样
                if last_clk_state != 1:
                    if debug_spi:
                        print(f"[SPI调试] 设置CLK({clk_pin}) = 1 (上升沿采样)")
                    set_start = time.time()
                    self.set_gpio({clk_pin: 1})
                    last_clk_state = 1
                    set_end = time.time()
                    if debug_spi:
                        print(f"[SPI调试] CLK拉高耗时: {set_end - set_start:.6f}s")
                else:
                    time.sleep(lag_time)  # 保持延迟
                    if debug_spi:
                        print(f"[SPI调试] CLK({clk_pin}) = 1 保持不变")
            
            time.sleep(lag_time)
            
            bit_end_time = time.time()
            if debug_spi:
                print(f"[SPI调试] 第{i+1}位处理总耗时: {bit_end_time - bit_start_time:.6f}s")
        
        # 拉高CS（结束传输），完成一次CS切片
        if debug_spi:
            print(f"[SPI调试] 设置CS({cs_pin}) = 1 (结束传输)")
        set_start = time.time()
        self.set_gpio({cs_pin: 1})
        time.sleep(lag_time)
        set_end = time.time()
        if debug_spi:
            print(f"[SPI调试] CS拉高耗时: {set_end - set_start:.6f}s")
        
        end_time = time.time()
        if debug_spi:
            print(f"[SPI调试] SPI传输完成，总耗时: {end_time - start_time:.6f}s")


class GPIOControlDaemon:
    """GPIO控制守护进程"""
    
    def __init__(self, config_path, simulate=False, debug_spi=False):
        self.config = configparser.ConfigParser()
        self.config.read(config_path)
        
        # 是否使用模拟模式和调试SPI
        self.simulate = simulate
        self.debug_spi = debug_spi
        
        # 初始化USB GPIO控制器
        self.controllers = {}
        self.controller_configs = {}
        
        # GPIO状态变化缓冲区和相关锁
        self.gpio_change_buffer = {}
        self.gpio_change_buffer_lock = threading.Lock()
        self.gpio_change_buffer_last_send = time.time()
        self.gpio_change_buffer_send_interval = 0.05  # 50毫秒的缓冲间隔
        
        # 消息ID生成相关
        self.message_id_counter = 0
        self.message_id_lock = threading.Lock()
        
        # GPIO状态跟踪（用于查询功能）
        self.current_gpio_states = {}
        
        # 读取配置文件中的所有GPIO设备
        for section_name in self.config.sections():
            if section_name == 'daemon_config':
                continue
            
            tty_path = self.config.get(section_name, 'tty_path')
            baudrate = self.config.getint(section_name, 'baudrate', fallback=115200)
            alias = self.config.get(section_name, 'alias')
            mode = self.config.get(section_name, 'mode')
            
            try:
                controller = USBGPIOController(tty_path, baudrate, simulate=simulate)
                self.controllers[alias] = controller
                self.controller_configs[alias] = {
                    'mode': mode,
                    'config': dict(self.config.items(section_name))
                }
                
                # 如果是SPI模式，提取SPI引脚配置
                if mode == 'spi':
                    spi_pins = {}
                    for key, value in self.controller_configs[alias]['config'].items():
                        if key.startswith(('clk_', 'data_', 'cs_')):
                            # 去除可能的注释部分（以#开头的内容）
                            clean_value = value.split('#')[0].strip()
                            if clean_value:  # 确保去除注释后还有有效内容
                                try:
                                    spi_pins[key] = int(clean_value)
                                except ValueError:
                                    print(f"警告: 无法将 '{key}' 的值 '{value}' 转换为整数，跳过该配置")
                    self.controller_configs[alias]['spi_pins'] = spi_pins
            except Exception as e:
                if not simulate:
                    print(f"初始化控制器 {alias} 失败: {e}")
                    print("尝试使用模拟模式...")
                    try:
                        controller = USBGPIOController(tty_path, baudrate, simulate=True)
                        self.controllers[alias] = controller
                        self.controller_configs[alias] = {
                            'mode': mode,
                            'config': dict(self.config.items(section_name))
                        }
                        
                        # 如果是SPI模式，提取SPI引脚配置
                        if mode == 'spi':
                            spi_pins = {}
                            for key, value in self.controller_configs[alias]['config'].items():
                                if key.startswith(('clk_', 'data_', 'cs_')):
                                    # 去除可能的注释部分（以#开头的内容）
                                    clean_value = value.split('#')[0].strip()
                                    if clean_value:  # 确保去除注释后还有有效内容
                                        try:
                                            spi_pins[key] = int(clean_value)
                                        except ValueError:
                                            print(f"警告: 无法将 '{key}' 的值 '{value}' 转换为整数，跳过该配置")
                            self.controller_configs[alias]['spi_pins'] = spi_pins
                    except Exception as e2:
                        print(f"即使在模拟模式下初始化控制器 {alias} 也失败: {e2}")
                else:
                    print(f"在模拟模式下初始化控制器 {alias} 失败: {e}")
        
        # 创建控制Socket
        socket_path = self.config.get('daemon_config', 'socket_path', fallback='/tmp/gpio.sock')
        if os.path.exists(socket_path):
            os.unlink(socket_path)
        
        self.control_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.control_socket.bind(socket_path)
        os.chmod(socket_path, 0o777)  # 设置权限以便其他进程访问
        
        # 创建状态监听Socket
        get_status_path = self.config.get('daemon_config', 'get_statu_path', fallback='/tmp/gpio_get.sock')
        if os.path.exists(get_status_path):
            os.unlink(get_status_path)
        
        self.status_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.status_socket.bind(get_status_path)
        self.status_socket.listen(10)  # 最多允许10个并发连接
        os.chmod(get_status_path, 0o777)
        
        # 存储状态监听客户端
        self.status_clients = []
        self.status_clients_lock = threading.Lock()
        
        # 为SPI操作添加队列和锁，确保SPI操作串行执行
        self.spi_queue = queue.Queue()
        self.spi_processing_lock = threading.Lock()  # 确保SPI处理的互斥性
        self.spi_worker_thread = None
        
        # 运行标志
        self.running = True
        
        print(f"GPIO守护进程初始化完成 (模拟模式: {simulate}, 调试SPI: {debug_spi})")
    
    def handle_control_command(self, data, addr):
        """处理控制命令"""
        try:
            command = json.loads(data.decode('utf-8'))
            alias = command.get('alias')
            mode = command.get('mode')
            
            # 调试：打印传入的命令
            if hasattr(self, 'debug') and self.debug:
                print(f"调试: 收到命令 - {command}")
            
            if alias not in self.controllers:
                print(f"错误: 未找到别名为 {alias} 的控制器")
                return
            
            controller = self.controllers[alias]
            controller_config = self.controller_configs[alias]
            
            if mode == 'set':
                if 'gpio' in command and 'value' in command:
                    # 单个GPIO控制
                    gpio = command['gpio']
                    value = command['value']
                    
                    # 调试：打印GPIO设置信息
                    if hasattr(self, 'debug') and self.debug:
                        print(f"调试: 设置GPIO {gpio} 为 {value}")
                    
                    controller.set_gpio({gpio: value})
                elif 'gpios' in command and 'values' in command:
                    # 批量GPIO控制
                    gpios = command['gpios']
                    values = command['values']
                    if len(gpios) != len(values):
                        print("错误: gpios数组和values数组长度不匹配")
                        return
                    
                    # 调试：打印批量GPIO设置信息
                    if hasattr(self, 'debug') and self.debug:
                        print(f"调试: 批量设置GPIO - gpios: {gpios}, values: {values}")
                    
                    gpio_states = dict(zip(gpios, values))
                    controller.set_gpio(gpio_states)
            
            elif mode == 'spi' and controller_config['mode'] == 'spi':
                # 将SPI命令加入队列，由专门的线程处理
                spi_task = {
                    'controller': controller,
                    'config': controller_config,
                    'command': command
                }
                
                # 调试：打印SPI命令信息
                if hasattr(self, 'debug') and self.debug:
                    print(f"调试: SPI命令 - {command}")
                
                self.spi_queue.put(spi_task)
            
            elif mode == 'spi_multi' and controller_config['mode'] == 'spi':
                # 将多路SPI命令加入队列，由专门的线程处理
                spi_task = {
                    'controller': controller,
                    'config': controller_config,
                    'command': command
                }
                
                # 调试：打印多路SPI命令信息
                if hasattr(self, 'debug') and self.debug:
                    print(f"调试: 多路SPI命令 - {command}")
                
                self.spi_queue.put(spi_task)
        
        except json.JSONDecodeError:
            print("错误: 无法解析JSON命令")
        except Exception as e:
            print(f"处理控制命令时发生错误: {e}")
    
    def process_spi_queue(self):
        """处理SPI队列中的任务"""
        while self.running:
            try:
                # 等待SPI任务
                spi_task = self.spi_queue.get(timeout=1.0)
                
                # 获取SPI配置中的延迟时间（配置文件中是毫秒，需要转换为秒）
                controller_alias = spi_task['command']['alias']
                controller_config = self.controller_configs[controller_alias]
                try:
                    lag_time_ms = float(controller_config.get('config', {}).get('lag_time', 1.0))  # 默认1毫秒
                    if lag_time_ms <= 0:
                        lag_time_ms = 1.0  # 确保延迟值为正数
                except (ValueError, TypeError):
                    lag_time_ms = 1.0  # 默认值
                lag_time = lag_time_ms / 1000.0  # 转换为秒
                
                # 执行SPI操作时使用互斥锁，确保一次只执行一个SPI任务
                with self.spi_processing_lock:
                    command = spi_task['command']
                    controller = spi_task['controller']
                    
                    if command['mode'] == 'spi':
                        # 单路SPI通信
                        spi_num = command.get('spi_num', 1)
                        spi_data = command.get('spi_data', '')
                        cs_collection = command.get('spi_data_cs_collection', 'down')
                        
                        clk_pin = controller_config['spi_pins'].get(f'clk_{spi_num}')
                        data_pin = controller_config['spi_pins'].get(f'data_{spi_num}')
                        cs_pin = controller_config['spi_pins'].get(f'cs_{spi_num}')
                        
                        if clk_pin and data_pin and cs_pin:
                            controller.set_spi(clk_pin, data_pin, cs_pin, spi_data, cs_collection, lag_time, self.debug_spi)
                        else:
                            print(f"错误: 未找到SPI接口{spi_num}的引脚配置")
                    
                    elif command['mode'] == 'spi_multi':
                        # 多路SPI通信
                        spis = command.get('spis', [])
                        for spi_config in spis:
                            spi_num = spi_config.get('spi_num', 1)
                            spi_data = spi_config.get('spi_data', '')
                            cs_collection = spi_config.get('spi_data_cs_collection', 'down')
                            
                            clk_pin = controller_config['spi_pins'].get(f'clk_{spi_num}')
                            data_pin = controller_config['spi_pins'].get(f'data_{spi_num}')
                            cs_pin = controller_config['spi_pins'].get(f'cs_{spi_num}')
                            
                            if clk_pin and data_pin and cs_pin:
                                controller.set_spi(clk_pin, data_pin, cs_pin, spi_data, cs_collection, lag_time, self.debug_spi)
                            else:
                                print(f"错误: 未找到SPI接口{spi_num}的引脚配置")
                
                # 标记任务完成
                self.spi_queue.task_done()
                
            except queue.Empty:
                # 队列为空，继续循环
                continue
            except Exception as e:
                print(f"处理SPI队列时发生错误: {e}")
                import traceback
                traceback.print_exc()
    
    def start_spi_worker(self):
        """启动SPI工作线程"""
        self.spi_worker_thread = threading.Thread(target=self.process_spi_queue, daemon=True)
        self.spi_worker_thread.start()
        print("SPI工作线程已启动")
    
    def handle_status_client(self, client_socket, client_addr):
        """处理状态监听客户端"""
        print(f"新的状态监听客户端连接: {client_addr}")
        
        with self.status_clients_lock:
            self.status_clients.append(client_socket)
        
        try:
            # 保持连接并处理客户端消息
            while self.running:
                # 尝试接收客户端消息（如ACK或查询请求）
                try:
                    client_socket.settimeout(1.0)  # 设置1秒超时
                    data = client_socket.recv(1024)
                    if not data:
                        # 客户端断开连接
                        break
                    
                    # 解析客户端发送的消息
                    try:
                        client_msg = json.loads(data.decode('utf-8'))
                        
                        # 处理ACK消息
                        if client_msg.get('type') == 'ack':
                            ack_id = client_msg.get('id')
                            print(f"收到客户端ACK: {ack_id}")
                            # 这里可以添加逻辑来跟踪已确认的消息
                        
                        # 处理状态查询请求
                        elif client_msg.get('type') == 'query_status':
                            # 发送当前所有GPIO状态
                            current_status = self.get_current_gpio_status()
                            client_socket.send(json.dumps(current_status).encode('utf-8'))
                            
                    except json.JSONDecodeError:
                        # 不是JSON格式的消息，可能是其他协议
                        pass
                        
                except socket.timeout:
                    # 超时是正常的，继续循环
                    continue
                except Exception as e:
                    # 连接可能已断开
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
    
    def start_gpio_monitoring(self):
        """启动GPIO状态监控线程"""
        # 初始化GPIO默认状态和上次状态
        self.gpio_default_states = {}
        self.gpio_last_states = {}
        
        # 跟踪哪些geter控制器已经发送了持续上报指令
        self.gpio_reporting_active = set()
        
        # 从配置中读取geter模式的GPIO配置
        for alias, config in self.controller_configs.items():
            if config['mode'] == 'geter':
                default_bit = int(config['config'].get('default_bit', 0))
                self.gpio_default_states[alias] = default_bit
                self.gpio_last_states[alias] = {}
        
        # 为每个geter控制器启动单独的监听线程
        for alias, controller in self.controllers.items():
            if self.controller_configs[alias]['mode'] == 'geter':
                default_bit = self.gpio_default_states.get(alias, 0)
                
                # 对于geter模式，发送持续上报指令
                if not controller.simulate:
                    if not controller.ser or not controller.ser.is_open:
                        try:
                            controller.reconnect()
                        except:
                            continue
                    
                    # 发送持续上报指令
                    if default_bit == 0:
                        # 使用3E指令（拉低模式）启用持续GPIO状态上报
                        command = bytearray([0x3E, 0xFF])
                    else:
                        # 使用3D指令（拉高模式）启用持续GPIO状态上报
                        command = bytearray([0x3D, 0xFF])
                    
                    try:
                        controller.ser.write(command)
                        print(f"已发送GPIO持续上报指令到 {alias} 设备 (default_bit={default_bit})")
                        self.gpio_reporting_active.add(alias)
                    except Exception as e:
                        print(f"发送GPIO持续上报指令失败: {e}")
                else:
                    # 模拟模式下标记为已激活
                    self.gpio_reporting_active.add(alias)
                
                # 为每个geter控制器启动监听线程
                if not controller.simulate:
                    # 启动监听线程
                    listen_thread = threading.Thread(
                        target=self.listen_gpio_controller,
                        args=(alias, controller, default_bit),
                        daemon=True
                    )
                    listen_thread.start()
                else:
                    # 模拟模式：启动模拟监听线程
                    simulate_thread = threading.Thread(
                        target=self.simulate_gpio_controller,
                        args=(alias, controller, default_bit),
                        daemon=True
                    )
                    simulate_thread.start()
        
        # 主线程只负责处理缓冲区数据广播
        while self.running:
            try:
                # 检查是否需要发送缓冲区数据
                current_time = time.time()
                if current_time - self.gpio_change_buffer_last_send >= self.gpio_change_buffer_send_interval:
                    self.send_buffered_gpio_status()
                    self.gpio_change_buffer_last_send = current_time
                    
                    # 计算距离下一次发送的时间间隔
                    time_since_last_send = time.time() - self.gpio_change_buffer_last_send
                    wait_time = max(0.01, self.gpio_change_buffer_send_interval - time_since_last_send)
                    time.sleep(wait_time)
                else:
                    # 距离下一次发送还有时间，等待剩余时间
                    remaining_time = self.gpio_change_buffer_send_interval - (current_time - self.gpio_change_buffer_last_send)
                    wait_time = max(0.01, remaining_time)
                    time.sleep(wait_time)
                
            except Exception as e:
                print(f"GPIO监控主线程发生错误: {e}")
                time.sleep(1)
    
    def listen_gpio_controller(self, alias, controller, default_bit):
        """监听单个GPIO控制器的数据上报"""
        print(f"开始监听GPIO控制器: {alias}")
        
        while self.running:
            try:
                # 使用select来监听串口数据，避免轮询+sleep
                # select会阻塞直到有数据可读
                ready, _, _ = select.select([controller.ser], [], [], 0.1)
                
                if ready:
                    # 读取所有可用数据
                    response_data = controller.ser.read(controller.ser.in_waiting)
                    
                    if response_data:
                        # 解析响应数据，格式为 "CH1:0 CH2:1 CH3:0 ..."
                        # 忽略换行符，将数据添加到缓冲区
                        response_str = response_data.decode('ascii', errors='ignore')
                        response_str = response_str.replace('\n', '').replace('\r', '').strip()
                        
                        # 将新数据添加到缓冲区
                        controller.data_buffer += response_str
                        
                        # 提取所有CHx:y格式的数据
                        import re
                        matches = re.findall(r'CH(\d+):([01])', controller.data_buffer)
                        
                        if matches:
                            gpio_states = {}
                            for gpio_num, state in matches:
                                gpio_num = int(gpio_num)
                                state = int(state)
                                gpio_states[gpio_num] = state
                            
                            # 更新当前GPIO状态（用于查询功能）
                            if alias not in self.current_gpio_states:
                                self.current_gpio_states[alias] = {}
                            self.current_gpio_states[alias].update(gpio_states)
                            
                            # 清理缓冲区：移除已处理的数据，保留未完整的尾部数据
                            # 使用正则找到最后一个完整匹配的位置
                            last_match_end = 0
                            for match in re.finditer(r'CH(\d+):([01])', controller.data_buffer):
                                last_match_end = match.end()
                            
                            # 保留未处理的尾部数据（可能是被截断的"CH"等）
                            if last_match_end > 0:
                                controller.data_buffer = controller.data_buffer[last_match_end:]
                        
                            # 检查每个GPIO的状态变化
                            for gpio_pin, current_state in gpio_states.items():
                                last_state = self.gpio_last_states[alias].get(gpio_pin)
                    
                                if last_state is not None and last_state != current_state:
                                    # 发现状态变化，广播给客户端
                                    # default_bit表示配置的查询电平指令集类型（0=3E指令拉低检测，1=3D指令拉高检测）
                                    status_data = {
                                        "gpios": [
                                            {
                                                "alias": alias,
                                                "default_bit": default_bit,
                                                "change_gpio": [
                                                    {
                                                        "gpio": gpio_pin,
                                                        "bit": current_state
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                    self.broadcast_gpio_status(status_data)
                    
                                # 更新最后状态
                                self.gpio_last_states[alias][gpio_pin] = current_state
            except Exception as e:
                print(f"监听GPIO控制器 {alias} 时发生错误: {e}")
                # 尝试重新连接
                try:
                    controller.reconnect()
                    # 重新发送持续上报指令
                    self.gpio_reporting_active.discard(alias)
                except:
                    pass

    def simulate_gpio_controller(self, alias, controller, default_bit):
        """模拟GPIO控制器的数据上报"""
        import random
        
        while self.running:
            # 模拟定期生成数据
            time.sleep(0.1)  # 模拟数据生成间隔
            
            gpio_states = {}
            for gpio_pin in range(1, 17):
                current_state = random.randint(0, 1)
                gpio_states[gpio_pin] = current_state
            
            # 更新当前GPIO状态（用于查询功能）
            if alias not in self.current_gpio_states:
                self.current_gpio_states[alias] = {}
            self.current_gpio_states[alias].update(gpio_states)
            
            # 检查每个GPIO的状态变化
            for gpio_pin, current_state in gpio_states.items():
                last_state = self.gpio_last_states[alias].get(gpio_pin)
                
                if last_state is not None and last_state != current_state:
                    status_data = {
                        "gpios": [
                            {
                                "alias": alias,
                                "default_bit": default_bit,
                                "change_gpio": [
                                    {
                                        "gpio": gpio_pin,
                                        "bit": current_state
                                    }
                                ]
                            }
                        ]
                    }
                    self.broadcast_gpio_status(status_data)
                
                # 更新最后状态
                self.gpio_last_states[alias][gpio_pin] = current_state
    
    def get_next_message_id(self):
        """获取下一个消息ID"""
        with self.message_id_lock:
            self.message_id_counter += 1
            return self.message_id_counter
    
    def broadcast_gpio_status(self, status_data):
        """将GPIO状态变化添加到缓冲区，稍后批量发送以避免JSON粘连"""
        with self.gpio_change_buffer_lock:
            # 从status_data中提取GPIO变化信息
            for gpio_info in status_data.get('gpios', []):
                alias = gpio_info.get('alias')
                if alias not in self.gpio_change_buffer:
                    self.gpio_change_buffer[alias] = []
                
                # 添加到缓冲区
                self.gpio_change_buffer[alias].append(gpio_info)
    
    def send_buffered_gpio_status(self):
        """发送缓冲区中的GPIO状态变化"""
        with self.gpio_change_buffer_lock:
            if not self.gpio_change_buffer:
                return  # 没有要发送的数据
            
            # 合并相同alias的GPIO变化
            combined_status_data = {"gpios": []}
            for alias, changes in self.gpio_change_buffer.items():
                combined_changes = {
                    "alias": alias,
                    "default_bit": changes[0].get('default_bit', 0),  # 使用第一个的default_bit
                    "change_gpio": []
                }
                
                # 合并所有变化
                for change in changes:
                    combined_changes["change_gpio"].extend(change.get('change_gpio', []))
                
                combined_status_data["gpios"].append(combined_changes)
            
            # 清空缓冲区
            self.gpio_change_buffer.clear()
        
        # 添加消息ID和类型
        message_id = self.get_next_message_id()
        message_data = {
            "type": "gpio_change",
            "id": message_id,
            "timestamp": time.time(),
            **combined_status_data  # 展开GPIO数据
        }
        
        # 发送合并后的数据
        with self.status_clients_lock:
            disconnected_clients = []
            for client in self.status_clients:
                try:
                    client.send(json.dumps(message_data).encode('utf-8'))
                except Exception as e:
                    print(f"向客户端发送状态失败: {e}")
                    disconnected_clients.append(client)
            
            # 移除断开的客户端
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
        
        # 为每个geter类型的控制器获取当前状态
        for alias, controller in self.controllers.items():
            if self.controller_configs[alias]['mode'] == 'geter':
                default_bit = self.gpio_default_states.get(alias, 0)
                
                # 从current_gpio_states获取当前GPIO状态，如果为空则使用最后一次已知状态
                current_gpio_states = self.current_gpio_states.get(alias, {}).copy()
                
                # 如果current_gpio_states为空，使用gpio_last_states作为备选
                if not current_gpio_states and alias in self.gpio_last_states:
                    current_gpio_states = self.gpio_last_states[alias].copy()
                
                current_status["gpios"].append({
                    "alias": alias,
                    "default_bit": default_bit,
                    "current_gpio_states": current_gpio_states
                })
        
        return current_status
    
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
                if self.running:  # 如果不是因为关闭导致的异常
                    print(f"接受状态监听连接时发生错误: {e}")
    
    def run(self):
        """运行守护进程"""
        print("GPIO守护进程启动...")
        
        # 启动SPI工作线程
        self.start_spi_worker()
        
        # 启动状态监听服务器线程
        status_thread = threading.Thread(target=self.start_status_server, daemon=True)
        status_thread.start()
        
        # 启动GPIO监控线程
        gpio_monitor_thread = threading.Thread(target=self.start_gpio_monitoring, daemon=True)
        gpio_monitor_thread.start()
        
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
        print("正在停止GPIO守护进程...")
        self.running = False
        
        # 等待SPI队列中的所有任务完成
        try:
            self.spi_queue.join()  # 等待所有队列任务完成
        except:
            pass
        
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
        
        # 关闭所有状态监听客户端
        with self.status_clients_lock:
            for client in self.status_clients:
                try:
                    client.close()
                except:
                    pass
            self.status_clients.clear()
        
        # 关闭所有USB控制器
        for controller in self.controllers.values():
            try:
                if controller.ser and controller.ser.is_open:
                    controller.ser.close()
            except:
                pass
        
        # 清理socket文件
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


if __name__ == '__main__':
    import sys
    
    # 检查命令行参数
    simulate = '--simulate' in sys.argv or '-s' in sys.argv
    debug_spi = '--debug-spi' in sys.argv
    debug = '--debug' in sys.argv or '-d' in sys.argv
    
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.ini')
    daemon = GPIOControlDaemon(config_path, simulate=simulate, debug_spi=debug_spi)
    daemon.debug = debug  # 添加调试标志
    daemon.run()