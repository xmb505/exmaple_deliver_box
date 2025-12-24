#!/bin/bash

# HT1621UNIXSOCKET_test.sh
# 通过Unix Socket和SPI模式控制HT1621 LCD显示
# 使用daemon_gpio守护进程和socket_json_sender.py工具

# 默认Unix Socket路径
SOCKET_PATH="/tmp/gpio.sock"

echo "🔧 HT1621 Unix Socket SPI 测试脚本"
echo "使用Unix Socket路径: $SOCKET_PATH"
echo

# 发送JSON命令到Unix Socket
send_json() {
    local json_data="$1"
    /home/xmb505/智能外卖柜样机/@debug_utils/socket_json_sender.py --socket-path "$SOCKET_PATH" --data "$json_data"
}

# 检查daemon是否运行
echo "🔍 检查daemon是否运行..."
if [ ! -S "$SOCKET_PATH" ]; then
    echo "⚠️  Unix Socket 不存在: $SOCKET_PATH"
    echo "请先启动 daemon_gpio"
    exit 1
else
    echo "✅ Unix Socket 存在，可以继续"
fi

# 直接使用SPI命令发送数据
# 发送帧数据（通过SPI）
send_frame() {
    local frame="$1"
    echo "发送帧数据: $frame (长度: ${#frame})"
    send_json '{"alias": "spi", "mode": "spi", "spi_num": 1, "spi_data_cs_collection": "down", "spi_data": "'$frame'"}'
    sleep 0.01
}

# 发命令：100 + 9-bit
send_cmd() {
    local cmd9="$1"
    if [[ ${#cmd9} -ne 9 ]]; then
        echo "❌ 命令需9位"
        return 1
    fi
    echo "发送命令: 100${cmd9}"
    send_frame "100${cmd9}"
}

# 写 RAM：101 + 6-bit 地址 + 8-bit 数据
write_ram_bin() {
    local addr=$1
    local data8="$2"
    
    if [[ ${#data8} -ne 8 ]] || [[ ! $data8 =~ ^[01]+$ ]]; then
        echo "❌ 数据需8位二进制"
        return 1
    fi

    # 地址转6位二进制（0~63）
    local addr_bin=$(printf "%06d" "$(echo "obase=2; $addr" | bc 2>/dev/null || echo "000000")")
    if [[ ${#addr_bin} -gt 6 ]]; then
        addr_bin="000000"
    fi

    local ram_data="101${addr_bin}${data8}"
    echo "写入RAM地址 $addr (0b${addr_bin}): 0b${data8} -> 帧: $ram_data"
    send_frame "$ram_data"
}

# ==================================================
# STEP 1: 初始化 HT1621（严格按序列）
# ==================================================
echo -e "\n✅ 初始化 HT1621（共阴，6位数码管）"
send_cmd "000000000"   # SYSDIS
sleep 0.01
send_cmd "001010110"   # BIAS: 1/3, 4 COM
send_cmd "011000000"   # RC256
send_cmd "000000010"   # SYSEN
send_cmd "000000110"   # LCDON
sleep 0.1

# ==================================================
# STEP 2: 显示 "123456"（使用提供的段码）
# ==================================================
echo -e "\n💡 显示 '123456'（按段码表）"

# 共阴数码管段码
# 0: 01111101, 1: 01100000, 2: 00111110, 3: 01111010
# 4: 01100011, 5: 01011011, 6: 01011111, 7: 01110000
# 8: 01111111, 9: 01111011

# 显示数字 '123456'
# RAM地址: 0,2,4,6,8,10 对应数码管的 位0,位1,位2,位3,位4,位5
write_ram_bin 0  "01100000"   # 数字 '1' (位0 - 最左边)
write_ram_bin 2  "00111110"   # 数字 '2' (位1)
write_ram_bin 4  "01111010"   # 数字 '3' (位2) 
write_ram_bin 6  "01100011"   # 数字 '4' (位3)
write_ram_bin 8  "01011011"   # 数字 '5' (位4)
write_ram_bin 10 "01011111"   # 数字 '6' (位5 - 最右边)

echo -e "\n✅ HT1621显示完成！"
echo "   数码管应显示: 123456"

# 可选：显示数字0-9测试
read -p "是否进行数字0-9显示测试? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "\n🔢 开始数字0-9显示测试..."
    
    # 数字对应的段码 (共阴数码管)
    declare -A digit_codes
    digit_codes[0]="01111101"
    digit_codes[1]="01100000" 
    digit_codes[2]="00111110"
    digit_codes[3]="01111010"
    digit_codes[4]="01100011"
    digit_codes[5]="01011011"
    digit_codes[6]="01011111"
    digit_codes[7]="01110000"
    digit_codes[8]="01111111"
    digit_codes[9]="01111011"
    
    for i in {0..9}; do
        echo "显示数字 $i..."
        write_ram_bin 0 "${digit_codes[$i]}"  # 只显示在一个位上方便测试
        sleep 0.5
    done
    
    # 恢复显示123456
    write_ram_bin 0  "01100000"   # '1'
    write_ram_bin 2  "00111110"   # '2'
    write_ram_bin 4  "01111010"   # '3'
    write_ram_bin 6  "01100011"   # '4'
    write_ram_bin 8  "01011011"   # '5'
    write_ram_bin 10 "01011111"   # '6'
    echo "恢复显示 '123456'"
fi

echo -e "\n🎉 HT1621 Unix Socket SPI 测试完成！"