#!/usr/bin/env python3
"""
WebSocket 服务器模块
用于GPIO状态实时推送
"""

import socket
import threading
import hashlib
import base64


class WebSocketServer:
    """简单的 WebSocket 服务器，用于 GPIO 状态广播"""

    def __init__(self, port, clients_list, clients_lock):
        self.port = port
        self.clients = clients_list
        self.clients_lock = clients_lock
        self.running = True
        self.server_socket = None

    def run(self):
        """运行 WebSocket 服务器"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(10)

            while self.running:
                try:
                    self.server_socket.settimeout(1.0)
                    client_socket, addr = self.server_socket.accept()
                    threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, addr),
                        daemon=True
                    ).start()
                except socket.timeout:
                    continue
        except Exception as e:
            print(f"WebSocket服务器错误: {e}")

    def handle_client(self, client_socket, addr):
        """处理 WebSocket 客户端连接"""
        try:
            # 握手
            request = client_socket.recv(4096).decode('utf-8')
            if 'Upgrade: websocket' not in request:
                client_socket.close()
                return

            # 提取 Sec-WebSocket-Key 并计算 Accept
            key = None
            for line in request.split('\r\n'):
                if line.startswith('Sec-WebSocket-Key:'):
                    key = line.split(':', 1)[1].strip()
                    break

            if not key:
                client_socket.close()
                return

            # 计算 Sec-WebSocket-Accept (RFC 6455)
            GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
            accept_key = base64.b64encode(
                hashlib.sha1((key + GUID).encode()).digest()
            ).decode()

            response = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept_key}\r\n"
                "\r\n"
            )
            client_socket.send(response.encode())

            with self.clients_lock:
                self.clients.append(client_socket)
            print(f"WebSocket客户端连接: {addr}")

            # 保持连接并处理消息
            while self.running:
                try:
                    client_socket.settimeout(0.5)
                    data = client_socket.recv(4096)
                    if not data:
                        break
                except socket.timeout:
                    continue
                except:
                    break

        except Exception as e:
            print(f"WebSocket客户端错误: {e}")
        finally:
            with self.clients_lock:
                if client_socket in self.clients:
                    self.clients.remove(client_socket)
            try:
                client_socket.close()
            except:
                pass
            print(f"WebSocket客户端断开: {addr}")