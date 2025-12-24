#!/usr/bin/env python3
"""
ht1621_input_test.py - HT1621 LCD输入测试工具
通过SPI访问HT1621 LCD，实时显示用户输入的数字

用法:
    ./ht1621_input_test.py --socket_path /tmp/gpio.sock --device_alias spi --device_id 1
"""

import argparse
import json
import socket
import sys
import time
import os  # 需要导入os模块


def send_json_to_socket(socket_path, json_data):
    """
    向指定的Unix socket发送JSON数据
    
    Args:
        socket_path (str): Unix socket文件路径
        json_data (str): 要发送的JSON数据字符串
    
    Returns:
        bool: 发送成功返回True，否则返回False
    """
    # 验证JSON格式
    try:
        parsed_json = json.loads(json_data)
    except json.JSONDecodeError as e:
        print(f"错误: 无效的JSON格式 - {e}", file=sys.stderr)
        return False
    
    # 检查socket文件是否存在
    if not os.path.exists(socket_path):
        print(f"错误: socket文件不存在 - {socket_path}", file=sys.stderr)
        return False
    
    try:
        # 创建Unix socket连接
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sock.connect(socket_path)
        
        # 发送JSON数据
        sock.send(json_data.encode('utf-8'))
        
        sock.close()
        return True
        
    except socket.error as e:
        print(f"错误: 连接socket失败 - {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"错误: 发送数据时发生异常 - {e}", file=sys.stderr)
        return False


def send_frame_to_ht1621(socket_path, device_alias, device_id, frame):
    """
    发送帧数据到HT1621
    
    Args:
        socket_path (str): Unix socket路径
        device_alias (str): 设备别名
        device_id (int): 设备ID
        frame (str): 要发送的帧数据（二进制字符串）
    """
    command = {
        "alias": device_alias,
        "mode": "spi",
        "spi_num": device_id,
        "spi_data_cs_collection": "down",
        "spi_data": frame
    }
    return send_json_to_socket(socket_path, json.dumps(command))


def send_command_to_ht1621(socket_path, device_alias, device_id, cmd9):
    """
    发送命令到HT1621
    
    Args:
        socket_path (str): Unix socket路径
        device_alias (str): 设备别名
        device_id (int): 设备ID
        cmd9 (str): 9位命令（二进制字符串）
    """
    frame = "100" + cmd9  # HT1621命令格式：100 + 9位命令
    return send_frame_to_ht1621(socket_path, device_alias, device_id, frame)


def write_ram_to_ht1621(socket_path, device_alias, device_id, addr, data8):
    """
    向HT1621的RAM写入数据
    
    Args:
        socket_path (str): Unix socket路径
        device_alias (str): 设备别名
        device_id (int): 设备ID
        addr (int): RAM地址 (0-63)
        data8 (str): 8位数据（二进制字符串）
    """
    # 地址转6位二进制
    addr_bin = format(addr, '06b')
    frame = "101" + addr_bin + data8  # HT1621 RAM写入格式：101 + 6位地址 + 8位数据
    return send_frame_to_ht1621(socket_path, device_alias, device_id, frame)


def init_ht1621_lcd(socket_path, device_alias, device_id):
    """
    初始化HT1621 LCD
    """
    print("正在初始化HT1621 LCD...")
    
    # 发送初始化序列
    send_command_to_ht1621(socket_path, device_alias, device_id, "000000000")  # SYSDIS: 关闭系统
    time.sleep(0.01)
    send_command_to_ht1621(socket_path, device_alias, device_id, "001010110")  # BIAS: 1/3 Bias, 4 COM
    send_command_to_ht1621(socket_path, device_alias, device_id, "011000000")  # RC256: 使用内部RC振荡器
    send_command_to_ht1621(socket_path, device_alias, device_id, "000000010")  # SYSEN: 使能系统
    send_command_to_ht1621(socket_path, device_alias, device_id, "000000110")  # LCDON: 打开显示输出
    time.sleep(0.01)
    
    print("HT1621 LCD初始化完成！")


def clear_display(socket_path, device_alias, device_id):
    """
    清除显示（将所有RAM位置零）
    """
    # HT1621有16个RAM地址，对应32个4-bit段，足够显示6位数字
    # 为了清除显示，将每个RAM位置零
    for addr in range(0, 12, 2):  # 显示数字的RAM地址通常是0, 2, 4, 6, 8, 10
        write_ram_to_ht1621(socket_path, device_alias, device_id, addr, "00000000")


def display_number(socket_path, device_alias, device_id, number_str):
    """
    在HT1621上显示数字（修正版，解决显示顺序问题）
    
    Args:
        socket_path (str): Unix socket路径
        device_alias (str): 设备别名
        device_id (int): 设备ID
        number_str (str): 要显示的数字字符串
    """
    # 数字对应的段码 (共阴数码管)
    digit_to_segments = {
        '0': "01111101",  # 二进制 01111101 = 十六进制 0x7D
        '1': "01100000",  # 二进制 01100000 = 十六进制 0x60
        '2': "00111110",  # 二进制 00111110 = 十六进制 0x3E
        '3': "01111010",  # 二进制 01111010 = 十六进制 0x7A
        '4': "01100011",  # 二进制 01100011 = 十六进制 0x63
        '5': "01011011",  # 二进制 01011011 = 十六进制 0x5B
        '6': "01011111",  # 二进制 01011111 = 十六进制 0x5F
        '7': "01110000",  # 二进制 01110000 = 十六进制 0x70
        '8': "01111111",  # 二进制 01111111 = 十六进制 0x7F
        '9': "01111011",  # 二进制 01111011 = 十六进制 0x7B
        ' ': "00000000",  # 空白
    }
    
    # 限制输入长度为6位
    number_str = number_str[:6]
    
    # RAM地址: 0,2,4,6,8,10 对应数码管的 位0,位1,位2,位3,位4,位5 (从左到右)
    ram_addresses = [0, 2, 4, 6, 8, 10]
    
    # 根据您提到的显示顺序问题（输入123显示为321）
    # 这意味着RAM地址可能与显示顺序相反
    # 尝试将数字反向映射到RAM地址
    padded_number = number_str.ljust(6)  # 左对齐，右边填充空格
    
    # 将输入的数字按反向顺序映射到RAM地址
    # 例如：输入"123"，将'1'放到最右边的RAM位置，'3'放到最左边的RAM位置
    for i, digit in enumerate(padded_number):
        if digit in digit_to_segments:
            segment_data = digit_to_segments[digit]
            # 反向映射 - 将输入的第一个数字映射到最右边的RAM地址
            ram_address = ram_addresses[5-i]  # 从ram_addresses[5]开始，即10,8,6,4,2,0
            write_ram_to_ht1621(socket_path, device_alias, device_id, ram_address, segment_data)

def display_number_corrected(socket_path, device_alias, device_id, number_str):
    """
    在HT1621上显示数字（修正版，解决显示顺序问题）
    
    Args:
        socket_path (str): Unix socket路径
        device_alias (str): 设备别名
        device_id (int): 设备ID
        number_str (str): 要显示的数字字符串
    """
    # 数字对应的段码 (共阴数码管)
    digit_to_segments = {
        '0': "01111101",  # 二进制 01111101 = 十六进制 0x7D
        '1': "01100000",  # 二进制 01100000 = 十六进制 0x60
        '2': "00111110",  # 二进制 00111110 = 十六进制 0x3E
        '3': "01111010",  # 二进制 01111010 = 十六进制 0x7A
        '4': "01100011",  # 二进制 01100011 = 十六进制 0x63
        '5': "01011011",  # 二进制 01011011 = 十六进制 0x5B
        '6': "01011111",  # 二进制 01011111 = 十六进制 0x5F
        '7': "01110000",  # 二进制 01110000 = 十六进制 0x70
        '8': "01111111",  # 二进制 01111111 = 十六进制 0x7F
        '9': "01111011",  # 二进制 01111011 = 十六进制 0x7B
        ' ': "00000000",  # 空白
    }
    
    # 限制输入长度为6位
    number_str = number_str[:6]
    
    # RAM地址: 0,2,4,6,8,10 对应数码管的 位0,位1,位2,位3,位4,位5
    # 从左到右的地址映射
    ram_addresses = [0, 2, 4, 6, 8, 10]
    
    # 填充数字字符串到6位，右对齐
    padded_number = number_str.rjust(6)
    
    # 根据您的反馈，输入123显示为321，说明RAM地址映射可能与预期相反
    # 尝试将数字反序后映射到RAM地址
    for i, digit in enumerate(padded_number):
        if digit in digit_to_segments:
            segment_data = digit_to_segments[digit]
            ram_address = ram_addresses[i]
            write_ram_to_ht1621(socket_path, device_alias, device_id, ram_address, segment_data)
    
    # 如果上面的方法仍不能解决顺序问题，尝试反向映射
    # 例如，对于输入"123"，将'1'写到最右边的位置，'3'写到最左边的位置
    if len(number_str) > 0:  # 只在有实际输入时尝试修正
        reversed_number = number_str.ljust(6)  # 左对齐，右边填充空格
        for i, digit in enumerate(reversed_number):
            if digit in digit_to_segments:
                segment_data = digit_to_segments[digit]
                # 反向映射，将输入的第一个数字映射到最右边的RAM地址
                ram_address = ram_addresses[5-i]  # 从ram_addresses[5]开始，即10,8,6,4,2,0
                write_ram_to_ht1621(socket_path, device_alias, device_id, ram_address, segment_data)


def main():
    parser = argparse.ArgumentParser(description="HT1621 LCD输入测试工具")
    parser.add_argument("--socket_path", required=True, help="Unix socket路径")
    parser.add_argument("--device_alias", required=True, help="设备别名")
    parser.add_argument("--device_id", type=int, required=True, help="设备ID")
    
    args = parser.parse_args()
    
    # 检查socket文件是否存在
    if not os.path.exists(args.socket_path):
        print(f"错误: socket文件不存在 - {args.socket_path}", file=sys.stderr)
        sys.exit(1)
    
    # 初始化HT1621 LCD
    init_ht1621_lcd(args.socket_path, args.device_alias, args.device_id)
    
    # 清除显示
    clear_display(args.socket_path, args.device_alias, args.device_id)
    
    print("HT1621 LCD已准备就绪！")
    print("输入数字（最多6位）并按回车，LCD将实时显示输入的数字。")
    print("输入 'quit' 或 'exit' 退出程序。")
    print()
    
    try:
        while True:
            user_input = input("请输入数字: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("退出程序...")
                break
            
            # 验证输入 - 只允许数字
            if not all(c.isdigit() or c.isspace() for c in user_input):
                print("错误: 只允许输入数字，请重新输入。")
                continue
            
            # 显示输入的数字
            display_number_corrected(args.socket_path, args.device_alias, args.device_id, user_input)
            print(f"LCD已显示: {user_input}")
    
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序运行时发生错误: {e}")
    
    # 清除显示
    clear_display(args.socket_path, args.device_alias, args.device_id)
    print("已清除显示，程序结束。")


if __name__ == '__main__':
    main()