from machine import Pin, I2C
from libraries.oled.ssd1306 import SSD1306I2C



def get_display(i2c_id, i2c_sda, i2c_scl) -> SSD1306I2C:
    return SSD1306I2C(128, 64, I2C(i2c_id, sda=Pin(i2c_sda), scl=Pin(i2c_scl), freq=400_000))
