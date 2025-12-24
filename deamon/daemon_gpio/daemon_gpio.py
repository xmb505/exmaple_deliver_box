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
    
    def __init__(self, tty_path, baudrate=115200, simulate=False):
        self.tty_path = tty_path
        self.baudrate = baudrate
        self.ser = None
        self.simulate = simulate
        self.gpio_states = {}  # 用于模拟模式下的GPIO状态
        
        # 添加一个状态跟踪字典，记录当前各GPIO引脚的状态
        self.current_gpio_states = {}
        
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
            # 检查是否是第一次设置或者状态是否发生了变化
            current_state = self.current_gpio_states.get(pin)
            if current_state is None or current_state != new_state:
                changed_states[pin] = new_state
                self.current_gpio_states[pin] = new_state  # 更新当前状态
        
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
                    controller.set_gpio({gpio: value})
                elif 'gpios' in command and 'values' in command:
                    # 批量GPIO控制
                    gpios = command['gpios']
                    values = command['values']
                    if len(gpios) != len(values):
                        print("错误: gpios数组和values数组长度不匹配")
                        return
                    gpio_states = dict(zip(gpios, values))
                    controller.set_gpio(gpio_states)
            
            elif mode == 'spi' and controller_config['mode'] == 'spi':
                # 将SPI命令加入队列，由专门的线程处理
                spi_task = {
                    'controller': controller,
                    'config': controller_config,
                    'command': command
                }
                self.spi_queue.put(spi_task)
            
            elif mode == 'spi_multi' and controller_config['mode'] == 'spi':
                # 将多路SPI命令加入队列，由专门的线程处理
                spi_task = {
                    'controller': controller,
                    'config': controller_config,
                    'command': command
                }
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
            # 发送初始状态（可选）
            pass
            
            # 保持连接
            while self.running:
                # 这里可以定期发送GPIO状态变化
                time.sleep(1)
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
        
        # 从配置中读取geter模式的GPIO配置
        for alias, config in self.controller_configs.items():
            if config['mode'] == 'geter':
                default_bit = int(config['config'].get('default_bit', 0))
                self.gpio_default_states[alias] = default_bit
                self.gpio_last_states[alias] = {}
        
        # 持续监控GPIO状态变化
        while self.running:
            try:
                for alias, controller in self.controllers.items():
                    if self.controller_configs[alias]['mode'] == 'geter':
                        default_bit = self.gpio_default_states.get(alias, 0)
                        
                        # 在实际实现中，这里应该遍历配置中指定的GPIO引脚
                        # 由于配置文件中没有明确指定监控哪些GPIO引脚
                        # 我们暂时假设有配置项来指定监控的GPIO
                        # 实际应用中可以扩展配置文件来定义监控的GPIO列表
                        
                        # 为了实现监控功能，我们假设配置中有一个gpio_list项
                        # 或者我们可以通过某种方式获取当前连接的GPIO设备的输入引脚
                        # 这里我们使用一个模拟的检查方式
                        
                        # 尝试读取一些可能的GPIO引脚状态（1-16）
                        for gpio_pin in range(1, 17):
                            current_state = controller.read_gpio(gpio_pin)
                            if current_state is not None:
                                last_state = self.gpio_last_states[alias].get(gpio_pin)
                                
                                # 检查状态是否发生变化
                                if last_state is not None and last_state != current_state:
                                    # 检查是否符合默认电平采集模式
                                    if (default_bit == 1 and current_state == 0) or (default_bit == 0 and current_state == 1):
                                        # 发现状态变化，符合采集条件，广播给客户端
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
                
                time.sleep(0.1)  # 每100ms检查一次
            except Exception as e:
                print(f"GPIO监控线程发生错误: {e}")
                time.sleep(1)
    
    def broadcast_gpio_status(self, status_data):
        """向所有状态监听客户端广播GPIO状态"""
        with self.status_clients_lock:
            disconnected_clients = []
            for client in self.status_clients:
                try:
                    client.send(json.dumps(status_data).encode('utf-8'))
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
    
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.ini')
    daemon = GPIOControlDaemon(config_path, simulate=simulate, debug_spi=debug_spi)
    daemon.run()