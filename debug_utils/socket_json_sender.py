#!/usr/bin/env python3
"""
socket_json_sender.py - 向Unix socket发送JSON数据的工具脚本

用法:
    socket_json_sender.py --socket-path [位置] --data '[json语句]'
    socket_json_sender.py -s [位置] -d '[json语句]'

示例:
    socket_json_sender.py --socket-path /tmp/gpio.sock --data '{"alias": "sender", "mode": "set", "gpio": 1, "value": 1}'
    socket_json_sender.py -s /tmp/gpio.sock -d '{"alias": "sender", "mode": "set", "gpios": [1, 2], "values": [0, 1]}'
"""

import argparse
import json
import socket
import sys
import os


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
        print(f"成功发送数据到 {socket_path}")
        print(f"发送的数据: {json_data}")
        
        sock.close()
        return True
        
    except socket.error as e:
        print(f"错误: 连接socket失败 - {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"错误: 发送数据时发生异常 - {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="向Unix socket发送JSON数据的工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
用法示例:
  %(prog)s --socket-path /tmp/gpio.sock --data '{"alias": "sender", "mode": "set", "gpio": 1, "value": 1}'
  %(prog)s -s /tmp/gpio.sock -d '{"alias": "sender", "mode": "set", "gpios": [1, 2], "values": [0, 1]}'

重要提示:
  JSON数据必须用单引号或双引号包围，以避免shell解析问题
  例如: --data '{"key": "value"}' 或 --data '{"key": "value"}'
        """
    )
    
    parser.add_argument(
        '--socket-path', '-s',
        required=True,
        help='Unix socket文件路径'
    )
    
    parser.add_argument(
        '--data', '-d',
        required=True,
        help='要发送的JSON数据字符串（必须用引号包围）'
    )
    
    args = parser.parse_args()
    
    # 发送JSON数据到socket
    success = send_json_to_socket(args.socket_path, args.data)
    
    if not success:
        sys.exit(1)


if __name__ == '__main__':
    main()