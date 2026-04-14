#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能外卖柜状态机
Smart Delivery Cabinet State Machine
"""

import time
import logging
import threading
import queue

class CabinetStateMachine:
    """柜子状态机"""

    # 状态定义
    STATE_BOOT = "BOOT"
    STATE_WAITING_INIT = "WAITING_INIT"
    STATE_INITIALIZING = "INITIALIZING"
    STATE_CHECKING = "CHECKING"
    STATE_CLEARING = "CLEARING"
    STATE_IDLE = "IDLE"
    STATE_OCCUPIED = "OCCUPIED"
    STATE_PICKING = "PICKING"

    def __init__(self, config, gpio_controller, lcd_controller, buzzer_controller, 
                 door_controller, code_generator, code_validator, keyboard_handler, logger):
        """
        初始化状态机

        Args:
            config: 配置管理器
            gpio_controller: GPIO控制器
            lcd_controller: LCD控制器
            buzzer_controller: 嗡鸣器控制器
            door_controller: 门控制器
            code_generator: 验证码生成器
            code_validator: 验证码验证器
            keyboard_handler: 键盘处理器
            logger: 日志记录器
        """
        self.config = config
        self.gpio_controller = gpio_controller
        self.lcd_controller = lcd_controller
        self.buzzer_controller = buzzer_controller
        self.door_controller = door_controller
        self.code_generator = code_generator
        self.code_validator = code_validator
        self.keyboard_handler = keyboard_handler
        self.logger = logger

        # 当前状态
        self.current_state = self.STATE_BOOT

        # GPIO状态（用于去抖动）
        self.gpio_states = {}
        self.gpio_states_lock = threading.Lock()

        # 门状态去抖动
        self.courier_door_last_change = 0
        self.student_door_last_change = 0
        self.courier_door_stable_state = None
        self.student_door_stable_state = None
        # 门状态稳定时间（秒）
        self.door_stabilization_time = 2.0

        # 检查状态检查时间戳
        self.checking_last_check = 0
        self.checking_check_interval = 2.0  # 每2秒检查一次
        self.courier_door_open_time = None  # 记录外卖员门打开时间
        self.checking_after_init = False  # 标记是否是初始化后的检查

        # 清理状态检查时间戳
        self.clearing_last_check = 0
        self.clearing_check_interval = 2.0  # 每2秒检查一次
        self.student_door_open_time = None  # 记录学生门打开时间

        # 取物状态检查时间戳
        self.picking_last_check = 0
        self.picking_check_interval = 2.0  # 每2秒检查一次

        # 当前验证码
        self.current_code = None

        # 外卖员侧LCD显示时间戳
        self.courier_lcd_display_time = None
        self.courier_lcd_timeout = 60  # 60秒后关闭背光

        # 取物状态跟踪
        self.picking_door_closed_time = None  # 门关闭时间
        self.picking_door_stable_duration = 2.0  # 门需要稳定2秒
        self.picking_buzzer_active = False  # 嗡鸣器是否激活

        # 初始化按钮长按时间
        self.init_button_press_time = None

        # 运行标志
        self.running = False

        self.logger.info("状态机初始化完成")

    def start(self):
        """启动状态机"""
        self.running = True
        self.logger.info("状态机启动")
        
        # 立即进入BOOT状态
        self._transition_to(self.STATE_BOOT)

    def stop(self):
        """停止状态机"""
        self.running = False
        self.logger.info("状态机停止")

    def update(self):
        """更新状态机（在主循环中调用）"""
        # 更新门状态去抖动
        self._update_door_stable_states()

        # 持续检查长按按钮（事件驱动需要周期性检查）
        if self.current_state == self.STATE_WAITING_INIT:
            self._handle_waiting_init_gpio()

        # 持续检查清理状态（事件驱动需要周期性检查）
        if self.current_state == self.STATE_CLEARING:
            self._handle_clearing_gpio()

        # 持续检查取物状态（事件驱动需要周期性检查）
        if self.current_state == self.STATE_PICKING:
            self._handle_picking_gpio()

        # 检查CHECKING状态的门关闭
        if self.current_state == self.STATE_CHECKING:
            self._handle_checking_gpio()

        # 检查OCCUPIED状态的外卖员侧LCD超时
        if self.current_state == self.STATE_OCCUPIED:
            self._check_courier_lcd_timeout()

    def handle_gpio_event(self, event):
        """
        处理GPIO事件

        Args:
            event: GPIO事件字典
        """
        event_type = event.get('type')

        if event_type == 'gpio_change':
            # 更新GPIO状态
            self._update_gpio_states(event)
            # 根据状态处理事件
            self._handle_gpio_change(event)

        elif event_type == 'current_status':
            # 更新GPIO状态
            self._update_gpio_states(event)

    def _update_gpio_states(self, event):
        """更新GPIO状态"""
        gpios = event.get('gpios', [])
        for gpio_info in gpios:
            alias = gpio_info.get('alias')
            if alias == 'geter':
                # 处理GPIO变化事件（change_gpio）
                change_gpios = gpio_info.get('change_gpio', [])
                for change in change_gpios:
                    gpio_num = change.get('gpio')
                    bit = change.get('bit')
                    with self.gpio_states_lock:
                        self.gpio_states[gpio_num] = bit
                    self.logger.debug(f"GPIO {gpio_num} 状态变化: {bit}")

                    # 更新门传感器变化时间
                    if gpio_num == 5:  # 外卖员门传感器
                        self.courier_door_last_change = time.time()
                    elif gpio_num == 6:  # 学生门传感器
                        self.student_door_last_change = time.time()

                # 处理当前状态查询事件（current_gpio_states）
                current_states = gpio_info.get('current_gpio_states', {})
                if current_states:
                    for gpio_num_str, bit in current_states.items():
                        gpio_num = int(gpio_num_str)
                        with self.gpio_states_lock:
                            self.gpio_states[gpio_num] = bit
                        self.logger.info(f"GPIO {gpio_num} 初始状态: {bit}")

                        # 更新门传感器变化时间
                        if gpio_num == 5:  # 外卖员门传感器
                            self.courier_door_last_change = time.time()
                            # 初始状态立即更新稳定状态
                            self.courier_door_stable_state = bit
                            self.logger.info(f"外卖员门初始状态: {bit}")
                        elif gpio_num == 6:  # 学生门传感器
                            self.student_door_last_change = time.time()
                            # 初始状态立即更新稳定状态
                            self.student_door_stable_state = bit
                            self.logger.info(f"学生门初始状态: {bit}")

    def _update_door_stable_states(self):
        """更新门状态去抖动"""
        current_time = time.time()

        # 更新外卖员门状态
        with self.gpio_states_lock:
            courier_door_current = self.gpio_states.get(5, 1)
        # 如果从未收到过门传感器状态变化，或者当前状态与稳定状态不同
        if self.courier_door_last_change == 0 or courier_door_current != self.courier_door_stable_state:
            # 更新变化时间
            if courier_door_current != self.courier_door_stable_state:
                self.courier_door_last_change = current_time
            # 检查是否经过稳定时间
            elapsed = current_time - self.courier_door_last_change
            if elapsed >= self.door_stabilization_time:
                if self.courier_door_stable_state != courier_door_current:
                    self.courier_door_stable_state = courier_door_current

        # 更新学生门状态
        with self.gpio_states_lock:
            student_door_current = self.gpio_states.get(6, 1)
        # 如果从未收到过门传感器状态变化，或者当前状态与稳定状态不同
        if self.student_door_last_change == 0 or student_door_current != self.student_door_stable_state:
            # 更新变化时间
            if student_door_current != self.student_door_stable_state:
                self.student_door_last_change = current_time
            # 检查是否经过稳定时间
            elapsed = current_time - self.student_door_last_change
            if elapsed >= self.door_stabilization_time:
                if self.student_door_stable_state != student_door_current:
                    self.student_door_stable_state = student_door_current

    def get_stable_door_state(self, door):
        """
        获取稳定的门状态

        Args:
            door: 门类型 ('courier' 或 'student')

        Returns:
            int: 0=关闭，1=打开
        """
        if door == 'courier':
            # 如果稳定状态为None，返回当前GPIO状态
            if self.courier_door_stable_state is None:
                with self.gpio_states_lock:
                    return self.gpio_states.get(5, 1)
            return self.courier_door_stable_state
        elif door == 'student':
            # 如果稳定状态为None，返回当前GPIO状态
            if self.student_door_stable_state is None:
                with self.gpio_states_lock:
                    return self.gpio_states.get(6, 1)
            return self.student_door_stable_state
        else:
            return 0  # 默认关闭

    def _handle_gpio_change(self, event):
        """处理GPIO变化事件"""
        self.logger.info(f"处理GPIO变化事件，当前状态: {self.current_state}, GPIO状态: {self.gpio_states}")

        # 根据当前状态处理GPIO事件
        if self.current_state == self.STATE_WAITING_INIT:
            self._handle_waiting_init_gpio()
        elif self.current_state == self.STATE_CHECKING:
            self._handle_checking_gpio()
        elif self.current_state == self.STATE_CLEARING:
            self._handle_clearing_gpio()
        elif self.current_state == self.STATE_IDLE:
            self._handle_idle_gpio()
        elif self.current_state == self.STATE_PICKING:
            self._handle_picking_gpio()

    def _handle_waiting_init_gpio(self):
        """处理等待初始化状态的GPIO事件"""
        # 检查初始化按钮（GPIO 3）
        init_button = self.gpio_states.get(3, 1)

        if init_button == 0:  # 按下
            if self.init_button_press_time is None:
                self.init_button_press_time = time.time()
                self.logger.info("初始化按钮按下")
            else:
                # 检查是否长按5秒
                elapsed = time.time() - self.init_button_press_time
                if elapsed >= 5.0 and elapsed < 5.1:  # 只在刚达到5秒时记录一次
                    self.logger.info("初始化按钮长按5秒，开始初始化")
                    self._transition_to(self.STATE_INITIALIZING)
                    self.init_button_press_time = None
        else:  # 释放
            if self.init_button_press_time is not None:
                self.logger.info("初始化按钮释放")
            self.init_button_press_time = None

    def _handle_idle_gpio(self):
        """处理空闲状态的GPIO事件"""
        # 检查外卖员按钮（GPIO 4）
        courier_button = self.gpio_states.get(4, 1)

        if courier_button == 0:  # 按下
            self.logger.info("外卖员按钮按下，开始存物流程")
            self._handle_courier_button()

        # 检查红外传感器（GPIO 1, 2）- 如果检测到物品，直接进入占用状态
        ir1 = self.gpio_states.get(1, 1)  # 默认为1（无物品）
        ir2 = self.gpio_states.get(2, 1)  # 默认为1（无物品）
        has_item = (ir1 == 0) or (ir2 == 0)

        if has_item:
            # 检查门是否关闭，如果是，则生成验证码
            courier_door = self.get_stable_door_state('courier')
            if courier_door == 0:  # 门关闭
                self.logger.info("检测到柜内有物品且门已关闭，生成验证码")
                # 生成验证码
                self.current_code = self.code_generator.generate_code()
                # 显示验证码
                self.lcd_controller.display_courier(self.current_code)
                self.lcd_controller.set_courier_backlight(True)
                self.logger.info(f"柜子已占用，验证码: {self.current_code}")
                self._transition_to(self.STATE_OCCUPIED)

    def _handle_checking_gpio(self):
        """处理检查状态的GPIO事件"""
        current_time = time.time()

        # 检查外卖员门传感器（使用当前GPIO状态，而不是稳定状态，避免延迟）
        with self.gpio_states_lock:
            courier_door = self.gpio_states.get(5, 1)

        # 如果门关闭，检测柜内物品
        if courier_door == 0:  # 门关闭
            # 检查红外传感器（GPIO 1, 2）
            ir1 = self.gpio_states.get(1, 1)  # 默认为1（无物品）
            ir2 = self.gpio_states.get(2, 1)  # 默认为1（无物品）

            # 任一传感器触发（0=有物品）
            has_item = (ir1 == 0) or (ir2 == 0)

            self.logger.info(f"检查状态 - 门已关闭（稳定状态: {self.courier_door_stable_state}, 当前GPIO: {courier_door}），检测柜内物品")
            self.logger.info(f"检查状态 - 门已关闭，检测柜内物品 - GPIO1: {ir1}, GPIO2: {ir2}, 有物品: {has_item}")

            if has_item:
                if self.checking_after_init:
                    # 初始化后的检查发现物品，进入清理模式
                    self.logger.info("初始化检查发现柜内有物品，进入清理状态")
                    self._transition_to(self.STATE_CLEARING)
                else:
                    # 存物流程中的检查发现物品，进入占用状态
                    self.logger.info("存物流程检查发现柜内有物品，进入占用状态")
                    self._transition_to(self.STATE_OCCUPIED)
            else:
                self.logger.info("柜内无物品，进入空闲状态")
                self._transition_to(self.STATE_IDLE)
        else:
            # 如果门还没关，等待门关闭
            # 检查是否已经过了门锁脉冲时间，且门仍然打开
            if self.courier_door_open_time:
                time_since_open = current_time - self.courier_door_open_time
                # 等待至少3秒后才开始检测（给门关闭留出时间）
                if time_since_open >= 3.0:
                    # 但只有当门实际关闭时才检测物品
                    pass  # 门还没关，继续等待

    def _handle_clearing_gpio(self):
        """处理清理状态的GPIO事件"""
        current_time = time.time()

        # 检查学生门传感器（GPIO 6）- 使用当前GPIO状态
        student_door = self.gpio_states.get(6, 1)
        
        self.logger.debug(f"清理状态 - 当前门状态: {student_door}")

        if student_door == 0:  # 门关闭
            # 检查是否到了检查时间
            if current_time - self.clearing_last_check >= self.clearing_check_interval:
                self.clearing_last_check = current_time

                # 检查红外传感器
                ir1 = self.gpio_states.get(1, 1)  # 默认为1（无物品）
                ir2 = self.gpio_states.get(2, 1)  # 默认为1（无物品）
                has_item = (ir1 == 0) or (ir2 == 0)

                self.logger.info(f"清理状态检查 - GPIO1: {ir1}, GPIO2: {ir2}, 有物品: {has_item}")

                if has_item:
                    self.logger.info("清理后仍有物品，嗡鸣器提示")
                    self.buzzer_controller.flash_item_not_taken()
                    # 重新开门
                    self.door_controller.open_student_door()
                else:
                    self.logger.info("物品已清空，进入空闲状态")
                    self._transition_to(self.STATE_IDLE)

    def _handle_picking_gpio(self):
        """处理取物状态的GPIO事件"""
        current_time = time.time()

        # 检查学生门传感器（GPIO 6）- 使用当前GPIO状态
        student_door = self.gpio_states.get(6, 1)

        if student_door == 1:  # 门打开
            # 门打开时，关闭嗡鸣器
            if self.picking_buzzer_active:
                self.logger.info("门已打开，关闭嗡鸣器提示")
                self.gpio_controller.set_gpio(6, 1)  # 关闭嗡鸣器（拉高）
                self.picking_buzzer_active = False
            # 重置门关闭时间
            self.picking_door_closed_time = None
        else:  # 门关闭
            # 门刚关闭，记录时间
            if self.picking_door_closed_time is None:
                self.picking_door_closed_time = current_time
                self.logger.info("学生门已关闭，开始计时等待稳定")
            
            # 检查门是否稳定关闭了足够长的时间
            if current_time - self.picking_door_closed_time >= self.picking_door_stable_duration:
                # 门已稳定关闭，检测柜内是否有物品
                ir1 = self.gpio_states.get(1, 1)  # 默认为1（无物品）
                ir2 = self.gpio_states.get(2, 1)  # 默认为1（无物品）
                has_item = (ir1 == 0) or (ir2 == 0)

                self.logger.info(f"门已稳定关闭，检测柜内物品 - GPIO1: {ir1}, GPIO2: {ir2}, 有物品: {has_item}")

                if has_item:
                    # 有物品，重新开门并启动嗡鸣器提示
                    self.logger.info("取物后仍有物品，重新开门并启动嗡鸣器提示")
                    self.door_controller.open_student_door()
                    self.gpio_controller.set_gpio(6, 0)  # 打开嗡鸣器（拉低）
                    self.picking_buzzer_active = True
                else:
                    # 无物品，进入空闲状态
                    self.logger.info("物品已取完，进入空闲状态")
                    # 关闭嗡鸣器
                    if self.picking_buzzer_active:
                        self.gpio_controller.set_gpio(6, 1)
                        self.picking_buzzer_active = False
                    self._transition_to(self.STATE_IDLE)

    def _check_courier_lcd_timeout(self):
        """检查外卖员侧LCD显示超时"""
        if self.courier_lcd_display_time is None:
            return
        
        import time
        current_time = time.time()
        elapsed = current_time - self.courier_lcd_display_time
        
        if elapsed >= self.courier_lcd_timeout:
            self.logger.info(f"外卖员侧LCD显示超时（{elapsed:.1f}秒），关闭背光")
            self.lcd_controller.set_courier_backlight(False)
            self.courier_lcd_display_time = None  # 清除时间戳，避免重复关闭

    def handle_keyboard_event(self, event):
        """
        处理键盘事件

        Args:
            event: 键盘事件字典（来自keyboard_handler）
        """
        event_type = event.get('type')
        event_value = event.get('value')

        self.logger.info(f"收到键盘事件: type={event_type}, value={event_value}, state={self.current_state}")

        if self.current_state == self.STATE_OCCUPIED:
            # 处理验证码输入
            if event_type == 'submit':
                # 提交验证码
                input_code = event_value
                self.logger.info(f"输入验证码: {input_code}, 正确验证码: {self.current_code}")

                # 使用verify_code方法验证验证码
                success, message = self.code_validator.verify_code(input_code)
                if success:
                    self.logger.info(f"验证码正确，打开学生门: {message}")
                    self._transition_to(self.STATE_PICKING)
                else:
                    self.logger.info(f"验证码错误: {message}")
                    self.buzzer_controller.flash_error()
            elif event_type == 'timeout':
                # 输入超时
                self.logger.info("输入超时，清空输入")
                self.lcd_controller.display_student("      ")  # 清空显示
                self.lcd_controller.set_student_backlight(False)  # 关闭背光
                self.buzzer_controller.flash_error()
            elif event_type == 'input':
                # 输入事件 - 实时显示到学生侧LCD
                input_display = event_value.rjust(6)  # 右对齐，空格填充
                self.logger.info(f"学生侧LCD显示: '{input_display}' (原始输入: '{event_value}')")
                
                # 首次输入时初始化学生侧LCD并打开背光
                if len(event_value) == 1:
                    import time
                    # 重新使能学生侧LCD系统和显示
                    self.lcd_controller.set_lcd_sys_on(self.lcd_controller.student_lcd_id)
                    time.sleep(0.1)
                    self.lcd_controller.set_student_display_on()
                    time.sleep(0.1)
                    # 打开背光
                    self.lcd_controller.set_student_backlight(True)
                    self.logger.info("首次输入，初始化学生侧LCD并打开背光")
                
                self.lcd_controller.display_student(input_display)  # 显示当前输入
                
                self.logger.debug(f"更新学生侧LCD显示: {input_display}")
        else:
            self.logger.info(f"当前状态 {self.current_state} 不处理键盘输入")

    def _handle_courier_button(self):
        """处理外卖员按钮"""
        # 打开外卖员门
        self.door_controller.open_courier_door()

        # 记录开门时间，用于延迟检测
        import time
        self.courier_door_open_time = time.time()

        # 等待关门并检测物品
        self.logger.info("等待外卖员关门并检测物品")

        # 进入检测状态
        self._transition_to(self.STATE_CHECKING)

    def _transition_to(self, new_state):
        """转换到新状态"""
        old_state = self.current_state
        self.logger.info(f"状态转换: {self.current_state} -> {new_state}")

        # 退出当前状态
        self._exit_state(self.current_state)

        # 进入新状态
        self.current_state = new_state
        self._enter_state(new_state, old_state)

    def _exit_state(self, state):
        """退出状态"""
        self.logger.debug(f"退出状态: {state}")

    def _enter_state(self, state, previous_state=None):
        """进入状态"""
        self.logger.info(f"进入状态: {state}")

        if state == self.STATE_BOOT:
            # LCD已经在硬件初始化时初始化过了，这里直接进入等待初始化状态
            self._transition_to(self.STATE_WAITING_INIT)

        elif state == self.STATE_WAITING_INIT:
            self.logger.info("等待初始化按钮长按5秒...")

        elif state == self.STATE_INITIALIZING:
            # 播放初始化提示音
            self.buzzer_controller.beep()
            # 进入检查状态
            self._transition_to(self.STATE_CHECKING)

        elif state == self.STATE_CHECKING:
            self.logger.info("检查柜内是否有物品...")
            # 设置检查标志：如果是从INITIALIZING来的，则为初始化检查
            if previous_state == self.STATE_INITIALIZING:
                self.checking_after_init = True
            else:
                # 从其他状态来的（如IDLE），不是初始化检查
                self.checking_after_init = False

        elif state == self.STATE_CLEARING:
            # 打开学生门
            self.door_controller.open_student_door()

            # 记录开门时间
            import time
            self.student_door_open_time = time.time()
            
            # 确保学生侧LCD正常工作（针对可能受损的HT1621）
            self.lcd_controller.set_lcd_sys_on(self.lcd_controller.student_lcd_id)  # 使能系统
            time.sleep(0.1)  # 短暂延迟
            self.lcd_controller.set_student_display_on()  # 打开显示
            
            self.logger.info("打开学生门，等待清理物品")

        elif state == self.STATE_IDLE:
            # 清空LCD
            self.lcd_controller.clear_courier()
            self.lcd_controller.clear_student()
            # 关闭背光
            self.lcd_controller.set_courier_backlight(False)
            self.lcd_controller.set_student_backlight(False)
            self.logger.info("系统空闲，等待外卖员存物")

        elif state == self.STATE_OCCUPIED:
            # 生成验证码
            self.current_code = self.code_generator.generate_code()
            
            # 重新使能LCD系统和显示（针对可能受损的HT1621）
            import time
            self.lcd_controller.set_lcd_sys_on(self.lcd_controller.courier_lcd_id)  # 使能系统
            time.sleep(0.1)  # 短暂延迟
            self.lcd_controller.set_courier_display_on()  # 打开显示
            time.sleep(0.1)  # 短暂延迟
            self.lcd_controller.display_courier(self.current_code)  # 显示验证码
            self.lcd_controller.set_courier_backlight(True)
            
            # 记录显示时间
            self.courier_lcd_display_time = time.time()
            self.logger.info(f"柜子已占用，验证码: {self.current_code}")

        elif state == self.STATE_PICKING:
            # 打开学生门
            self.door_controller.open_student_door()
            # 记录开门时间
            import time
            self.student_door_open_time = time.time()
            # 关闭学生侧背光
            self.lcd_controller.set_student_backlight(False)
            # 关闭外卖员侧背光
            self.lcd_controller.set_courier_backlight(False)
            self.courier_lcd_display_time = None  # 清除时间戳
            
            # 确保学生侧LCD正常工作（针对可能受损的HT1621）
            self.lcd_controller.set_lcd_sys_on(self.lcd_controller.student_lcd_id)  # 使能系统
            time.sleep(0.1)  # 短暂延迟
            self.lcd_controller.set_student_display_on()  # 打开显示
            
            self.logger.info("打开学生门，等待取物")

    def get_current_state(self):
        """获取当前状态"""
        return self.current_state