GPIO控制指令格式说明

1. 单个GPIO控制（保持向后兼容）：
{
    "alias": "sender",
    "mode": "set",
    "gpio": 1,
    "value": 1
}
daemon会向/dev/ttyUSB0发送指令 3A 01 01，将GPIO1置为高电平

2. 多个GPIO批量控制（新增）：
{
    "alias": "sender",
    "mode": "set",
    "gpios": [1, 2, 3],
    "values": [1, 0, 1]
}
daemon会向/dev/ttyUSB0发送指令 3A 01 01 02 00 03 01，同时设置多个GPIO状态

注意：gpios数组和values数组必须保持一一对应关系，且长度相同。

3. 单路SPI数据发送：

{
    "alias": "spi",
    "mode": "spi",
    "spi_num": 1,
    "spi_data_cs_collection": "down",  // 触发沿选择：上升沿"up"或下降沿"down"
    "spi_data": "10000100"
}
daemon会使用配置文件中定义的spi_num号SPI接口发送数据

4. 多路SPI数据发送（同时控制5路SPI）：

{
    "alias": "spi",
    "mode": "spi_multi",
    "spis": [
        {
            "spi_num": 1,
            "spi_data_cs_collection": "down",
            "spi_data": "10000100"
        },
        {
            "spi_num": 2,
            "spi_data_cs_collection": "up",
            "spi_data": "11001100"
        },
        {
            "spi_num": 3,
            "spi_data_cs_collection": "down",
            "spi_data": "00110011"
        },
        {
            "spi_num": 4,
            "spi_data_cs_collection": "up",
            "spi_data": "10101010"
        },
        {
            "spi_num": 5,
            "spi_data_cs_collection": "down",
            "spi_data": "01010101"
        }
    ]
}
daemon会同时使用配置文件中定义的5个SPI接口发送数据，每路可独立设置触发沿
注意，这里不限制一定要发送8位比特，只是说一个json语句会触发一次cs切片