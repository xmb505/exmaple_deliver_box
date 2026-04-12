#!/usr/bin/env python3
"""
总守护进程
负责拉起和管理所有服务
"""

import os
import sys
import time
import signal
import subprocess
import configparser
import logging
from pathlib import Path

class DaemonAll:
    """总守护进程"""
    
    def __init__(self, config_path):
        """初始化守护进程"""
        self.config = configparser.ConfigParser()
        self.config.read(config_path)
        
        # 工作目录
        self.work_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 服务列表
        self.services = []
        
        # 运行标志
        self.running = False
        
        # 子进程列表
        self.processes = {}
        
        # 初始化日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('/var/log/daemon_all.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('DaemonAll')
        
        self.logger.info("总守护进程初始化完成")
    
    def load_services(self):
        """加载服务配置"""
        self.logger.info("加载服务配置...")
        
        # 首先加载gpio_service（必须第一个启动）
        if self.config.has_section('gpio_service'):
            service_name = 'gpio_service'
            name = 'GPIO守护进程'
            service_type = 'daemon'
            work_dir = self.config.get('gpio_service', 'work_dir')
            work_command = self.config.get('gpio_service', 'work_command')
            
            service = {
                'service_name': service_name,
                'name': name,
                'service_type': service_type,
                'work_dir': os.path.join(self.work_dir, work_dir),
                'work_command': work_command
            }
            
            self.services.insert(0, service)  # 插入到列表开头
            self.logger.info(f"加载服务: {service_name} - {name} (核心服务)")
        
        # 遍历所有section
        sections = self.config.sections()
        service_sections = [s for s in sections if s.startswith('service_')]
        
        for section in service_sections:
            service_name = self.config.get(section, 'service_name')
            name = self.config.get(section, 'name')
            service_type = self.config.get(section, 'service_type')
            work_dir = self.config.get(section, 'work_dir')
            work_command = self.config.get(section, 'work_command')
            
            service = {
                'service_name': service_name,
                'name': name,
                'service_type': service_type,
                'work_dir': os.path.join(self.work_dir, work_dir),
                'work_command': work_command
            }
            
            self.services.append(service)
            self.logger.info(f"加载服务: {service_name} - {name}")
        
        self.logger.info(f"共加载 {len(self.services)} 个服务")
    
    def start_service(self, service):
        """启动单个服务"""
        service_name = service['service_name']
        work_dir = service['work_dir']
        work_command = service['work_command']
        
        self.logger.info(f"启动服务: {service_name}")
        
        try:
            # 切换到工作目录
            os.chdir(work_dir)
            
            # 检查是否是application服务且启用了debug模式
            if service_name == 'application' and '--debug-application' in sys.argv:
                # debug模式：输出到控制台
                process = subprocess.Popen(
                    work_command.split(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )
                
                # 实时输出日志
                def log_output():
                    for line in process.stdout:
                        print(f"[{service_name}] {line}", end='')
                
                import threading
                log_thread = threading.Thread(target=log_output, daemon=True)
                log_thread.start()
            else:
                # 正常模式：输出到文件
                process = subprocess.Popen(
                    work_command.split(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )
            
            self.processes[service_name] = process
            self.logger.info(f"服务 {service_name} 启动成功 (PID: {process.pid})")
            
            return True
        except Exception as e:
            self.logger.error(f"启动服务 {service_name} 失败: {e}")
            return False
    
    def stop_service(self, service_name):
        """停止单个服务"""
        if service_name not in self.processes:
            self.logger.warning(f"服务 {service_name} 未运行")
            return
        
        process = self.processes[service_name]
        
        try:
            # 发送SIGTERM信号
            process.terminate()
            
            # 等待进程结束
            process.wait(timeout=5)
            
            self.logger.info(f"服务 {service_name} 已停止")
        except subprocess.TimeoutExpired:
            # 进程未在5秒内结束，强制杀死
            process.kill()
            self.logger.warning(f"服务 {service_name} 强制停止")
        except Exception as e:
            self.logger.error(f"停止服务 {service_name} 失败: {e}")
        finally:
            del self.processes[service_name]
    
    def start_all_services(self):
        """启动所有服务"""
        self.logger.info("启动所有服务...")
        
        for i, service in enumerate(self.services):
            self.start_service(service)
            
            # 如果是gpio_service，等待socket文件创建
            if service['service_name'] == 'gpio_service':
                self.logger.info("等待GPIO服务socket文件创建...")
                import time
                for _ in range(10):  # 等待最多5秒
                    if os.path.exists('/tmp/gpio.sock'):
                        self.logger.info("GPIO服务socket文件已创建")
                        break
                    time.sleep(0.5)
                else:
                    self.logger.warning("GPIO服务socket文件未创建，继续启动其他服务")
            
            # 其他服务间启动间隔1秒
            if i < len(self.services) - 1:
                time.sleep(1)
        
        self.logger.info("所有服务启动完成")
    
    def stop_all_services(self):
        """停止所有服务"""
        self.logger.info("停止所有服务...")
        
        # 反向停止服务
        for service_name in reversed(list(self.processes.keys())):
            self.stop_service(service_name)
        
        self.logger.info("所有服务已停止")
    
    def monitor_services(self):
        """监控服务状态"""
        while self.running:
            try:
                # 检查所有服务状态
                for service_name, process in list(self.processes.items()):
                    return_code = process.poll()
                    
                    if return_code is not None:
                        # 进程已退出
                        self.logger.error(f"服务 {service_name} 意外退出 (返回码: {return_code})")
                        
                        # 重新启动服务
                        service = next((s for s in self.services if s['service_name'] == service_name), None)
                        if service:
                            self.logger.info(f"重新启动服务: {service_name}")
                            self.start_service(service)
                
                # 短暂休眠
                time.sleep(5)
                
            except Exception as e:
                self.logger.error(f"监控服务时发生错误: {e}")
                time.sleep(5)
    
    def run(self):
        """运行守护进程"""
        self.logger.info("总守护进程启动...")
        
        # 加载服务配置
        self.load_services()
        
        # 启动所有服务
        self.start_all_services()
        
        # 设置运行标志
        self.running = True
        
        # 监控服务状态
        self.monitor_services()
    
    def stop(self):
        """停止守护进程"""
        self.logger.info("正在停止总守护进程...")
        self.running = False
        
        # 停止所有服务
        self.stop_all_services()
        
        self.logger.info("总守护进程已停止")


def signal_handler(signum, frame):
    """信号处理函数"""
    global daemon
    if daemon:
        daemon.stop()
    sys.exit(0)


if __name__ == '__main__':
    # 设置信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 获取配置文件路径
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.ini')
    
    # 创建守护进程
    daemon = DaemonAll(config_path)
    
    # 运行守护进程
    try:
        daemon.run()
    except Exception as e:
        logging.error(f"总守护进程运行时发生错误: {e}", exc_info=True)
        daemon.stop()
        sys.exit(1)