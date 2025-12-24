#!/usr/bin/env python3

import sys
import serial
import configparser
import time
from pathlib import Path


class USBGPIOController:
    def __init__(self, config_path='config.ini'):
        config = configparser.ConfigParser()
        config.read(config_path)
        
        self.device_path = config.get('device', 'device_path', fallback='/dev/ttyUSB0')
        self.baud_rate = config.getint('device', 'baud_rate', fallback=115200)
        
        try:
            self.ser = serial.Serial(self.device_path, self.baud_rate, timeout=0.001)
        except Exception as e:
            print(f"错误: 无法连接到设备 {self.device_path}: {e}", file=sys.stderr)
            sys.exit(1)
    
    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
    
    def send_command(self, command):
        self.ser.write(command)
    
    def set_gpio(self, gpio_states):
        command = bytearray([0x3A])
        for gpio_pin, state in gpio_states.items():
            command.append(gpio_pin)
            command.append(state)
        self.ser.write(bytes(command))


def parse_set_command(args):
    gpio_states = {}
    for i in range(0, len(args), 2):
        gpio_states[int(args[i])] = int(args[i + 1])
    return gpio_states


def print_usage():
    print("用法: ./usb2gpio.py [--debug-timer] set <引脚号> <状态> [引脚号 状态 ...]")
    print()
    print("选项:")
    print("  --debug-timer                       - 显示命令执行时间（毫秒）")
    print()
    print("命令:")
    print("  set <引脚号> <状态> [引脚号 状态 ...]      - 批量设置GPIO状态")
    print()
    print("示例:")
    print("  ./usb2gpio.py set 1 1              - 设置引脚1为高电平")
    print("  ./usb2gpio.py set 1 0              - 设置引脚1为低电平")
    print("  ./usb2gpio.py set 1 1 2 1          - 设置引脚1和2为高电平")
    print("  ./usb2gpio.py --debug-timer set 1 1 - 设置引脚1为高电平并显示执行时间")


def main():
    debug_timer = '--debug-timer' in sys.argv
    if debug_timer:
        sys.argv.remove('--debug-timer')
        start_time = time.perf_counter()
    
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'set':
        if len(sys.argv) < 4:
            print("错误: set命令至少需要一对参数（引脚号 状态）", file=sys.stderr)
            print_usage()
            sys.exit(1)
        
        gpio_states = parse_set_command(sys.argv[2:])
        if gpio_states is None:
            sys.exit(1)
        
        controller = USBGPIOController()
        
        try:
            controller.set_gpio(gpio_states)
            if debug_timer:
                elapsed_time = (time.perf_counter() - start_time) * 1000
                print(f"执行时间: {elapsed_time:.2f}ms")
        finally:
            controller.close()
    
    else:
        print(f"错误: 未知命令 '{command}'", file=sys.stderr)
        print_usage()
        sys.exit(1)


if __name__ == '__main__':
    main()
