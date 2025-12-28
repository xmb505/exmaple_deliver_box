#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
应用层测试脚本
Application Layer Test Script
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.config_loader import ConfigLoader
from log_system.logger_setup import setup_logging

def test_config():
    """测试配置加载"""
    print("=" * 60)
    print("测试配置加载")
    print("=" * 60)

    try:
        config = ConfigLoader()
        config.load()

        # 测试读取配置
        print(f"GPIO控制Socket: {config.get('daemon_config', 'gpio_control_socket')}")
        print(f"GPIO监听Socket: {config.get('daemon_config', 'gpio_monitor_socket')}")
        print(f"HT1621 Socket: {config.get('daemon_config', 'ht1621_socket')}")
        print(f"键盘监听Socket: {config.get('daemon_config', 'keyboard_monitor_socket')}")

        print(f"\n门锁通电时间: {config.get_float('door_control', 'door_lock_pulse_duration')}秒")
        print(f"红外稳定时间: {config.get_float('ir_sensor', 'ir_sensor_stabilization')}秒")
        print(f"验证码长度: {config.get_int('pickup_code', 'pickup_code_length')}")

        print("\n✓ 配置加载测试通过")
        return True

    except Exception as e:
        print(f"\n✗ 配置加载测试失败: {e}")
        return False

def test_logging():
    """测试日志系统"""
    print("\n" + "=" * 60)
    print("测试日志系统")
    print("=" * 60)

    try:
        config = ConfigLoader()
        config.load()
        logger = setup_logging(config)

        logger.debug("这是DEBUG日志")
        logger.info("这是INFO日志")
        logger.warning("这是WARNING日志")
        logger.error("这是ERROR日志")

        print("\n✓ 日志系统测试通过")
        return True

    except Exception as e:
        print(f"\n✗ 日志系统测试失败: {e}")
        return False

def test_code_generator():
    """测试验证码生成器"""
    print("\n" + "=" * 60)
    print("测试验证码生成器")
    print("=" * 60)

    try:
        config = ConfigLoader()
        config.load()
        logger = setup_logging(config)

        from pickup_code.code_generator import PickupCodeGenerator

        generator = PickupCodeGenerator(config, logger)

        # 生成5个验证码
        codes = []
        for i in range(5):
            code = generator.generate_code()
            codes.append(code)
            print(f"生成验证码 {i+1}: {code}")

        # 测试唯一性
        if len(set(codes)) == len(codes):
            print("\n✓ 验证码唯一性测试通过")
        else:
            print("\n✗ 验证码唯一性测试失败")
            return False

        # 测试验证
        from pickup_code.code_validator import PickupCodeValidator
        validator = PickupCodeValidator(generator, config, logger)

        # 测试正确的验证码
        success, msg = validator.verify_code(codes[0])
        print(f"验证正确验证码: {success}, {msg}")

        # 测试错误的验证码
        success, msg = validator.verify_code("000000")
        print(f"验证错误验证码: {success}, {msg}")

        print("\n✓ 验证码生成器测试通过")
        return True

    except Exception as e:
        print(f"\n✗ 验证码生成器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("\n智能外卖柜应用层测试")
    print("=" * 60)

    results = []

    # 运行测试
    results.append(("配置加载", test_config()))
    results.append(("日志系统", test_logging()))
    results.append(("验证码生成器", test_code_generator()))

    # 输出测试结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{name}: {status}")

    # 检查是否全部通过
    all_passed = all(result for _, result in results)

    if all_passed:
        print("\n✓ 所有测试通过！")
        return 0
    else:
        print("\n✗ 部分测试失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())
