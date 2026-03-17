#!/usr/bin/env python3
"""
daemon_gpio测试脚本
用于测试GPIO守护进程的功能
"""

import json
import socket
import time
import threading


def test_gpio_control():
    """测试GPIO控制功能"""
    print("开始测试GPIO控制功能...")
    
    try:
        # 创建到GPIO守护进程的连接
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sock.connect('/tmp/gpio.sock')
        
        # 测试单个GPIO控制
        command = {
            "alias": "sender",
            "mode": "set",
            "gpio": 1,
            "value": 1
        }
        sock.send(json.dumps(command).encode('utf-8'))
        print("发送GPIO 1 设置为高电平命令")
        time.sleep(0.5)
        
        # 测试批量GPIO控制
        command = {
            "alias": "sender",
            "mode": "set",
            "gpios": [1, 2],
            "values": [0, 1]
        }
        sock.send(json.dumps(command).encode('utf-8'))
        print("发送GPIO 1设置为低电平, GPIO 2设置为高电平命令")
        time.sleep(0.5)
        
        # 测试SPI通信（如果配置了SPI）
        command = {
            "alias": "spi",
            "mode": "spi",
            "spi_num": 1,
            "spi_data_cs_collection": "down",
            "spi_data": "10000100"
        }
        sock.send(json.dumps(command).encode('utf-8'))
        print("发送SPI数据命令")
        time.sleep(0.5)
        
        # 测试多路SPI通信
        command = {
            "alias": "spi",
            "mode": "spi_multi",
            "spis": [
                {
                    "spi_num": 1,
                    "spi_data_cs_collection": "down",
                    "spi_data": "10000100"
                },
                {
                    "spi_num": 2,
                    "spi_data_cs_collection": "up",
                    "spi_data": "11001100"
                }
            ]
        }
        sock.send(json.dumps(command).encode('utf-8'))
        print("发送多路SPI数据命令")
        time.sleep(0.5)
        
        sock.close()
        print("GPIO控制功能测试完成")
        
    except Exception as e:
        print(f"GPIO控制功能测试出错: {e}")


def test_status_monitoring():
    """测试状态监听功能"""
    print("开始测试状态监听功能...")
    
    def listen_status():
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            client.connect('/tmp/gpio_get.sock')
            print("连接到状态监听服务")
            
            # 设置非阻塞模式并设置超时
            client.settimeout(5)  # 5秒超时
            
            # 监听状态更新（最多等待5秒）
            while True:
                try:
                    data = client.recv(1024)
                    if data:
                        print(f"收到GPIO状态更新: {data.decode('utf-8')}")
                    else:
                        break
                except socket.timeout:
                    print("状态监听超时，没有收到状态更新")
                    break
                except ConnectionResetError:
                    print("与状态监听服务的连接被重置")
                    break
                except Exception as e:
                    print(f"接收状态更新时出错: {e}")
                    break
        except Exception as e:
            print(f"连接状态监听服务失败: {e}")
        finally:
            client.close()
    
    # 启动监听线程，持续监听状态更新
    listen_thread = threading.Thread(target=listen_status, daemon=True)
    listen_thread.start()
    
    print("状态监听已启动...")
    time.sleep(6)  # 等待6秒
    print("状态监听功能测试完成")


def main():
    print("开始测试daemon_gpio...")
    
    print("\n注意: 请确保daemon_gpio守护进程正在运行")
    print("您可以使用以下命令启动守护进程（模拟模式）:")
    print("  python3 daemon_gpio.py --simulate")
    print("")
    
    choice = input("是否继续测试? (y/N): ")
    if choice.lower() != 'y':
        print("测试已取消")
        return
    
    # 测试GPIO控制功能
    test_gpio_control()
    
    print("\n" + "="*50 + "\n")
    
    # 测试状态监听功能
    test_status_monitoring()
    
    print("\n所有测试完成！")


if __name__ == '__main__':
    main()