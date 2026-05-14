#!/usr/bin/env python3
"""
USB GPIO 控制器模块
封装与 USB2GPIO 设备的串口通信
"""

import serial
import time
import threading


class USBGPIOController:
    """USB GPIO 控制器类"""

    def __init__(self, tty_path, baudrate=115200, simulate=False, debug=False):
        self.tty_path = tty_path
        self.baudrate = baudrate
        self.ser = None
        self.simulate = simulate
        self.debug = debug
        self.gpio_states = {}  # 用于模拟模式下的GPIO状态
        self.current_gpio_states = {}  # 当前各GPIO引脚的状态
        self.data_buffer = ""  # 数据缓冲区，用于累积流式数据避免截断
        self._lock = threading.Lock()  # 串口操作锁，防止并发竞争

        if not simulate:
            self.connect()
        else:
            print(f"USB GPIO控制器运行在模拟模式，设备: {self.tty_path}")

    def connect(self):
        """连接到USB GPIO设备"""
        try:
            self.ser = serial.Serial(self.tty_path, self.baudrate, timeout=0.001)
            print(f"成功连接到 {self.tty_path}")
        except Exception as e:
            print(f"错误: 无法连接到设备 {self.tty_path}: {e}")
            raise

    def reconnect(self):
        """重新连接到设备"""
        if self.ser:
            try:
                self.ser.close()
            except:
                pass
        time.sleep(1)
        self.connect()

    def send_command(self, command):
        """发送命令到USB GPIO设备"""
        if hasattr(self, 'debug') and self.debug:
            print(f"调试: 发送指令 - {[hex(b) for b in command]}")

        if self.simulate:
            self._simulate_command(command)
            return True

        if not self.ser or not self.ser.is_open:
            try:
                self.reconnect()
            except:
                return False

        try:
            self.ser.write(command)
            return True
        except Exception as e:
            print(f"发送命令失败: {e}")
            try:
                self.reconnect()
            except:
                pass
            return False

    def _simulate_command(self, command):
        """模拟模式：解析命令并更新GPIO状态"""
        if command[0] == 0x3A:  # GPIO设置命令
            i = 1
            while i < len(command):
                if i + 1 < len(command):
                    pin = command[i]
                    state = command[i + 1]
                    self.gpio_states[pin] = state
                    self.current_gpio_states[pin] = state
                    i += 2
                else:
                    break
        elif command[0] == 0x3F:  # GPIO读取命令
            pin = command[1]
            state = self.gpio_states.get(pin, 0)

    def set_gpio(self, gpio_states):
        """
        设置GPIO状态，gpio_states为字典 {pin: state, ...}
        优化：只对状态发生变化的GPIO引脚发送命令
        线程安全：使用锁保护串口操作，防止并发竞争
        """
        with self._lock:
            changed_states = {}
            for pin, new_state in gpio_states.items():
                gpio_pin = int(pin)
                state = int(new_state)
                current_state = self.current_gpio_states.get(gpio_pin)
                if current_state is None or current_state != state:
                    changed_states[gpio_pin] = state
                    self.current_gpio_states[gpio_pin] = state

            if not changed_states:
                return True

            command = bytearray([0x3A])
            for gpio_pin, state in changed_states.items():
                command.append(gpio_pin)
                command.append(state)
            return self.send_command(bytes(command))

    def read_gpio(self, gpio_pin):
        """读取单个GPIO状态"""
        if self.simulate:
            return self.gpio_states.get(gpio_pin, 0)

        command = bytearray([0x3F, gpio_pin])
        if not self.send_command(bytes(command)):
            return None

        time.sleep(0.01)
        if self.ser.in_waiting >= 3:
            response = self.ser.read(3)
            if len(response) == 3 and response[0] == 0x2F and response[1] == gpio_pin:
                return response[2]
        return None

    def set_spi(self, clk_pin, data_pin, cs_pin, data, cs_collection="down", lag_time=0.001, debug_spi=False):
        """使用bit-banging方式实现SPI通信，支持任意比特数"""
        import time

        start_time = time.time()

        if debug_spi:
            lag_time_ms = lag_time * 1000
            print(f"[SPI调试] 开始SPI传输 - CLK:{clk_pin}, DATA:{data_pin}, CS:{cs_pin}, 数据长度:{len(data)}, CS触发方式:{cs_collection}, 每次操作延迟:{lag_time_ms:.3f}ms")

        if self.simulate:
            if debug_spi:
                print(f"模拟SPI通信: CLK={clk_pin}, DATA={data_pin}, CS={cs_pin}")
            total_ops = 3 + len(data) * 3
            time.sleep(total_ops * lag_time)
            if debug_spi:
                print(f"[SPI调试] 模拟传输完成")
            return

        # 拉低CS（开始传输）
        self.set_gpio({cs_pin: 0})
        time.sleep(lag_time)

        # 发送数据（每一位）
        last_data_state = None
        last_clk_state = None

        for i, bit in enumerate(data):
            if bit == ' ':
                continue

            bit = int(bit)
            if last_data_state is None or last_data_state != bit:
                self.set_gpio({data_pin: bit})
                time.sleep(lag_time)
                last_data_state = bit
            else:
                time.sleep(lag_time)

            # 时钟脉冲
            if cs_collection == "down":
                if last_clk_state is None or last_clk_state != 1:
                    self.set_gpio({clk_pin: 1})
                    last_clk_state = 1
                else:
                    time.sleep(lag_time)
                time.sleep(lag_time)
                if last_clk_state != 0:
                    self.set_gpio({clk_pin: 0})
                    last_clk_state = 0
            else:
                if last_clk_state is None or last_clk_state != 0:
                    self.set_gpio({clk_pin: 0})
                    last_clk_state = 0
                else:
                    time.sleep(lag_time)
                time.sleep(lag_time)
                if last_clk_state != 1:
                    self.set_gpio({clk_pin: 1})
                    last_clk_state = 1

            time.sleep(lag_time)

        # 拉高CS（结束传输）
        self.set_gpio({cs_pin: 1})
        time.sleep(lag_time)

        if debug_spi:
            end_time = time.time()
            print(f"[SPI调试] SPI传输完成，总耗时: {end_time - start_time:.6f}s")