#!/bin/bash
# 智能外卖柜应用启动脚本
# Smart Delivery Box Application Start Script

cd "$(dirname "$0")"

echo "=========================================="
echo "智能外卖柜应用启动"
echo "=========================================="

# 检查Python版本
python3 --version

# 启动应用
python3 main.py

echo "应用已退出"