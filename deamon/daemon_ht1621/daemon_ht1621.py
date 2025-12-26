#!/usr/bin/env python3
"""
HT1621抽象层守护进程
提供Unix Socket接口，通过GPIO守护进程的SPI模式控制HT1621 LCD
"""

import json
import socket
import threading
import time
import os
import struct
import configparser


class HT1621Daemon:
    """HT1621守护进程类"""
    
    def __init__(self, config_path="/home/xmb505/智能外卖柜样机/deamon/daemon_ht1621/config/config.ini", debug=False):
        # 创建一个区分大小写的配置解析器
        self.config = configparser.ConfigParser()
        # 设置选项名称保持原样（区分大小写）
        self.config.optionxform = str
        self.config.read(config_path)
        
        self.gpio_socket_path = self.config.get('daemon_config', 'gpio_socket_path', fallback='/tmp/gpio.sock')
        self.ht1621_socket_path = self.config.get('daemon_config', 'ht1621_socket_path', fallback='/tmp/ht1621.sock')
        self.running = True
        self.debug = debug  # 添加调试标志
        
        # 从配置文件读取段码表 (从font_data段)
        self.digit_to_segments = {}
        for key in self.config.options('font_data'):
            # 区分段码和RAM地址，段码是单个字符，RAM地址是ram_address_开头
            if not key.startswith('ram_address_'):
                # 保持字符的原始大小写，因为'C'和'c'是不同的字符
                self.digit_to_segments[key] = self.config.get('font_data', key)
        
        # 从配置文件读取RAM地址映射 (也在font_data段中)
        self.ram_addresses = []
        for i in range(6):  # 6个显示位
            addr_key = f'ram_address_{i}'
            if self.config.has_option('font_data', addr_key):
                self.ram_addresses.append(self.config.getint('font_data', addr_key))
        
        # 从配置文件读取初始化序列
        self.init_commands_data = []
        for key in self.config.options('init_sequence'):
            if key.startswith('init_'):
                # 去除注释部分（以#开头的内容）和多余空格
                raw_value = self.config.get('init_sequence', key)
                clean_value = raw_value.split('#')[0].strip()
                self.init_commands_data.append(clean_value)
        
        # 从配置文件读取设备映射
        self.device_mapping = {}
        for key in self.config.options('device_mapping'):
            if key.startswith('device_'):
                device_id = int(key[7:])  # 移除'device_'前缀，获取数字
                mapping_str = self.config.get('device_mapping', key)
                # 解析格式: alias:spi_interface_id
                alias, spi_interface_id = mapping_str.split(':')
                self.device_mapping[device_id] = (alias, int(spi_interface_id))
        
        # 初始化GPIO Socket
        self.gpio_sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    
    def send_to_gpio(self, data):
        """发送数据到GPIO守护进程"""
        # 调试：打印发送的数据
        if hasattr(self, 'debug') and self.debug:
            print(f"调试: 发送到GPIO守护进程 - {data}")
        
        try:
            self.gpio_sock.sendto(data.encode('utf-8'), self.gpio_socket_path)
            return True
        except Exception as e:
            print(f"发送到GPIO守护进程失败: {e}")
            return False
    
    def init_ht1621(self, device_id):
        """初始化HT1621"""
        if device_id not in self.device_mapping:
            print(f"错误: 未找到device_id {device_id}的映射配置")
            return False
            
        alias, spi_interface_id = self.device_mapping[device_id]
        print(f"初始化HT1621设备 {device_id} (映射到{alias}设备的SPI接口{spi_interface_id})...")
        
        # 使用ht1621_input_test.py中验证过的初始化序列（9位命令格式）
        init_commands = [
            "000000000",  # SYSDIS: 关闭系统
            "001010110",  # BIAS: 1/3 Bias, 4 COM
            "011000000",  # RC256: 使用内部RC振荡器
            "000000010",  # SYSEN: 使能系统
            "000000110"   # LCDON: 打开显示输出
        ]
        
        # 发送初始化序列
        for cmd9 in init_commands:
            frame = "100" + cmd9  # HT1621命令格式：100 + 9位命令
            cmd = {
                "alias": alias,
                "mode": "spi", 
                "spi_num": spi_interface_id,
                "spi_data_cs_collection": "down", 
                "spi_data": frame
            }
            self.send_to_gpio(json.dumps(cmd))
        
        # 初始化完成后，清除所有显示
        self.clear_display(device_id)
        
        print(f"HT1621设备 {device_id} 初始化完成")
        return True
    
    def clear_display(self, device_id):
        """清除HT1621的所有显示"""
        if device_id not in self.device_mapping:
            print(f"错误: 未找到device_id {device_id}的映射配置")
            return False
            
        # 清除所有RAM地址的显示（写入0x00）
        for ram_address in self.ram_addresses:
            self.write_ram_to_ht1621(device_id, ram_address, "00000000")
        
        return True
    
    def write_ram_to_ht1621(self, device_id, address, data):
        """写RAM到HT1621"""
        if device_id not in self.device_mapping:
            print(f"错误: 未找到device_id {device_id}的映射配置")
            return False
            
        alias, spi_interface_id = self.device_mapping[device_id]
        
        # RAM写入命令格式: 101 + 6位地址 + 8位数据
        address_bin = format(address, '06b')  # 6位地址
        data_bin = data  # 8位数据 (已经是8位二进制字符串)
        command = f"101{address_bin}{data_bin}"
        
        cmd = {
            "alias": alias,  # 使用映射的设备别名
            "mode": "spi", 
            "spi_num": spi_interface_id,  # 使用映射的SPI接口ID
            "spi_data_cs_collection": "down", 
            "spi_data": command
        }
        
        return self.send_to_gpio(json.dumps(cmd))
    
    def display_data(self, device_id, display_data):
        """在HT1621上显示数据"""
        if device_id not in self.device_mapping:
            print(f"错误: 未找到device_id {device_id}的映射配置")
            return False
            
        # 限制显示数据长度为6位
        display_data = str(display_data)[:6]
        
        # 将显示数据右对齐，左边填充空格
        padded_data = display_data.rjust(6)
        
        # 写入每个字符到对应的RAM地址
        # 修复显示方向问题：字符顺序需要反向映射到RAM地址
        # 例如：输入"Err404"应该正常显示，而不是显示为"404rrE"
        for i, char in enumerate(padded_data):
            # 查找字符的段码，首先尝试原始字符，然后尝试转为大写（保持向后兼容性）
            segment_key = None
            if char in self.digit_to_segments:
                segment_key = char
            elif char.upper() in self.digit_to_segments:
                segment_key = char.upper()
            elif char == ' ':  # 处理空格
                segment_key = 'space'
            
            if segment_key and segment_key in self.digit_to_segments:
                segment_data = self.digit_to_segments[segment_key]
                # 反向映射：将第一个字符映射到最后一个RAM地址，最后一个字符映射到第一个RAM地址
                ram_address_index = len(self.ram_addresses) - 1 - i
                ram_address = self.ram_addresses[ram_address_index] if ram_address_index >= 0 else self.ram_addresses[0]
                self.write_ram_to_ht1621(device_id, ram_address, segment_data)
            else:
                # 如果字符不在段码表中，显示为空白
                ram_address_index = len(self.ram_addresses) - 1 - i
                ram_address = self.ram_addresses[ram_address_index] if ram_address_index >= 0 else self.ram_addresses[0]
                self.write_ram_to_ht1621(device_id, ram_address, self.digit_to_segments.get('space', '00000000'))
        
        return True
    
    def handle_client_command(self, data):
        """处理客户端命令"""
        try:
            command = json.loads(data.decode('utf-8'))
            
            device_id = command.get('device_id', 1)
            display_data = command.get('display_data', '')
            
            if display_data == 'init':
                # 特殊命令：初始化HT1621
                success = self.init_ht1621(device_id)
                if success:
                    return {'status': 'success', 'message': f'HT1621设备 {device_id} 初始化完成'}
                else:
                    return {'status': 'error', 'message': f'HT1621设备 {device_id} 初始化失败'}
            else:
                # 显示数据
                success = self.display_data(device_id, display_data)
                if success:
                    return {'status': 'success', 'message': f'已显示: {display_data}'}
                else:
                    return {'status': 'error', 'message': f'显示数据失败: {display_data}'}
                
        except json.JSONDecodeError:
            return {'status': 'error', 'message': 'JSON格式错误'}
        except Exception as e:
            return {'status': 'error', 'message': f'处理命令时出错: {e}'}
    
    def start_server(self):
        """启动HT1621守护进程服务器"""
        print("启动HT1621抽象层守护进程...")
        
        # 创建HT1621 Socket
        if os.path.exists(self.ht1621_socket_path):
            os.unlink(self.ht1621_socket_path)
        
        self.ht1621_sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.ht1621_sock.bind(self.ht1621_socket_path)
        os.chmod(self.ht1621_socket_path, 0o777)  # 设置权限以便其他进程访问
        
        print(f"HT1621守护进程已启动，监听: {self.ht1621_socket_path}")
        print(f"连接到GPIO守护进程: {self.gpio_socket_path}")
        
        # 等待GPIO守护进程准备就绪
        print("等待GPIO守护进程准备就绪...")
        for attempt in range(10):  # 最多尝试10次
            if os.path.exists(self.gpio_socket_path):
                print("GPIO守护进程已准备就绪")
                break
            time.sleep(1)
        else:
            print("警告: 无法连接到GPIO守护进程，但继续启动")
        
        # 强制重新初始化所有已配置的设备
        print("开始初始化所有HT1621设备...")
        for device_id in sorted(self.device_mapping.keys()):
            try:
                print(f"正在初始化设备 {device_id}...")
                success = self.init_ht1621(device_id)
                if success:
                    # 显示测试信息确认初始化成功
                    self.display_data(device_id, "HELLO")
                    self.clear_display(device_id)
                    print(f"设备 {device_id} 初始化成功并已测试")
                else:
                    print(f"设备 {device_id} 初始化失败")
            except Exception as e:
                print(f"设备 {device_id} 初始化时发生异常: {e}")
                pass  # 如果设备不存在，跳过初始化
        
        try:
            while self.running:
                try:
                    data, addr = self.ht1621_sock.recvfrom(1024)
                    if data:
                        response = self.handle_client_command(data)
                        # 对于UDP，我们不直接回复，但可以记录操作
                        print(f"处理命令: {response}")
                except socket.error:
                    if self.running:
                        time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n正在停止HT1621守护进程...")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """清理资源"""
        try:
            self.gpio_sock.close()
            if hasattr(self, 'ht1621_sock'):
                self.ht1621_sock.close()
            if os.path.exists(self.ht1621_socket_path):
                os.unlink(self.ht1621_socket_path)
        except:
            pass


def main():
    import sys
    # 检查命令行参数
    debug = '--debug' in sys.argv or '-d' in sys.argv
    
    daemon = HT1621Daemon(debug=debug)
    try:
        daemon.start_server()
    except KeyboardInterrupt:
        print("\n收到中断信号，正在退出...")
        daemon.running = False
        daemon.cleanup()


if __name__ == '__main__':
    main()