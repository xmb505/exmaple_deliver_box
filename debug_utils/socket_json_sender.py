#!/usr/bin/env python3
"""
socket_json_sender.py - Unix socket通信工具脚本

用法:
    # 发送模式 (默认)
    socket_json_sender.py --socket-path [位置] --side send --data '[json语句]'
    socket_json_sender.py --socket-path [位置] --type udp --side send --data '[json语句]'
    socket_json_sender.py --socket-path [位置] --type tcp --side send --data '[json语句]'
    
    # 接收模式 (监听)
    socket_json_sender.py --socket-path [位置] --side receive

示例:
    # UDP发送
    socket_json_sender.py --socket-path /tmp/gpio.sock --data '{"alias": "sender", "mode": "set", "gpio": 1, "value": 1}'
    # TCP发送
    socket_json_sender.py --socket-path /tmp/gpio_get.sock --type tcp --data '{"type": "query_status"}'
    # TCP监听
    socket_json_sender.py --socket-path /tmp/gpio_get.sock --type tcp --side receive
"""

import argparse
import json
import socket
import sys
import os
import datetime


def send_json_to_udp_socket(socket_path, json_data):
    """
    向指定的Unix UDP socket发送JSON数据
    
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
        # 创建Unix socket连接 (UDP)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sock.connect(socket_path)
        
        # 发送JSON数据
        sock.send(json_data.encode('utf-8'))
        print(f"成功发送UDP数据到 {socket_path}")
        print(f"发送的数据: {json_data}")
        
        sock.close()
        return True
        
    except socket.error as e:
        print(f"错误: 连接UDP socket失败 - {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"错误: 发送数据时发生异常 - {e}", file=sys.stderr)
        return False


def send_json_to_tcp_socket(socket_path, json_data):
    """
    向指定的Unix TCP socket发送JSON数据
    
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
        # 创建Unix socket连接 (TCP)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        
        # 连接socket
        sock.connect(socket_path)
        
        # 发送JSON数据
        sock.send(json_data.encode('utf-8'))
        print(f"成功发送TCP数据到 {socket_path}")
        print(f"发送的数据: {json_data}")
        
        # 尝试接收响应（可选）
        try:
            sock.settimeout(2.0)  # 设置2秒超时
            response = sock.recv(1024)
            if response:
                print(f"接收的响应: {response.decode('utf-8', errors='ignore')}")
        except socket.timeout:
            print("未收到响应或响应超时")
        except Exception as e:
            print(f"接收响应时出错: {e}")
        
        sock.close()
        return True
        
    except socket.error as e:
        print(f"错误: 连接TCP socket失败 - {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"错误: 发送数据时发生异常 - {e}", file=sys.stderr)
        return False


def receive_from_tcp_socket(socket_path):
    """
    从指定的Unix TCP socket接收JSON数据（监听模式）
    
    Args:
        socket_path (str): Unix socket文件路径
    
    Returns:
        bool: 监听成功返回True，否则返回False
    """
    # 检查socket文件是否存在
    if not os.path.exists(socket_path):
        print(f"错误: socket文件不存在 - {socket_path}", file=sys.stderr)
        return False
    
    try:
        # 创建Unix socket连接 (TCP)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        
        # 连接socket
        sock.connect(socket_path)
        print(f"已连接到TCP socket {socket_path}，开始监听...")
        print("按Ctrl+C退出监听")
        print("-" * 50)
        
        # 持续接收数据
        while True:
            try:
                # 接收数据
                data = sock.recv(1024)
                if not data:
                    print("连接断开")
                    break
                
                # 解析和打印接收到的数据
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                received_data = data.decode('utf-8', errors='ignore')
                print(f"[{timestamp}] 接收到: {received_data}")
                
            except KeyboardInterrupt:
                print("\n接收到中断信号，正在停止监听...")
                break
            except socket.error as e:
                print(f"Socket接收错误: {e}")
                break
            except Exception as e:
                print(f"处理接收到的数据时出错: {e}")
                continue
    
    except socket.error as e:
        print(f"错误: 连接TCP socket失败 - {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"错误: 监听过程中发生异常 - {e}", file=sys.stderr)
        return False
    finally:
        try:
            sock.close()
        except:
            pass
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Unix socket通信工具（支持TCP和UDP，支持发送和接收模式）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
用法示例:
  # UDP发送（默认）
  %(prog)s --socket-path /tmp/gpio.sock --data '{"alias": "sender", "mode": "set", "gpio": 1, "value": 1}'
  
  # TCP发送
  %(prog)s --socket-path /tmp/gpio_get.sock --type tcp --side send --data '{"type": "query_status"}'
  
  # TCP监听
  %(prog)s --socket-path /tmp/gpio_get.sock --type tcp --side receive

重要提示:
  - UDP socket主要用于发送控制命令（如GPIO控制、SPI通信）
  - TCP socket主要用于监听状态变化和查询状态
  - JSON数据必须用单引号或双引号包围，以避免shell解析问题
        """
    )
    
    parser.add_argument(
        '--socket-path', '-s',
        required=True,
        help='Unix socket文件路径'
    )
    
    parser.add_argument(
        '--data', '-d',
        help='要发送的JSON数据字符串（必须用引号包围）'
    )
    
    parser.add_argument(
        '--type', '-t',
        choices=['udp', 'tcp'],
        default='udp',
        help='Socket类型 (默认: udp)'
    )
    
    parser.add_argument(
        '--side', '-si',
        choices=['send', 'receive'],
        default='send',
        help='操作模式: send (发送) 或 receive (接收/监听) (默认: send)'
    )
    
    args = parser.parse_args()
    
    # 验证参数组合
    if args.side == 'send' and not args.data:
        print("错误: 发送模式需要 --data 参数", file=sys.stderr)
        sys.exit(1)
    
    if args.side == 'receive' and args.type == 'udp':
        print("错误: UDP不支持接收模式，仅TCP支持监听功能", file=sys.stderr)
        sys.exit(1)
    
    # 根据指定的类型和模式执行操作
    if args.side == 'send':
        if args.type == 'udp':
            success = send_json_to_udp_socket(args.socket_path, args.data)
        elif args.type == 'tcp':
            success = send_json_to_tcp_socket(args.socket_path, args.data)
    elif args.side == 'receive':
        success = receive_from_tcp_socket(args.socket_path)
    else:
        print(f"错误: 不支持的操作模式 - {args.side}", file=sys.stderr)
        sys.exit(1)
    
    if not success:
        sys.exit(1)


if __name__ == '__main__':
    main()