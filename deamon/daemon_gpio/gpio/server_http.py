#!/usr/bin/env python3
"""
HTTP 服务器模块
提供REST API接口控制GPIO
"""

import json
from http.server import BaseHTTPRequestHandler


class HTTPRequestHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器，接口与 Unix Socket JSON 格式一致"""

    daemon = None  # 将在初始化时设置

    def log_message(self, format, *args):
        """自定义日志格式"""
        print(f"[HTTP] {self.address_string()} - {format % args}")

    def do_POST(self):
        """处理 POST 请求 - GPIO控制"""
        if self.path != '/gpio':
            self.send_error(404, "Not Found")
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')

            try:
                command = json.loads(body)
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON")
                return

            response = self.process_command(command)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))

        except Exception as e:
            self.send_error(500, str(e))

    def do_GET(self):
        """处理 GET 请求 - 查询状态"""
        if self.path not in ('/status', '/status/'):
            self.send_error(404, "Not Found")
            return

        try:
            response = self.process_command({'type': 'query_status'})

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))

        except Exception as e:
            self.send_error(500, str(e))

    def process_command(self, command):
        """处理命令并返回结果，与 Unix Socket 处理逻辑一致"""
        if self.daemon is None:
            return {'error': 'Daemon not initialized'}

        alias = command.get('alias')
        mode = command.get('mode')

        # 检查 alias 是否存在于配置中
        if not alias or alias not in self.daemon.controller_configs:
            return {'error': f'Unknown alias: {alias}', 'available': list(self.daemon.controller_configs.keys())}

        # 检查设备是否可用
        if alias not in self.daemon.controllers:
            return {'error': f'Device {alias} not available (check /dev/null config)'}

        controller = self.daemon.controllers[alias]
        controller_config = self.daemon.controller_configs[alias]

        if mode == 'set':
            return self._handle_set(command, controller, alias)
        elif mode == 'spi':
            return self._handle_spi(command, controller, controller_config, alias)
        elif mode == 'spi_multi':
            return self._handle_spi_multi(command, controller, controller_config, alias)
        elif command.get('type') == 'query_status':
            return self.daemon.get_current_gpio_status()

        return {'error': f'Unknown mode: {mode}'}

    def _handle_set(self, command, controller, alias):
        """处理set命令"""
        if 'gpio' in command and 'value' in command:
            controller.set_gpio({command['gpio']: command['value']})
            return {'success': True, 'alias': alias, 'gpio': command['gpio'], 'value': command['value']}
        elif 'gpios' in command and 'values' in command:
            gpio_states = dict(zip(command['gpios'], command['values']))
            controller.set_gpio(gpio_states)
            return {'success': True, 'alias': alias, 'gpios': command['gpios'], 'values': command['values']}
        return {'error': 'Missing gpio/value or gpios/values'}

    def _handle_spi(self, command, controller, controller_config, alias):
        """处理SPI命令"""
        if controller_config['mode'] != 'spi':
            return {'error': f'Device {alias} is not SPI mode'}

        spi_task = {
            'controller': controller,
            'config': controller_config,
            'command': command
        }
        self.daemon.spi_queue.put(spi_task)
        return {'success': True, 'message': 'SPI command queued', 'alias': alias, 'mode': 'spi'}

    def _handle_spi_multi(self, command, controller, controller_config, alias):
        """处理多路SPI命令"""
        if controller_config['mode'] != 'spi':
            return {'error': f'Device {alias} is not SPI mode'}

        spi_task = {
            'controller': controller,
            'config': controller_config,
            'command': command
        }
        self.daemon.spi_queue.put(spi_task)
        return {'success': True, 'message': 'SPI multi command queued', 'alias': alias, 'mode': 'spi_multi'}