#!/usr/bin/env python3
"""
HT1621测试脚本
用于验证HT1621通信是否正常
"""

import serial
import time
import sys


class HT1621TestController:
    def __init__(self, device_path='/dev/ttyUSB0', baud_rate=115200):
        """
        初始化HT1621控制器
        :param device_path: USB2GPIO设备路径
        :param baud_rate: 波特率
        """
        self.device_path = device_path
        self.baud_rate = baud_rate
        self.ser = None
        
        # GPIO引脚定义
        self.DATA_PIN = 1  # 数据线
        self.WR_PIN = 2    # 写时钟
        self.CS_PIN = 3    # 片选
        
        try:
            self.ser = serial.Serial(self.device_path, self.baud_rate, timeout=0.001)
        except Exception as e:
            print(f"错误: 无法连接到设备 {self.device_path}: {e}", file=sys.stderr)
            sys.exit(1)
    
    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
    
    def send_gpio_command(self, gpio_states):
        """
        发送GPIO设置命令
        :param gpio_states: GPIO状态字典 {pin: state, ...}
        """
        command = bytearray([0x3A])
        for gpio_pin, state in gpio_states.items():
            command.append(gpio_pin)
            command.append(state)
        self.ser.write(bytes(command))
    
    def set_gpio(self, pin, state):
        """
        设置单个GPIO状态
        :param pin: GPIO引脚号
        :param state: 状态 (0=低电平, 1=高电平)
        """
        self.send_gpio_command({pin: state})
    
    def send_frame(self, frame_bits):
        """
        发送帧数据
        :param frame_bits: 帧数据位列表
        """
        # 拉低CS，开始传输
        self.set_gpio(self.CS_PIN, 0)
        
        for bit in frame_bits:
            # 设置数据位
            self.set_gpio(self.DATA_PIN, bit)
            # WR下降沿采样
            self.set_gpio(self.WR_PIN, 0)
            self.set_gpio(self.WR_PIN, 1)  # 拉高WR
        
        # 拉高CS，结束并应用
        self.set_gpio(self.CS_PIN, 1)
        time.sleep(0.001)  # 短暂延迟
    
    def send_command(self, cmd9):
        """
        发送命令 (100 + 9位命令)
        :param cmd9: 9位命令
        """
        frame_bits = [1, 0, 0]  # 起始码
        # 添加9位命令（最高位在前）
        for i in range(8, -1, -1):
            frame_bits.append((cmd9 >> i) & 1)
        self.send_frame(frame_bits)
    
    def write_ram(self, addr, data8):
        """
        写RAM (101 + 6位地址 + 8位数据)
        :param addr: RAM地址 (0-63)
        :param data8: 8位数据
        """
        frame_bits = [1, 0, 1]  # 起始码
        
        # 添加6位地址（最高位在前）
        for i in range(5, -1, -1):
            frame_bits.append((addr >> i) & 1)
        
        # 添加8位数据（最高位在前）
        for i in range(7, -1, -1):
            frame_bits.append((data8 >> i) & 1)
        
        self.send_frame(frame_bits)
    
    def init_ht1621(self):
        """
        初始化HT1621 (共阴，6位数码管)
        """
        print("设置GPIO引脚状态...")
        # 设置CS默认高电平，WR初始低电平，DATA初始化为低电平
        self.set_gpio(self.CS_PIN, 1)
        self.set_gpio(self.WR_PIN, 0)
        self.set_gpio(self.DATA_PIN, 0)
        time.sleep(0.01)
        
        print("发送HT1621初始化命令...")
        # 发送初始化序列
        self.send_command(0b000000000)  # SYSDIS: 关闭系统
        time.sleep(0.01)
        self.send_command(0b001010110)  # BIAS: 1/3 Bias, 4 COM
        self.send_command(0b011000000)  # RC256: 使用内部RC振荡器
        self.send_command(0b000000010)  # SYSEN: 使能系统
        self.send_command(0b000000110)  # LCDON: 打开显示输出
        time.sleep(0.01)
        print("HT1621初始化完成！")
    
    def display_digit(self, digit, position=0):
        """
        在指定位置显示单个数字
        :param digit: 要显示的数字 (0-9)
        :param position: 显示位置 (0-5)
        """
        # 数字对应的段码 (共阴数码管)
        digit_to_segments = {
            0: 0b01111101,  # 二进制 01111101 = 十进制 125 = 十六进制 0x7D
            1: 0b01100000,  # 二进制 01100000 = 十进制 96 = 十六进制 0x60
            2: 0b00111110,  # 二进制 00111110 = 十进制 62 = 十六进制 0x3E
            3: 0b01111010,  # 二进制 01111010 = 十进制 122 = 十六进制 0x7A
            4: 0b01100011,  # 二进制 01100011 = 十进制 99 = 十六进制 0x63
            5: 0b01011011,  # 二进制 01011011 = 十进制 91 = 十六进制 0x5B
            6: 0b01011111,  # 二进制 01011111 = 十进制 95 = 十六进制 0x5F
            7: 0b01110000,  # 二进制 01110000 = 十进制 112 = 十六进制 0x70
            8: 0b01111111,  # 二进制 01111111 = 十进制 127 = 十六进制 0x7F
            9: 0b01111011,  # 二进制 01111011 = 十进制 123 = 十六进制 0x7B
        }
        
        if digit not in digit_to_segments:
            print(f"错误: 数字 {digit} 不在有效范围内 (0-9)")
            return
        
        # 计算RAM地址 (每个数字需要2个RAM地址，地址间隔2)
        ram_address = position * 2  # 0, 2, 4, 6, 8, 10 对应 6个数码管位
        
        segment_data = digit_to_segments[digit]
        print(f"在位置 {position} 显示数字 {digit} (RAM地址 {ram_address}, 段码 {bin(segment_data)})")
        self.write_ram(ram_address, segment_data)
    
    def display_all_digits(self):
        """
        测试：显示所有数字0-9
        """
        print("开始测试显示数字0-9...")
        for i in range(10):
            print(f"显示数字 {i}...")
            self.display_digit(i, 0)  # 只在第一个位置显示
            time.sleep(1)
    
    def display_number(self, number):
        """
        在6位数码管上显示数字
        :param number: 要显示的数字 (0-999999)
        """
        # 数字对应的段码 (共阴数码管)
        digit_to_segments = {
            0: 0b01111101,  # 二进制 01111101 = 十进制 125 = 十六进制 0x7D
            1: 0b01100000,  # 二进制 01100000 = 十进制 96 = 十六进制 0x60
            2: 0b00111110,  # 二进制 00111110 = 十进制 62 = 十六进制 0x3E
            3: 0b01111010,  # 二进制 01111010 = 十进制 122 = 十六进制 0x7A
            4: 0b01100011,  # 二进制 01100011 = 十进制 99 = 十六进制 0x63
            5: 0b01011011,  # 二进制 01011011 = 十进制 91 = 十六进制 0x5B
            6: 0b01011111,  # 二进制 01011111 = 十进制 95 = 十六进制 0x5F
            7: 0b01110000,  # 二进制 01110000 = 十进制 112 = 十六进制 0x70
            8: 0b01111111,  # 二进制 01111111 = 十进制 127 = 十六进制 0x7F
            9: 0b01111011,  # 二进制 01111011 = 十进制 123 = 十六进制 0x7B
        }
        
        # 将数字转换为6位字符串（不足前面补0）
        num_str = f"{number:06d}"
        
        # 显示每一位数字到对应的RAM地址
        # RAM地址: 0,2,4,6,8,10 对应数码管的 位0,位1,位2,位3,位4,位5
        ram_addresses = [0, 2, 4, 6, 8, 10]  # 每个RAM地址间隔2（因为每个RAM只有4个数据位，一个段码需要2个地址）
        
        print(f"显示数字: {number}")
        for i in range(6):
            digit = int(num_str[i])
            segment_data = digit_to_segments[digit]
            ram_address = ram_addresses[i]
            print(f"位置 {i}: 数字 {digit} -> RAM地址 {ram_address} -> 段码 {bin(segment_data)}")
            self.write_ram(ram_address, segment_data)


def main():
    print("HT1621测试开始...")
    
    # 初始化HT1621控制器（使用/dev/ttyUSB0）
    controller = HT1621TestController('/dev/ttyUSB0')
    
    try:
        print("初始化HT1621...")
        controller.init_ht1621()
        print("HT1621初始化完成！")
        
        print("显示数字0...")
        controller.display_number(0)
        print("数字0已显示！")
        
        time.sleep(2)  # 延迟2秒观察结果
        
        print("显示数字123456...")
        controller.display_number(123456)
        print("数字123456已显示！")
        
        time.sleep(2)  # 延迟2秒观察结果
        
        print("显示数字987654...")
        controller.display_number(987654)
        print("数字987654已显示！")
        
        time.sleep(2)  # 延迟2秒观察结果
        
        print("测试完成！")
        
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        controller.close()


if __name__ == "__main__":
    main()
