# GPIO守护进程实现逻辑

## 概述
- 将USB2GPIO设备抽象为UNIX Socket接口，便于进程间通信
- 采用JSON数据格式进行命令传输，提高编程便利性
- 仅适用于BL-ENV-V1.3硬件平台
- 严格遵循USB2GPIO设备使用说明书的指令协议

## 通信机制
- 使用SOCK_DGRAM类型的UNIX Socket确保进程间通信稳定性
- 通过/tmp/gpio.sock文件进行命令控制
- 通过/tmp/gpio_get.sock文件进行状态监听

## 功能模式

### 1. GPIO控制模式 (操控逻辑)
- 创建控制用UNIX Socket文件
- 接收客户端发送的JSON格式控制命令
- 根据命令内容操作对应的USB2GPIO设备
- 支持单个GPIO控制、批量GPIO控制和SPI通信

### 2. GPIO状态监听模式 (监听逻辑)
- 创建监听用UNIX Socket文件
- 客户端主动连接监听Socket
- 守护进程作为服务端主动向客户端发送GPIO状态数据
- 支持实时状态反馈和事件通知

### 3. SPI低速模式
- 就是bit banging

## 支持的指令类型
- seter模式：控制输出设备（如灯泡、门锁、继电器等）
- geter模式：读取输入设备（如传感器、开关状态等）
- spi模式：支持多路SPI通信，可独立设置各路的时钟沿触发方式