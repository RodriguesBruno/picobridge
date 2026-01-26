import time
import asyncio
import framebuf
from framebuf import FrameBuffer

from libraries.oled.ssd1306 import SSD1306I2C
from src.lcd_numbers import get_char
from src.screensaver import Screensaver

chars_per_line: int = 16
FONT_WIDTH: int = 6
fb_line_height: int = 11


class DisplayController:
    def __init__(self, display: SSD1306I2C, screensaver: Screensaver) -> None:
        self._display: SSD1306I2C = display
        self.screensaver: Screensaver = screensaver

        self._display_has_started: bool = False
        self._display.init_display()

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

        # Screensaver
        self._last_activity_time: int = time.ticks_ms()

        # Brightness
        self._brightness_active: int = 255
        self._brightness_screensaver: int = 1


    async def start(self, value: int = 9) -> None:
        await self.self_test(value=value)
        asyncio.create_task(self._drive_all_lines())
        asyncio.create_task(self._drive_timer_bar())

    async def self_test(self, value: int) -> None:
        self._display_has_started = False

        nums = [get_char(v) for v in range(value, -1, -1)]

        for number in nums:
            self._display.fill(0)
            for sq in number:
                a, b, c, d, e = sq
                self._display.fill_rect(a, b, c, d, e)
            self._display.show()
            await asyncio.sleep_ms(150)

        await asyncio.sleep_ms(200)
        self._display.fill(0)
        self._display.show()

        self._display_has_started = True

    def _map_line(self, line: int) -> int:
        idx = line - 1
        if 0 <= idx < self._line_count:
            return idx
        raise ValueError("valid lines are 1–5")

    def _get_framebuf(self) -> FrameBuffer:
        return framebuf.FrameBuffer(
            bytearray(self._display.width * fb_line_height),
            self._display.width,
            fb_line_height,
            framebuf.MONO_VLSB
        )

    def _get_bar_framebuf(self) -> FrameBuffer:
        return framebuf.FrameBuffer(
            bytearray(self._display.width * self._bar_thickness),
            self._display.width,
            self._bar_thickness,
            framebuf.MONO_VLSB
        )

    def _blit_to_line(self, fb, line_index) -> None:
        self._display.blit(fb, 0, line_index * fb_line_height)

    async def set_last_activity_time(self, value: int) -> None:
        self._last_activity_time = value

    def screensaver_is_active(self) -> bool:
        return self.screensaver.is_active()

    def screensaver_is_enabled(self) -> bool:
        return self.screensaver.is_enabled()

    async def activate_screensaver(self) -> None:
        self.screensaver.activate()
        await self.set_brightness(level=self._brightness_screensaver)
        await self.hide_bar()

    async def deactivate_screensaver(self) -> None:
        self.screensaver.deactivate()
        await self.set_brightness(level=self._brightness_active)
        await self.show_bar()

    async def screensaver_drive(self):
        while True:
            await asyncio.sleep(1)

            now = time.ticks_ms()
            idle_ms = time.ticks_diff(now, self._last_activity_time)
            idle_s = idle_ms / 1000

            if self.screensaver.is_enabled():
                if idle_s >= self.screensaver.get_timeout():
                    await self.activate_screensaver()
                else:
                    remaining = self.screensaver.get_timeout() - idle_s
                    percent = remaining / self.screensaver.get_timeout()
                    bar_len = int(self._display.width * percent)

                    if self.screensaver.is_active():
                        await self.deactivate_screensaver()

                    if not self._bar_visible:
                        await self.show_bar()

                    await self.set_bar_length(value=bar_len)
            else:
                if self.screensaver.is_active():
                    await self.deactivate_screensaver()

    def display_width(self) -> int:
        return self._display.width

    async def clear_line(self, line: int) -> None:
        idx = self._map_line(line)
        self.lines_data[idx] = ''

    async def clear_lines(self) -> None:
        for i in range(self._line_count):
            self.lines_data[i] = ''

    async def write_to_line(self, line: int, text: str) -> None:
        idx = self._map_line(line)
        self.lines_data[idx] = text

    async def set_line_alignment(self, line: int, alignment: str) -> None:
        idx = self._map_line(line)
        if alignment not in ("left", "center", "right"):
            raise ValueError("alignment must be left, center or right")

        self.line_alignments[idx] = alignment

    async def add_highlight(self, line: int) -> None:
        idx = self._map_line(line)
        self.highlighted_lines[idx] = True

    async def remove_highlight(self, line: int) -> None:
        idx = self._map_line(line)
        self.highlighted_lines[idx] = False

    async def enable_scrolling(self, line: int) -> None:
        idx = self._map_line(line)
        self.scroll_enabled[idx] = True
        self.scroll_positions[idx] = self._display.width

    async def disable_scrolling(self, line: int) -> None:
        idx = self._map_line(line)
        self.scroll_enabled[idx] = False

    async def set_scroll_speed(self, line: int, speed: int) -> None:
        idx = self._map_line(line)
        self.scroll_speeds[idx] = max(1, min(8, speed))

    async def set_bar_length(self, value: int) -> None:
        self._bar_length = max(0, min(self._display.width, value))

    async def show_bar(self) -> None:
        self._bar_visible = True

    async def hide_bar(self) -> None:
        self._bar_visible = False

    def get_brightness_screensaver(self) -> int:
        return self._brightness_screensaver

    def set_brightness_screensaver(self, level: int) -> None:
        level = max(0, min(255, level))
        self._brightness_screensaver = level

    def get_brightness(self) -> int:
        return self._brightness_active

    async def reset_brightness(self) -> None:
        await self.set_brightness(level=self._brightness_active)

    async def set_brightness(self, level: int):
        level = max(0, min(255, level))
        self._display.write_cmd(0x81)
        self._display.write_cmd(level)

    async def _drive_all_lines(self) -> None:
        fb = self._get_framebuf()

        prev_render = [''] * self._line_count
        prev_hl = [False] * self._line_count

        while True:
            try:
                if self._display_has_started:

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
                                x = self._display.width

                            self.scroll_positions[idx] = x

                            if highlight:
                                fb.rect(0, 0, self._display.width, fb_line_height, 1)

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
                                    px = self._display.width - (FONT_WIDTH * len(text))
                                    fb.text(text, px, 2)
                                else:
                                    fb.text(text, 0, 2)

                            if highlight:
                                fb.rect(0, 0, self._display.width, fb_line_height, 1)

                            self._blit_to_line(fb, idx)

                    self._display.show()

                await asyncio.sleep_ms(30)

            except Exception as e:
                print(f"[DISPLAY_CONTROLLER] Drive Lines Error: {e}")

    async def _drive_timer_bar(self) -> None:
        fb = self._get_bar_framebuf()
        prev = -1
        y = fb_line_height * self._line_count

        while True:
            try:
                if self._display_has_started:

                    if self._bar_visible:
                        if self._bar_length != prev:
                            prev = self._bar_length
                            fb.fill(0)
                            fb.rect(0, 0, self._bar_length, self._bar_thickness, 1)
                            self._display.blit(fb, 0, y)
                            self._display.show()

                    else:
                        fb.fill(0)
                        self._display.blit(fb, 0, y)
                        self._display.show()

                await asyncio.sleep_ms(100)

            except Exception as e:
                print(f"[DISPLAY_CONTROLLER] Driver Bar Error: {e}")
