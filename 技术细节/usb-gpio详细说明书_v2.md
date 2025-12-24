# USB to GPIO 控制模块技术说明书 v2.0

## 1. 设备概述

### 1.1 基本信息
- **设备名称**: USB转GPIO控制模块
- **硬件版本**: BL-ENV-V1.3
- **软件版本**: Build:20250928-1250 CTM--01
- **制造商**: Yunou Intelligent Technology Co., Ltd
- **通信接口**: Type-C USB接口
- **通信协议**: TTL串行通信
- **GPIO数量**: 16个（编号1-16）
- **默认波特率**: 115200
- **数据格式**: HEX发送模式

### 1.2 电气特性
- **工作电压**: 通过USB供电（5V）
- **GPIO电平**: TTL电平（0V/3.3V/5V兼容）
- **PWM频率范围**: 1Hz - 65535Hz
- **计数器最大响应频率**: 1kHz
- **滤波时间范围**: 0-255ms

## 2. 通信协议规范

### 2.1 基本通信设置
```bash
# Linux系统下的串口设置
stty -F /dev/ttyUSB0 115200
```

### 2.2 数据格式规范
- **发送格式**: 十六进制（HEX）字节流
- **字节序**: 大端序（高位字节在前）
- **返回格式**: 与发送指令对应的确认格式
- **超时设置**: 建议每条指令超时时间1-3秒

## 3. 指令集详细规范

### 3.1 GPIO输出控制指令

#### 3.1.1 3A指令 - 离散GPIO控制
**功能**: 控制单个或多个不连续GPIO的电平状态

**指令格式**:
```
发送: 3A [GPIO1] [状态1] [GPIO2] [状态2] ...
返回: 2A [GPIO1] [状态1] [GPIO2] [状态2] ...
```

**参数说明**:
- `3A`: 指令标识符（1字节）
- `[GPIO]`: GPIO通道号（1字节，01-16，0A表示10，10表示16）
- `[状态]`: 电平状态（1字节，00=低电平，01=高电平）

**示例**:
```bash
# 设置GPIO1为高电平
echo -ne '\x3A\x01\x01' > /dev/ttyUSB0
# 返回: 2A 01 01

# 设置GPIO1低电平，GPIO3和GPIO6高电平
echo -ne '\x3A\x01\x00\x03\x01\x06\x01' > /dev/ttyUSB0
# 返回: 2A 01 00 03 01 06 01
```

#### 3.1.2 3B指令 - 连续GPIO控制
**功能**: 控制连续GPIO序列的电平状态

**指令格式**:
```
发送: 3B [GPIO1状态] [GPIO2状态] [GPIO3状态] ...
返回: 2B [GPIO1状态] [GPIO2状态] [GPIO3状态] ...
```

**参数说明**:
- `3B`: 指令标识符（1字节）
- `[GPIO状态]`: 每个字节对应一个GPIO状态（00=低电平，01=高电平）

**示例**:
```bash
# 设置GPIO1-6状态：1,3,4,5为低电平，2,6为高电平
echo -ne '\x3B\x00\x01\x00\x00\x00\x01' > /dev/ttyUSB0
# 返回: 2B 00 01 00 00 00 01
```

#### 3.1.3 3C指令 - 延迟GPIO控制
**功能**: 设置GPIO在指定延迟后改变状态

**指令格式**:
```
发送: 3C [GPIO] [延迟高字节] [延迟低字节] [目标状态]
返回: 2C [GPIO] [延迟高字节] [延迟低字节] [目标状态]
```

**参数说明**:
- `3C`: 指令标识符（1字节）
- `[GPIO]`: GPIO通道号（1字节）
- `[延迟高字节][延迟低字节]`: 延迟时间（2字节，大端序，单位ms）
- `[目标状态]`: 目标电平状态（1字节，00=低电平，01=高电平）

**示例**:
```bash
# GPIO1在100ms后设置为低电平
echo -ne '\x3C\x01\x00\x64\x00' > /dev/ttyUSB0
# 返回: 2C 01 00 64 00
```

### 3.2 GPIO状态查询指令

#### 3.2.1 3D指令 - 全GPIO状态查询（拉高模式）
**功能**: 读取所有GPIO状态，查询时将所有GPIO拉高

**指令格式**:
```
发送: 3D FF
返回: ASCII格式持续输出
```

**返回格式**:
```
CH1:1 CH2:1 CH3:1 CH4:1 CH5:1 CH6:1 CH7:1 CH8:1 CH9:1 CH10:1 CH11:1 CH12:1 CH13:1 CH14:1 CH15:1 CH16:1
```

**重要说明**: 此指令会持续输出数据，直到发送下一个指令为止

#### 3.2.2 3E指令 - 全GPIO状态查询（拉低模式）
**功能**: 读取所有GPIO状态，查询时将所有GPIO拉低

**指令格式**:
```
发送: 3E FF
返回: ASCII格式持续输出
```

**返回格式**:
```
CH1:0 CH2:0 CH3:0 CH4:0 CH5:0 CH6:0 CH7:0 CH8:0 CH9:0 CH10:0 CH11:0 CH12:0 CH13:0 CH14:0 CH15:0 CH16:0
```

**重要说明**: 此指令会持续输出数据，直到发送下一个指令为止

#### 3.2.3 3F指令 - 单GPIO状态查询
**功能**: 查询单个GPIO的电平状态

**指令格式**:
```
发送: 3F [GPIO]
返回: 2F [GPIO] [状态]
```

**参数说明**:
- `3F`: 指令标识符（1字节）
- `[GPIO]`: GPIO通道号（1字节）
- `[状态]`: 电平状态（1字节，00=低电平，01=高电平）

**示例**:
```bash
# 查询GPIO1状态
echo -ne '\x3F\x01' > /dev/ttyUSB0
# 返回: 2F 01 01（表示高电平）
```

### 3.3 PWM控制指令

#### 3.3.1 5A指令 - PWM输出控制
**功能**: 控制指定通道的PWM输出

**指令格式**:
```
发送: 5A [通道] [频率高字节] [频率低字节] [占空比]
返回: 4A [通道] [频率高字节] [频率低字节] [占空比]
```

**参数说明**:
- `5A`: 指令标识符（1字节）
- `[通道]`: PWM通道号（1字节，01=通道1，02=通道2，03=通道3）
- `[频率高字节][频率低字节]`: PWM频率（2字节，大端序，单位Hz，最大65535）
- `[占空比]`: 占空比（1字节，00-64对应0%-100%）

**示例**:
```bash
# 通道1输出1kHz，50%占空比方波
echo -ne '\x5A\x01\x03\xE8\x32' > /dev/ttyUSB0
# 返回: 4A 01 03 E8 32

# 通道3输出50kHz，20%占空比方波
echo -ne '\x5A\x03\xC3\x50\x14' > /dev/ttyUSB0
# 返回: 4A 03 C3 50 14
```

### 3.4 输入模式配置指令

#### 3.4.1 5B指令 - 区间GPIO状态查询
**功能**: 配置指定区间GPIO为输入模式并读取状态

**指令格式**:
```
发送: 5B [起始GPIO] [结束GPIO] [输入模式]
返回: 4B [起始GPIO] [结束GPIO] [输入模式] [状态数据...]
```

**参数说明**:
- `5B`: 指令标识符（1字节）
- `[起始GPIO]`: 起始GPIO通道号（1字节）
- `[结束GPIO]`: 结束GPIO通道号（1字节）
- `[输入模式]`: 输入模式（1字节，00=弱上拉输入，01=弱下拉输入）
- `[状态数据...]`: 各GPIO状态（每个GPIO 1字节，00=低电平，01=高电平）

**示例**:
```bash
# 配置GPIO1-10为上拉输入
echo -ne '\x5B\x01\x0A\x00' > /dev/ttyUSB0
# 返回: 4B 01 0A 00 01 01 01 01 01 01 01 01 01 01

# 配置GPIO3-8为下拉输入
echo -ne '\x5B\x03\x08\x01' > /dev/ttyUSB0
# 返回: 4B 03 08 01 00 00 00 00 00 00
```

### 3.5 计数器模式指令

#### 3.5.1 5C指令 - 计数器模式配置
**功能**: 配置GPIO为计数器模式

**指令格式**:
```
发送: 5C [GPIO] [滤波时间] [功能1] [功能2]
返回: 4C [GPIO] [滤波时间] [功能1] [功能2]
```

**参数说明**:
- `5C`: 指令标识符（1字节）
- `[GPIO]`: GPIO通道号（1字节）
- `[滤波时间]`: 滤波时间（1字节，00-FF对应0-255ms）
- `[功能1]`: 计数功能开关（1字节，00=禁用，01=启用）
- `[功能2]`: 上报模式（1字节，00=主动查询，01=自动上报）

**自动上报格式**:
```
4D [GPIO] [计数值高字节] [计数值中高字节] [计数值中低字节] [计数值低字节]
```

**示例**:
```bash
# GPIO1配置为计数器模式，滤波10ms，启用自动上报
echo -ne '\x5C\x01\x0A\x01\x01' > /dev/ttyUSB0
# 返回: 4C 01 0A 01 01
# 自动上报: 4D 01 00 00 00 0A（表示计数10次）
```

#### 3.5.2 5D指令 - 计数器查询控制
**功能**: 主动查询或清零计数器

**指令格式**:
```
发送: 5D [GPIO] [功能]
返回: 4D [GPIO] [计数值高字节] [计数值中高字节] [计数值中低字节] [计数值低字节]
```

**参数说明**:
- `5D`: 指令标识符（1字节）
- `[GPIO]`: GPIO通道号（1字节）
- `[功能]`: 功能选择（1字节，00=清零计数器，01=主动查询）

**示例**:
```bash
# 主动查询GPIO1计数值
echo -ne '\x5D\x01\x01' > /dev/ttyUSB0
# 返回: 4D 01 00 00 00 0A（表示计数10次）
```

### 3.6 系统信息指令

#### 3.6.1 ver指令 - 版本信息查询
**功能**: 查询设备版本信息

**指令格式**:
```
发送: ver
返回: 多行文本信息
```

**返回格式**:
```
Software: Bulid:20250928-1250 CTM--01
Hardware: BL-ENV-V1.3
Weblink: https://item.taobao.com/item.htm?id=711754897030
Copyright:Yunou Intelligent Technology Co., Ltd
```

## 4. 编程接口规范

### 4.1 Python示例代码
```python
import serial
import time
import struct

class USBGPIOController:
    def __init__(self, device_path='/dev/ttyUSB0', baud_rate=115200):
        self.ser = serial.Serial(device_path, baud_rate, timeout=3)
        
    def send_command(self, command):
        """发送HEX命令并返回响应"""
        self.ser.write(command)
        time.sleep(0.1)
        response = self.ser.read_all()
        return response
    
    def set_gpio(self, gpio_pin, state):
        """设置单个GPIO状态"""
        command = bytes([0x3A, gpio_pin, state])
        return self.send_command(command)
    
    def read_gpio(self, gpio_pin):
        """读取单个GPIO状态"""
        command = bytes([0x3F, gpio_pin])
        response = self.send_command(command)
        if len(response) >= 3 and response[0] == 0x2F:
            return response[2]  # 返回状态值
        return None
    
    def set_pwm(self, channel, frequency, duty_cycle):
        """设置PWM输出"""
        freq_high = (frequency >> 8) & 0xFF
        freq_low = frequency & 0xFF
        command = bytes([0x5A, channel, freq_high, freq_low, duty_cycle])
        return self.send_command(command)
    
    def close(self):
        """关闭串口连接"""
        self.ser.close()

# 使用示例
if __name__ == "__main__":
    controller = USBGPIOController()
    
    # 设置GPIO1为高电平
    response = controller.set_gpio(1, 1)
    print(f"设置响应: {response.hex()}")
    
    # 读取GPIO1状态
    state = controller.read_gpio(1)
    print(f"GPIO1状态: {state}")
    
    # 设置PWM通道1为1kHz，50%占空比
    response = controller.set_pwm(1, 1000, 50)
    print(f"PWM设置响应: {response.hex()}")
    
    controller.close()
```

### 4.2 C++示例代码
```cpp
#include <iostream>
#include <fstream>
#include <vector>
#include <unistd.h>

class USBGPIOController {
private:
    std::string device_path;
    int baud_rate;
    
public:
    USBGPIOController(const std::string& path = "/dev/ttyUSB0", int baud = 115200)
        : device_path(path), baud_rate(baud) {}
    
    bool sendCommand(const std::vector<unsigned char>& command, std::vector<unsigned char>& response) {
        // 设置串口参数
        std::string stty_cmd = "stty -F " + device_path + " " + std::to_string(baud_rate);
        system(stty_cmd.c_str());
        
        // 发送命令
        std::ofstream device(device_path, std::ios::binary);
        if (!device) return false;
        
        device.write(reinterpret_cast<const char*>(command.data()), command.size());
        device.close();
        
        // 读取响应
        usleep(100000); // 等待100ms
        
        std::ifstream input(device_path, std::ios::binary);
        if (!input) return false;
        
        response.clear();
        unsigned char byte;
        while (input.read(reinterpret_cast<char*>(&byte), 1)) {
            response.push_back(byte);
        }
        input.close();
        
        return true;
    }
    
    bool setGPIO(int gpio_pin, bool state) {
        std::vector<unsigned char> command = {0x3A, static_cast<unsigned char>(gpio_pin), 
                                             static_cast<unsigned char>(state ? 1 : 0)};
        std::vector<unsigned char> response;
        return sendCommand(command, response);
    }
};

int main() {
    USBGPIOController controller;
    
    // 设置GPIO1为高电平
    if (controller.setGPIO(1, true)) {
        std::cout << "GPIO1设置为高电平成功" << std::endl;
    }
    
    return 0;
}
```

## 5. 故障排除指南

### 5.1 常见问题

#### 5.1.1 设备连接问题
**症状**: 找不到`/dev/ttyUSB0`设备
**解决方案**:
1. 检查USB连接是否牢固
2. 确认设备驱动已正确安装
3. 检查`dmesg | grep tty`查看设备识别情况
4. 尝试重新插拔USB设备

#### 5.1.2 权限问题
**症状**: Permission denied访问串口设备
**解决方案**:
```bash
# 方法1: 将用户添加到dialout组
sudo usermod -a -G dialout $USER
# 注销重新登录生效

# 方法2: 临时修改设备权限
sudo chmod 666 /dev/ttyUSB0
```

#### 5.1.3 通信无响应
**症状**: 发送指令后无返回数据
**解决方案**:
1. 确认波特率设置为115200
2. 检查HEX格式是否正确
3. 增加超时时间
4. 使用`xxd`工具检查返回数据格式

#### 5.1.4 3D/3E指令持续输出
**症状**: 发送3D/3E指令后数据持续输出
**说明**: 这是正常行为，这两个指令设计为持续输出模式
**解决方案**: 发送任意其他指令停止持续输出

### 5.2 调试工具

#### 5.2.1 串口监控
```bash
# 使用minicom监控串口
minicom -D /dev/ttyUSB0 -b 115200

# 使用screen监控串口
screen /dev/ttyUSB0 115200
```

#### 5.2.2 HEX数据分析
```bash
# 发送HEX命令并查看返回的HEX数据
echo -ne '\x3A\x01\x01' > /dev/ttyUSB0 && timeout 1 cat /dev/ttyUSB0 | xxd
```

## 6. 性能优化建议

### 6.1 通信优化
- 批量操作：使用3A指令同时控制多个GPIO减少通信次数
- 合理设置超时：根据指令复杂度调整超时时间
- 缓冲管理：避免频繁的小数据包传输

### 6.2 实时性考虑
- PWM输出：优先使用硬件PWM通道（1-3）
- 计数器模式：合理设置滤波时间平衡响应速度和抗干扰
- 状态查询：避免过于频繁的查询操作

## 7. 安全注意事项

### 7.1 电气安全
- 确认GPIO电压等级与外部设备兼容
- 避免GPIO短路和过载
- 使用适当的电平转换电路

### 7.2 软件安全
- 串口设备权限控制
- 异常情况下的资源释放
- 输入参数的有效性检查

## 8. 技术支持

### 8.1 联系信息
- **制造商**: Yunou Intelligent Technology Co., Ltd
- **产品链接**: https://item.taobao.com/item.htm?id=711754897030

### 8.2 开发资源
- 配置文件：`config.ini`
- 原始说明书：`usb-gpio使用说明书.txt`
- 详细说明书：`usb-gpio使用说明书_优化版.txt`

---

**文档版本**: v2.0  
**最后更新**: 2025年11月28日  
**适用硬件**: BL-ENV-V1.3  
**适用软件**: Build:20250928-1250 CTM--01