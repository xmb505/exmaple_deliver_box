#!/usr/bin/env python3
"""
外卖柜状态机
实现外卖柜的核心业务逻辑
"""

import time
import random
import threading
from enum import Enum
import os
import sys

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hardware.gpio_controller import GPIOController
from hardware.lcd_controller import LCDController
from input.keyboard_handler import KeyboardHandler


class State(Enum):
    """系统状态枚举"""
    INIT = "init"                     # 初始化状态
    WAIT = "wait"                     # 等待状态
    RECEIVE = "receive"               # 存件状态
    RECEIVE_CHECK = "receive_check"   # 存件检查状态
    PICKUP = "pickup"                 # 取件状态


class DeliveryBoxMachine:
    """外卖柜状态机"""

    def __init__(self):
        # 硬件控制器
        self.gpio = GPIOController()
        self.lcd = LCDController()
        self.keyboard = KeyboardHandler()

        # 设置LCD的GPIO控制器引用
        self.lcd.set_gpio_controller(self.gpio)

        # 当前状态
        self.state = State.INIT

        # 内存数据库: {取件码: 柜子编号}
        self.pickup_codes = {}

        # 柜子状态: {柜子编号: "empty"/"occupied"}
        self.box_status = {1: "empty", 2: "empty"}

        # 当前操作的柜子
        self.current_box = None

        # 当前生成的取件码
        self.current_code = None

        # 计时器
        self.state_start_time = None
        self.backlight_timers = {}

        # 存件按钮上次状态
        self.last_store_button_state = None

        # 重新存件窗口 (60秒内可再次打开)
        self.reopen_window = {}  # {box_id: expire_time}

        # 运行标志
        self.running = True

        # 背光超时时间
        self.backlight_timeout = 10

        print("\n" + "="*50)
        print("智能外卖柜系统启动")
        print("="*50 + "\n")

    def generate_code(self):
        """生成6位随机取件码"""
        return ''.join([str(random.randint(0, 9)) for _ in range(6)])

    def init_hardware(self):
        """初始化硬件检测"""
        print("\n[初始化] 开始检测硬件...")

        errors = []

        # 连接GPIO状态socket
        if not self.gpio.connect_status_socket():
            errors.append("GPIO状态socket连接失败")

        # 连接键盘socket
        if not self.keyboard.connect():
            errors.append("键盘socket连接失败")

        # 初始化LCD
        self.lcd.init_all()

        # 给一点时间让状态同步
        time.sleep(0.5)

        # 查询当前状态并等待响应
        self.gpio.query_status()
        print("[初始化] 等待GPIO初始状态...")

        # 等待并接收current_status响应，最多等待3秒
        initial_status_received = False
        for _ in range(30):  # 30次 * 0.1秒 = 3秒
            msg = self.gpio.receive_status(timeout=0.1)
            if msg and msg.get('type') == 'current_status':
                print("[初始化] 已接收GPIO初始状态")
                initial_status_received = True
                break
            time.sleep(0.1)

        if not initial_status_received:
            print("[初始化] 警告: 未收到GPIO初始状态，将继续使用默认值")

        # 检测门传感器
        print("\n[初始化] 检测门传感器...")
        for box_id in [1, 2]:
            outer = self.gpio.is_outer_door_closed(box_id)
            inner = self.gpio.is_inner_door_closed(box_id)

            outer_str = "已关闭" if outer else "未关闭"
            inner_str = "已关闭" if inner else "未关闭"

            print(f"  柜子{box_id}: 外侧门{outer_str}, 内侧门{inner_str}")

            if not outer:
                errors.append(f"柱子{box_id}外侧门未关闭")
            if not inner:
                errors.append(f"柱子{box_id}内侧门未关闭")

        # 检测红外传感器
        print("\n[初始化] 检测红外传感器...")
        for box_id in [1, 2]:
            ir = self.gpio.has_item(box_id)
            ir_str = "有物品" if ir else "无物品"
            print(f"  柱子{box_id}: {ir_str}")

        # 设置键盘回调
        self.keyboard.set_callbacks(
            on_digit=self.on_keyboard_digit,
            on_enter=self.on_keyboard_enter,
            on_delete=self.on_keyboard_delete
        )

        if errors:
            print("\n[初始化] 检测失败!")
            for err in errors:
                print(f"  - {err}")
            return False

        print("\n[初始化] 所有硬件检测通过!")
        return True

    def on_keyboard_digit(self, buffer):
        """键盘数字输入回调"""
        # 点亮学生侧LCD背光
        self.lcd.display_input(buffer)
        self.reset_backlight_timer(2)

    def on_keyboard_enter(self, buffer):
        """键盘回车回调"""
        self.handle_pickup_input(buffer)

    def on_keyboard_delete(self, buffer):
        """键盘删除回调"""
        self.lcd.display_input(buffer if buffer else "      ")

    def reset_backlight_timer(self, lcd_id):
        """重置背光计时器"""
        if lcd_id in self.backlight_timers:
            self.backlight_timers[lcd_id].cancel()

        timer = threading.Timer(self.backlight_timeout, lambda: self.lcd.set_backlight(lcd_id, False))
        timer.daemon = True
        timer.start()
        self.backlight_timers[lcd_id] = timer

    def handle_pickup_input(self, code):
        """处理取件输入"""
        print(f"\n[取件] 输入验证码: {code}")

        if len(code) != 6:
            print("[取件] 错误: 验证码长度不正确")
            self.lcd.display_input("Error ")
            self.keyboard.clear_buffer()
            return

        if code in self.pickup_codes:
            box_id = self.pickup_codes[code]
            print(f"[取件] 验证成功! 打开柱子{box_id}内侧门")

            # 清除验证码
            del self.pickup_codes[code]

            # 进入取件状态
            self.current_box = box_id
            self.state = State.PICKUP
            self.state_start_time = time.time()

            # 打开内侧门
            self.gpio.open_box_inner_door(box_id)
            self.lcd.display_input("OPEN  ")

        else:
            print("[取件] 错误: 验证码不存在")
            self.lcd.display_input("Error ")
            self.keyboard.clear_buffer()

    def find_empty_box(self):
        """查找空闲柜子"""
        for box_id, status in self.box_status.items():
            if status == "empty":
                return box_id
        return None

    def check_store_button(self):
        """检测存件按钮 - 检测上升沿(0->1)，按钮按下时触发"""
        current_state = self.gpio.get_store_button_state()

        # 检测上升沿 (0->1): 松开->按下
        if self.last_store_button_state is not None:
            if self.last_store_button_state == 0 and current_state == 1:
                self.last_store_button_state = current_state
                return True

        self.last_store_button_state = current_state
        return False

    def check_reopen_window(self, box_id):
        """检查是否在重新存件窗口内"""
        if box_id in self.reopen_window:
            if time.time() < self.reopen_window[box_id]:
                return True
            else:
                del self.reopen_window[box_id]
        return False

    def run(self):
        """运行状态机"""
        # 初始化
        if not self.init_hardware():
            print("\n系统初始化失败，请检查硬件!")
            return

        self.state = State.WAIT
        print("\n" + "="*50)
        print("系统进入等待状态")
        print("="*50 + "\n")

        # 主循环
        while self.running:
            # 处理GPIO状态更新
            self.gpio.receive_status(timeout=0.01)

            # 处理键盘输入
            self.keyboard.process_event(timeout=0.01)

            # 状态机处理
            if self.state == State.WAIT:
                self.state_wait()
            elif self.state == State.RECEIVE:
                self.state_receive()
            elif self.state == State.RECEIVE_CHECK:
                self.state_receive_check()
            elif self.state == State.PICKUP:
                self.state_pickup()

            # 短暂休眠
            time.sleep(0.05)

    def state_wait(self):
        """等待状态"""
        # 检测存件按钮
        if self.check_store_button():
            # 查找空闲柜子
            box_id = self.find_empty_box()

            if box_id is None:
                print("[存件] 没有空闲柜子!")
                return

            # 检查是否在重新存件窗口
            if self.check_reopen_window(box_id):
                print(f"[存件] 重新打开柱子{box_id}外侧门")
            else:
                print(f"\n[存件] 外卖员按下按钮, 分配柱子{box_id}")

            # 进入存件状态
            self.current_box = box_id
            self.state = State.RECEIVE
            self.state_start_time = time.time()

            # 生成取件码
            self.current_code = self.generate_code()

            # 打开外侧门
            self.gpio.open_box_outer_door(box_id)

            # 显示柜子编号和取件码
            self.lcd.display_box_id(box_id)
            self.lcd.display_pickup_code(box_id, self.current_code)

            print(f"[存件] 取件码: {self.current_code}")

    def state_receive(self):
        """存件状态 - 等待外卖员存件并关门"""
        # 首先等待门被打开（电磁锁弹开，门检测从1变成0）
        if not hasattr(self, 'door_opened_flag'):
            self.door_opened_flag = False

        if not self.door_opened_flag:
            # 等待门打开（检测为0）
            if not self.gpio.is_outer_door_closed(self.current_box):
                print(f"[存件] 检测到外侧门已打开，等待外卖员存件...")
                self.door_opened_flag = True
            return

        # 门已打开过，现在等待门关闭
        if self.gpio.is_outer_door_closed(self.current_box):
            print(f"[存件] 检测到外侧门关闭, 等待稳定...")

            # 等待3秒让门稳定
            time.sleep(3)

            # 再次确认门已关闭
            self.gpio.receive_status()
            if self.gpio.is_outer_door_closed(self.current_box):
                print(f"[存件] 外侧门已稳定关闭")
                self.state = State.RECEIVE_CHECK
                self.state_start_time = time.time()
                # 清除门打开标志
                self.door_opened_flag = False

    def state_receive_check(self):
        """存件检查状态 - 检测是否有物品"""
        # 检测红外传感器
        has_item = self.gpio.has_item(self.current_box)

        if has_item:
            # 有物品，绑定验证码
            self.pickup_codes[self.current_code] = self.current_box
            self.box_status[self.current_box] = "occupied"

            print(f"[存件] 检测到物品, 柱子{self.current_box}已占用")
            print(f"[存件] 验证码 {self.current_code} 已绑定到柱子{self.current_box}")
        else:
            # 没有物品
            print(f"[存件] 未检测到物品!")
            print(f"[存件] 存件失败，请重新按按钮存件")

            # 清除取件码显示
            self.lcd.display(self.current_box + 2, "EMPTY ")
            self.lcd.set_backlight(self.current_box + 2, False)

        # 返回等待状态
        self.current_box = None
        self.current_code = None
        self.state = State.WAIT

        print("\n" + "-"*30)
        print("系统返回等待状态")
        print("-"*30 + "\n")

    def state_pickup(self):
        """取件状态 - 等待学生取件"""
        elapsed = time.time() - self.state_start_time

        # 检测内侧门是否关闭
        if self.gpio.is_inner_door_closed(self.current_box):
            print(f"[取件] 内侧门已关闭")

            # 等待稳定
            time.sleep(2)

            # 再次确认
            self.gpio.receive_status()
            if self.gpio.is_inner_door_closed(self.current_box):
                # 检测是否还有物品
                if self.gpio.has_item(self.current_box):
                    print(f"[取件] 检测到还有物品, 重新打开门!")
                    self.gpio.open_box_inner_door(self.current_box)
                    self.state_start_time = time.time()
                else:
                    print(f"[取件] 物品已取走")
                    self.gpio.close_box_inner_door(self.current_box)
                    self.box_status[self.current_box] = "empty"
                    self.current_box = None
                    self.state = State.WAIT
                    self.keyboard.clear_buffer()
                    self.lcd.display_input("      ")

                    print("\n" + "-"*30)
                    print("系统返回等待状态")
                    print("-"*30 + "\n")

        # 超时提醒
        elif elapsed > 60:
            print(f"[取件] 警告: 门已打开超过60秒, 请关门!")

        # 定期提醒
        elif elapsed > 30 and int(elapsed) % 10 == 0:
            print(f"[取件] 提示: 门已打开 {int(elapsed)} 秒")

    def stop(self):
        """停止状态机"""
        self.running = False
        self.gpio.close()
        self.keyboard.close()
        print("\n系统已停止")


def main():
    """主函数"""
    machine = DeliveryBoxMachine()

    try:
        machine.run()
    except KeyboardInterrupt:
        print("\n\n收到中断信号")
        machine.stop()


if __name__ == "__main__":
    main()
