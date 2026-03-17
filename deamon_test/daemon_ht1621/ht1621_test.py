#!/usr/bin/env python3
"""
HT1621守护进程测试脚本
"""

import json
import socket
import sys


def send_ht1621_command(ht1621_socket_path, command):
    """发送命令到HT1621守护进程"""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sock.connect(ht1621_socket_path)
        
        # 发送JSON命令
        json_data = json.dumps(command)
        sock.send(json_data.encode('utf-8'))
        
        print(f"已发送命令: {json_data}")
        
        sock.close()
        return True
    except Exception as e:
        print(f"发送命令失败: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("用法: ht1621_test.py <数字>")
        print("例如: ht1621_test.py 123456")
        sys.exit(1)
    
    display_data = sys.argv[1]
    
    # 创建命令
    command = {
        "device_id": 1,
        "display_data": display_data
    }
    
    # 发送到HT1621守护进程
    success = send_ht1621_command("/tmp/ht1621.sock", command)
    
    if success:
        print(f"成功发送显示命令: {display_data}")
    else:
        print("发送命令失败")


if __name__ == '__main__':
    main()