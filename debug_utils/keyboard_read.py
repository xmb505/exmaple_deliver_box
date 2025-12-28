#!/usr/bin/env python3
"""
keyboard_read.py - 键盘事件监听工具
连接到键盘守护进程的状态监听Socket，持续打印键盘输入事件

用法:
    ./keyboard_read.py --socket_path /tmp/keyboard_get.sock
    ./keyboard_read.py --socket_path /tmp/keyboard_get.sock --query-interval 30  # 每30秒查询一次当前状态
"""

import argparse
import json
import socket
import sys
import os
import datetime
import threading
import time


def send_ack(sock, message_id, addr):
    """向服务器发送ACK确认"""
    ack_msg = {
        "type": "ack",
        "id": message_id
    }
    try:
        sock.sendto(json.dumps(ack_msg).encode('utf-8'), addr)
        return True
    except Exception as e:
        print(f"发送ACK失败: {e}")
        return False


def send_status_query(sock, addr):
    """向服务器发送状态查询请求"""
    query_msg = {
        "type": "query_status"
    }
    try:
        sock.sendto(json.dumps(query_msg).encode('utf-8'), addr)
        return True
    except Exception as e:
        print(f"发送状态查询失败: {e}")
        return False


def listen_keyboard_events(socket_path, query_interval=None):
    """
    连接到键盘事件监听Socket并持续监听事件
    
    Args:
        socket_path (str): 键盘事件监听Socket路径
        query_interval (int): 状态查询间隔（秒），None表示不主动查询
    """
    # 检查socket文件是否存在
    if not os.path.exists(socket_path):
        print(f"错误: socket文件不存在 - {socket_path}", file=sys.stderr)
        sys.exit(1)
    
    # 创建Unix socket用于发送和接收UDP消息
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    temp_socket_path = f"{socket_path}_listener_{os.getpid()}"
    if os.path.exists(temp_socket_path):
        os.unlink(temp_socket_path)
    
    sock.bind(temp_socket_path)
    os.chmod(temp_socket_path, 0o777)
    
    try:
        print(f"正在连接到键盘事件监听Socket: {socket_path}")
        
        # 连接成功后立即查询一次当前键盘状态，模拟开机时获取初始状态
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] 正在获取初始键盘状态（模拟开机状态）...")
        if send_status_query(sock, socket_path):
            print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] 已发送初始状态查询请求")
            # 等待一小段时间接收响应
            time.sleep(0.5)
        else:
            print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] 初始状态查询请求发送失败")
        
        print("成功设置键盘事件监听，开始监听事件...")
        print("按Ctrl+C退出监听")
        if query_interval:
            print(f"将每 {query_interval} 秒查询一次当前键盘状态")
        print("-" * 50)
        
        # 启动定期查询线程（如果指定了查询间隔）
        query_thread = None
        if query_interval:
            def query_loop():
                while True:
                    try:
                        time.sleep(query_interval)
                        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] 发送状态查询请求...")
                        if not send_status_query(sock, socket_path):
                            print("状态查询发送失败")
                    except:
                        # 查询线程异常退出
                        break
            
            query_thread = threading.Thread(target=query_loop, daemon=True)
            query_thread.start()
        
        while True:
            try:
                # 接收数据
                raw_data, addr = sock.recvfrom(1024)
                
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
                                                send_ack(sock, message_id, addr)
                                                if query_interval:  # 只在定期查询模式下打印ACK
                                                    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] 已发送ACK: {message_id}")
                                            
                                            # 格式化输出键盘事件
                                            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                                            
                                            # 根据消息类型处理
                                            if json_data.get('type') == 'current_status':
                                                # 输出当前键盘状态
                                                current_keys = json_data.get('current_keys', {})
                                                print(f"[{timestamp}] 当前键盘状态: {current_keys}")
                                            elif json_data.get('type') == 'key_event':
                                                event_type = json_data.get('event_type', 'unknown')
                                                key = json_data.get('key', 'unknown')
                                                
                                                if event_type == 'press':
                                                    key_code = json_data.get('key_code', 'N/A')
                                                    device = json_data.get('device', 'N/A')
                                                    print(f"[{timestamp}] 按键按下: {key} (码: {key_code}, 设备: {device})")
                                                elif event_type == 'release':
                                                    key_code = json_data.get('key_code', 'N/A')
                                                    device = json_data.get('device', 'N/A')
                                                    print(f"[{timestamp}] 按键释放: {key} (码: {key_code}, 设备: {device})")
                                                elif event_type == 'repeat':
                                                    # 忽略重复事件（长按），避免刷屏
                                                    pass
                                                else:
                                                    print(f"[{timestamp}] 键盘事件: {json.dumps(json_data, ensure_ascii=False)}")
                                            else:
                                                print(f"[{timestamp}] 键盘消息: {json.dumps(json_data, ensure_ascii=False)}")
                                                
                                            parsed_count += 1
                                        except json.JSONDecodeError:
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
                            print(f"[{timestamp}] 键盘原始数据: {json_str}")
                except Exception as e:
                    # 如果不是JSON格式，直接打印原始数据
                    decoded_data = raw_data.decode('utf-8', errors='ignore').strip()
                    if decoded_data:
                        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                        print(f"[{timestamp}] 键盘原始数据: {decoded_data}")
                        
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
        # 清理临时socket文件
        try:
            sock.close()
        except:
            pass
        try:
            if os.path.exists(temp_socket_path):
                os.unlink(temp_socket_path)
        except:
            pass


def main():
    parser = argparse.ArgumentParser(description="键盘事件监听工具")
    parser.add_argument("--socket_path", "-s", required=True, 
                        help="键盘事件监听Socket路径 (例如: /tmp/keyboard_get.sock)")
    parser.add_argument("--query-interval", "-q", type=int, 
                        help="状态查询间隔（秒），用于主动查询当前键盘状态")
    
    args = parser.parse_args()
    
    listen_keyboard_events(args.socket_path, args.query_interval)


if __name__ == '__main__':
    main()