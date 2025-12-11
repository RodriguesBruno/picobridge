import asyncio
import framebuf
from machine import Pin, I2C

from libraries.oled.ssd1306 import SSD1306I2C
from src.lcd_numbers import get_char

chars_per_line: int = 16
FONT_WIDTH: int = 6
fb_line_height: int = 11


class DisplayController:

    def __init__(self, i2c_id: int, i2c_sda: int, i2c_scl: int) -> None:
        self.display = SSD1306I2C(128, 64,I2C(i2c_id, sda=Pin(i2c_sda), scl=Pin(i2c_scl), freq=400_000))
        self._display_is_running: bool = False
        self.display.init_display()

        # Lines
        self._line_count = 5
        self.lines_data = [''] * self._line_count
        self.highlighted_lines = [False] * self._line_count
        self.line_alignments = ["center"] * self._line_count

        # Per-line scrolling settings
        self.scroll_enabled = [False] * self._line_count
        self.scroll_positions = [0] * self._line_count
        self.scroll_speeds = [2] * self._line_count

        # Bar
        self._bar_visible: bool = False
        self._bar_length: int = 0
        self._bar_thickness: int = 4

        # Async scheduler
        self._loop = asyncio.get_event_loop()
        self._loop.create_task(self.self_test(value=9))
        self._loop.create_task(self._drive_all_lines())
        self._loop.create_task(self._drive_timer_bar())

    async def self_test(self, value: int):
        self._display_is_running = False

        nums = [get_char(v) for v in range(value, -1, -1)]

        for number in nums:
            self.display.fill(0)
            for sq in number:
                a, b, c, d, e = sq
                self.display.fill_rect(a, b, c, d, e)
            self.display.show()
            await asyncio.sleep_ms(150)

        await asyncio.sleep_ms(200)
        self.display.fill(0)
        self.display.show()

        self._display_is_running = True

    def _map_line(self, line: int) -> int:
        idx = line - 1
        if 0 <= idx < self._line_count:
            return idx
        raise ValueError("valid lines are 1–5")

    def _get_framebuf(self):
        return framebuf.FrameBuffer(
            bytearray(self.display.width * fb_line_height),
            self.display.width,
            fb_line_height,
            framebuf.MONO_VLSB
        )

    def _get_bar_framebuf(self):
        return framebuf.FrameBuffer(
            bytearray(self.display.width * self._bar_thickness),
            self.display.width,
            self._bar_thickness,
            framebuf.MONO_VLSB
        )

    def _blit_to_line(self, fb, line_index):
        self.display.blit(fb, 0, line_index * fb_line_height)

    async def clear_line(self, line: int):
        idx = self._map_line(line)
        self.lines_data[idx] = ''

    async def clear_lines(self):
        for i in range(self._line_count):
            self.lines_data[i] = ''

    async def write_to_line(self, line: int, text: str):
        idx = self._map_line(line)
        self.lines_data[idx] = text

    async def set_line_alignment(self, line: int, alignment: str):
        idx = self._map_line(line)
        if alignment not in ("left", "center", "right"):
            raise ValueError("alignment must be left, center or right")
        self.line_alignments[idx] = alignment

    async def add_highlight(self, line: int):
        idx = self._map_line(line)
        self.highlighted_lines[idx] = True

    async def remove_highlight(self, line: int):
        idx = self._map_line(line)
        self.highlighted_lines[idx] = False

    async def enable_scrolling(self, line: int):
        idx = self._map_line(line)
        self.scroll_enabled[idx] = True
        self.scroll_positions[idx] = self.display.width  # reset scroll start

    async def disable_scrolling(self, line: int):
        idx = self._map_line(line)
        self.scroll_enabled[idx] = False

    async def set_scroll_speed(self, line: int, speed: int):
        idx = self._map_line(line)
        self.scroll_speeds[idx] = max(1, min(8, speed))

    async def set_bar_length(self, value: int):
        self._bar_length = max(0, min(self.display.width, value))

    async def show_bar(self):
        self._bar_visible = True

    async def hide_bar(self):
        self._bar_visible = False

    async def set_brightness(self, level: int):
        level = max(0, min(255, level))
        self.display.write_cmd(0x81)
        self.display.write_cmd(level)

    async def _drive_all_lines(self):
        fb = self._get_framebuf()

        prev_render = [''] * self._line_count
        prev_hl = [False] * self._line_count

        while True:
            if self._display_is_running:

                for idx in range(self._line_count):

                    text = self.lines_data[idx]
                    highlight = self.highlighted_lines[idx]

                    if self.scroll_enabled[idx] and text:

                        fb.fill(0)
                        x = self.scroll_positions[idx]
                        fb.text(text, x, 2)

                        text_width = FONT_WIDTH * len(text)

                        x -= self.scroll_speeds[idx]
                        if x < -text_width - 10:
                            x = self.display.width

                        self.scroll_positions[idx] = x

                        if highlight:
                            fb.rect(0, 0, self.display.width, fb_line_height, 1)

                        self._blit_to_line(fb, idx)
                        continue

                    if text != prev_render[idx] or highlight != prev_hl[idx]:

                        prev_render[idx] = text
                        prev_hl[idx] = highlight

                        fb.fill(0)

                        if text:
                            align = self.line_alignments[idx]
                            if align == "center":
                                t = text.center(chars_per_line)
                                fb.text(t, 0, 2)
                            elif align == "right":
                                px = self.display.width - (FONT_WIDTH * len(text))
                                fb.text(text, px, 2)
                            else:
                                fb.text(text, 0, 2)

                        if highlight:
                            fb.rect(0, 0, self.display.width, fb_line_height, 1)

                        self._blit_to_line(fb, idx)

                self.display.show()

            await asyncio.sleep_ms(30)

    async def _drive_timer_bar(self):
        fb = self._get_bar_framebuf()
        prev = -1
        y = fb_line_height * self._line_count

        while True:
            if self._display_is_running:

                if self._bar_visible:
                    if self._bar_length != prev:
                        prev = self._bar_length
                        fb.fill(0)
                        fb.rect(0, 0, self._bar_length, self._bar_thickness, 1)
                        self.display.blit(fb, 0, y)
                        self.display.show()

                else:
                    fb.fill(0)
                    self.display.blit(fb, 0, y)
                    self.display.show()

            await asyncio.sleep_ms(100)
