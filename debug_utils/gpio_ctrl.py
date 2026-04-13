#!/usr/bin/env python3
"""
gpio_ctrl.py - 简易GPIO控制工具

用法:
    # 设置单个GPIO
    ./gpio_ctrl.py set <gpio编号> <0|1>

    # 批量设置多个GPIO
    ./gpio_ctrl.py set <gpio编号>=<值> <gpio编号>=<值> ...

    # 查询当前GPIO状态
    ./gpio_ctrl.py status

示例:
    ./gpio_ctrl.py set 1 1          # 将GPIO1置高
    ./gpio_ctrl.py set 3 0          # 将GPIO3置低
    ./gpio_ctrl.py set 1=1 2=0 3=1  # 批量设置GPIO1高、GPIO2低、GPIO3高
    ./gpio_ctrl.py status           # 查询所有GPIO当前状态
"""

import argparse
import json
import socket
import sys
import os

SOCKET_PATH = "/tmp/gpio.sock"
STATUS_SOCKET_PATH = "/tmp/gpio_get.sock"


def send_udp(socket_path, data: dict) -> bool:
    if not os.path.exists(socket_path):
        print(f"错误: socket不存在 - {socket_path}", file=sys.stderr)
        return False
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sock.connect(socket_path)
        sock.send(json.dumps(data).encode('utf-8'))
        sock.close()
        return True
    except socket.error as e:
        print(f"错误: {e}", file=sys.stderr)
        return False


def send_tcp_and_recv(socket_path, data: dict) -> bool:
    if not os.path.exists(socket_path):
        print(f"错误: socket不存在 - {socket_path}", file=sys.stderr)
        return False
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(socket_path)
        sock.send(json.dumps(data).encode('utf-8'))

        # 接收响应
        sock.settimeout(3.0)
        buf = b""
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
            except socket.timeout:
                break

        sock.close()

        if not buf:
            print("未收到响应")
            return False

        # 解析并打印状态
        raw = buf.decode('utf-8').strip()
        resp = json.loads(raw)
        if resp.get("type") == "current_status":
            print("当前GPIO状态:")
            for dev in resp.get("gpios", []):
                alias = dev.get("alias", "unknown")
                states = dev.get("current_gpio_states", {})
                print(f"  [{alias}]")
                for gpio_id, val in sorted(states.items(), key=lambda x: int(x[0])):
                    level = "高(1)" if val == 1 else "低(0)"
                    print(f"    GPIO{gpio_id}: {level}")
        else:
            print(f"响应: {json.dumps(resp, ensure_ascii=False, indent=2)}")
        return True

    except socket.error as e:
        print(f"错误: {e}", file=sys.stderr)
        return False
    except json.JSONDecodeError as e:
        print(f"解析响应失败: {e}", file=sys.stderr)
        return False


def cmd_set(args):
    """处理 set 子命令"""
    # 判断是单个设置还是批量设置
    # 单个: set <gpio> <value>
    # 批量: set 1=1 2=0 3=1
    if len(args.targets) == 2 and '=' not in args.targets[0] and '=' not in args.targets[1]:
        # 单个模式: gpio_ctrl.py set 1 1
        try:
            gpio_num = int(args.targets[0])
            value = int(args.targets[1])
            if value not in (0, 1):
                print("错误: 值必须为 0 或 1", file=sys.stderr)
                sys.exit(1)
        except ValueError:
            print("错误: gpio编号和值必须为整数", file=sys.stderr)
            sys.exit(1)

        data = {
            "alias": "sender",
            "mode": "set",
            "gpio": gpio_num,
            "value": value
        }
        print(f"设置 GPIO{gpio_num} -> {'高(1)' if value == 1 else '低(0)'}")
        if send_udp(SOCKET_PATH, data):
            print("发送成功")
        else:
            sys.exit(1)

    else:
        # 批量模式: gpio_ctrl.py set 1=1 2=0 3=1
        gpios = []
        values = []
        for item in args.targets:
            if '=' not in item:
                print(f"错误: 格式错误 '{item}'，批量模式请使用 gpio=value 格式", file=sys.stderr)
                sys.exit(1)
            parts = item.split('=', 1)
            try:
                g = int(parts[0])
                v = int(parts[1])
                if v not in (0, 1):
                    print(f"错误: GPIO{g} 的值必须为 0 或 1", file=sys.stderr)
                    sys.exit(1)
            except ValueError:
                print(f"错误: '{item}' 格式无效", file=sys.stderr)
                sys.exit(1)
            gpios.append(g)
            values.append(v)

        data = {
            "alias": "sender",
            "mode": "set",
            "gpios": gpios,
            "values": values
        }
        pairs = ", ".join(f"GPIO{g}->{'高(1)' if v == 1 else '低(0)'}" for g, v in zip(gpios, values))
        print(f"批量设置: {pairs}")
        if send_udp(SOCKET_PATH, data):
            print("发送成功")
        else:
            sys.exit(1)


def cmd_status(args):
    """处理 status 子命令"""
    if send_tcp_and_recv(STATUS_SOCKET_PATH, {"type": "query_status"}):
        pass
    else:
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="简易GPIO控制工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s set 1 1          将GPIO1置高
  %(prog)s set 3 0          将GPIO3置低
  %(prog)s set 1=1 2=0 3=1  批量设置GPIO1高、GPIO2低、GPIO3高
  %(prog)s status           查询所有GPIO当前状态
        """
    )

    subparsers = parser.add_subparsers(dest="command", metavar="命令")
    subparsers.required = True

    # set 子命令
    set_parser = subparsers.add_parser("set", help="设置GPIO电平")
    set_parser.add_argument(
        "targets", nargs="+",
        help="单个: <gpio编号> <0|1>  批量: <gpio>=<0|1> ..."
    )
    set_parser.set_defaults(func=cmd_set)

    # status 子命令
    status_parser = subparsers.add_parser("status", help="查询当前GPIO状态")
    status_parser.set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
