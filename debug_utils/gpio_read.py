#!/usr/bin/env python3
"""
gpio_read.py - GPIO事件监听工具
连接到GPIO守护进程的状态监听Socket，持续打印输入GPIO状态变化事件

注意：此工具只监听配置为"geter"模式的GPIO输入设备状态变化
当输入GPIO状态发生变化时（如按钮按下、传感器触发），守护进程会发送事件

用法:
    ./gpio_read.py --socket_path /tmp/gpio_get.sock
    ./gpio_read.py --socket_path /tmp/gpio_get.sock --query-interval 30  # 每30秒查询一次当前状态
"""

import argparse
import json
import socket
import sys
import os
import datetime
import threading
import time


def send_ack(sock, message_id):
    """向服务器发送ACK确认"""
    ack_msg = {
        "type": "ack",
        "id": message_id
    }
    try:
        sock.send(json.dumps(ack_msg).encode('utf-8'))
        return True
    except Exception as e:
        print(f"发送ACK失败: {e}")
        return False


def send_status_query(sock):
    """向服务器发送状态查询请求"""
    query_msg = {
        "type": "query_status"
    }
    try:
        sock.send(json.dumps(query_msg).encode('utf-8'))
        return True
    except Exception as e:
        print(f"发送状态查询失败: {e}")
        return False


def listen_gpio_events(socket_path, query_interval=None):
    """
    连接到GPIO状态监听Socket并持续监听事件
    
    Args:
        socket_path (str): GPIO状态监听Socket路径
        query_interval (int): 状态查询间隔（秒），None表示不主动查询
    """
    # 检查socket文件是否存在
    if not os.path.exists(socket_path):
        print(f"错误: socket文件不存在 - {socket_path}", file=sys.stderr)
        sys.exit(1)
    
    try:
        # 创建Unix socket连接（TCP，因为状态监听使用TCP）
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        
        print(f"正在连接到GPIO状态监听Socket: {socket_path}")
        sock.connect(socket_path)
        
        print("成功连接到GPIO状态监听Socket，开始监听事件...")
        print("注意：只有当geter模式的GPIO设备状态发生变化时才会显示事件")
        print("按Ctrl+C退出监听")
        if query_interval:
            print(f"将每 {query_interval} 秒查询一次当前GPIO状态")
        print("-" * 50)
        
        # 启动定期查询线程（如果指定了查询间隔）
        query_thread = None
        if query_interval:
            def query_loop():
                while True:
                    try:
                        time.sleep(query_interval)
                        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] 发送状态查询请求...")
                        if not send_status_query(sock):
                            print("状态查询发送失败")
                    except:
                        # 查询线程异常退出
                        break
            
            query_thread = threading.Thread(target=query_loop, daemon=True)
            query_thread.start()
        
        # 从daemon_gpio.py代码可知，GPIO状态监听通过TCP连接发送JSON数据
        # 仅当geter模式的GPIO设备检测到状态变化时才会发送事件
        while True:
            try:
                # 接收数据 - 从daemon_gpio代码看，每次发送一个完整的JSON
                raw_data = sock.recv(1024)
                if not raw_data:
                    print("连接断开，尝试重新连接...")
                    break
                
                try:
                    # 解析JSON数据 - 处理可能粘连的多个JSON对象
                    json_str = raw_data.decode('utf-8').strip()
                    if json_str:  # 确保不是空字符串
                        # 尝试解析多个可能粘连的JSON对象
                        parsed_count = 0
                        start_idx = 0
                        
                        while start_idx < len(json_str):
                            # 寻找JSON对象的开始
                            obj_start = json_str.find('{', start_idx)
                            if obj_start == -1:
                                break
                            
                            # 寻找匹配的结束括号
                            brace_count = 0
                            i = obj_start
                            while i < len(json_str):
                                if json_str[i] == '{':
                                    brace_count += 1
                                elif json_str[i] == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        # 找到完整的JSON对象
                                        try:
                                            complete_json = json_str[obj_start:i+1]
                                            json_data = json.loads(complete_json)
                                            
                                            # 检查是否包含消息ID，如果包含则发送ACK
                                            if 'id' in json_data:
                                                message_id = json_data['id']
                                                send_ack(sock, message_id)
                                                print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] 已发送ACK: {message_id}")
                                            
                                            # 打印消息
                                            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # 包含毫秒
                                            print(f"[{timestamp}] GPIO事件: {json.dumps(json_data, ensure_ascii=False)}")
                                            parsed_count += 1
                                        except json.JSONDecodeError as e:
                                            print(f"JSON解析错误: {e}")
                                            # 如果解析失败，跳过这个位置
                                            pass
                                        start_idx = i + 1
                                        break
                                i += 1
                            else:
                                # 没有找到匹配的结束括号，可能是数据不完整
                                start_idx = len(json_str)
                        
                        # 如果没有解析到任何JSON对象，说明数据可能格式异常
                        if parsed_count == 0:
                            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                            print(f"[{timestamp}] GPIO原始数据: {json_str}")
                except Exception as e:
                    # 如果不是JSON格式，直接打印原始数据
                    decoded_data = raw_data.decode('utf-8', errors='ignore').strip()
                    if decoded_data:
                        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                        print(f"[{timestamp}] GPIO原始数据: {decoded_data}")
            except socket.error as e:
                print(f"Socket接收错误: {e}")
                break
            except Exception as e:
                print(f"处理接收到的数据时出错: {e}")
                continue  # 继续监听，不退出
    
    except KeyboardInterrupt:
        print("\n接收到中断信号，正在停止监听...")
    except socket.error as e:
        print(f"Socket连接错误: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"监听过程中发生错误: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        try:
            sock.close()
        except:
            pass


def main():
    parser = argparse.ArgumentParser(description="GPIO事件监听工具")
    parser.add_argument("--socket_path", "-s", required=True, 
                        help="GPIO状态监听Socket路径 (例如: /tmp/gpio_get.sock)")
    parser.add_argument("--query-interval", "-q", type=int, 
                        help="状态查询间隔（秒），用于主动查询当前GPIO状态")
    
    args = parser.parse_args()
    
    listen_gpio_events(args.socket_path, args.query_interval)


if __name__ == '__main__':
    main()
