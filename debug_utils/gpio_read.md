GPIO事件监听工具使用说明
====================

gpio_read.py 是一个用于监听GPIO状态变化事件的调试工具。

功能
----
- 连接到GPIO守护进程的状态监听Socket (/tmp/gpio_get.sock)
- 持续打印输入GPIO设备的状态变化事件
- 只监听配置为"geter"模式的GPIO输入设备

用法
----
./gpio_read.py --socket_path /tmp/gpio_get.sock

说明
----
- 此工具只在GPIO输入设备（配置为geter模式）检测到状态变化时才会显示事件
- 常用于调试按钮、传感器等输入设备
- 按Ctrl+C退出监听
- 显示格式：[时间戳] GPIO事件: {事件数据}