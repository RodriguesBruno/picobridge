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


class _LineState:
    def __init__(self, line_count: int, display_width: int) -> None:
        self._line_count = line_count
        self._display_width = display_width

        self.lines_data = [''] * self._line_count
        self.highlighted_lines = [False] * self._line_count
        self.line_alignments = ["center"] * self._line_count

        self.scroll_enabled = [False] * self._line_count
        self.scroll_positions = [0] * self._line_count
        self.scroll_speeds = [2] * self._line_count

    def line_count(self) -> int:
        return self._line_count

    def map_line(self, line: int) -> int:
        idx = line - 1
        if 0 <= idx < self._line_count:
            return idx
        raise ValueError("valid lines are 1-5")

    def clear_line(self, line: int) -> None:
        idx = self.map_line(line)
        self.lines_data[idx] = ''

    def clear_lines(self) -> None:
        for i in range(self._line_count):
            self.lines_data[i] = ''

    def write_to_line(self, line: int, text: str) -> None:
        idx = self.map_line(line)
        self.lines_data[idx] = text

    def set_line_alignment(self, line: int, alignment: str) -> None:
        idx = self.map_line(line)
        if alignment not in ("left", "center", "right"):
            raise ValueError("alignment must be left, center or right")

        self.line_alignments[idx] = alignment

    def add_highlight(self, line: int) -> None:
        idx = self.map_line(line)
        self.highlighted_lines[idx] = True

    def remove_highlight(self, line: int) -> None:
        idx = self.map_line(line)
        self.highlighted_lines[idx] = False

    def enable_scrolling(self, line: int) -> None:
        idx = self.map_line(line)
        self.scroll_enabled[idx] = True
        self.scroll_positions[idx] = self._display_width

    def disable_scrolling(self, line: int) -> None:
        idx = self.map_line(line)
        self.scroll_enabled[idx] = False

    def set_scroll_speed(self, line: int, speed: int) -> None:
        idx = self.map_line(line)
        self.scroll_speeds[idx] = max(1, min(8, speed))


class _LineRenderer:
    def __init__(self, display: SSD1306I2C, state: _LineState) -> None:
        self._display = display
        self._state = state
        self._fb = self._get_framebuf()
        self._prev_render = [''] * self._state.line_count()
        self._prev_hl = [False] * self._state.line_count()

    def _get_framebuf(self) -> FrameBuffer:
        row_bytes = (fb_line_height + 7) // 8
        return framebuf.FrameBuffer(
            bytearray(self._display.width * row_bytes),
            self._display.width,
            fb_line_height,
            framebuf.MONO_VLSB
        )

    def _blit_to_line(self, fb, line_index: int) -> None:
        self._display.blit(fb, 0, line_index * fb_line_height)

    def _render_scrolling_line(self, idx: int, text: str, highlight: bool) -> bool:
        fb = self._fb
        fb.fill(0)
        x = self._state.scroll_positions[idx]
        fb.text(text, x, 2)

        text_width = FONT_WIDTH * len(text)

        x -= self._state.scroll_speeds[idx]
        if x <= -text_width:
            x = self._display.width

        self._state.scroll_positions[idx] = x

        if highlight:
            fb.rect(0, 0, self._display.width, fb_line_height, 1)

        self._blit_to_line(fb, idx)
        return True

    def render(self) -> bool:
        dirty = False
        for idx in range(self._state.line_count()):
            text = self._state.lines_data[idx]
            highlight = self._state.highlighted_lines[idx]

            if self._state.scroll_enabled[idx] and text:
                if self._render_scrolling_line(idx, text, highlight):
                    dirty = True
                continue

            if text != self._prev_render[idx] or highlight != self._prev_hl[idx]:
                self._prev_render[idx] = text
                self._prev_hl[idx] = highlight

                fb = self._fb
                fb.fill(0)

                if text:
                    align = self._state.line_alignments[idx]
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

                dirty = True

        if dirty:
            self._display.show()

        return dirty


class _BarRenderer:
    def __init__(self, display: SSD1306I2C, line_count: int, thickness: int = 4) -> None:
        self._display = display
        self._bar_thickness = thickness
        self._bar_visible = False
        self._bar_length = 0
        self._prev_length = -1
        self._prev_visible = False
        self._y = fb_line_height * line_count
        self._fb = self._get_bar_framebuf()

    def _get_bar_framebuf(self) -> FrameBuffer:
        row_bytes = (self._bar_thickness + 7) // 8
        return framebuf.FrameBuffer(
            bytearray(self._display.width * row_bytes),
            self._display.width,
            self._bar_thickness,
            framebuf.MONO_VLSB
        )

    def display_width(self) -> int:
        return self._display.width

    def is_visible(self) -> bool:
        return self._bar_visible

    def set_length(self, value: int) -> None:
        self._bar_length = max(0, min(self._display.width, value))

    def show(self) -> None:
        self._bar_visible = True

    def hide(self) -> None:
        self._bar_visible = False

    def step(self, display_has_started: bool) -> None:
        if not display_has_started:
            return

        fb = self._fb

        if self._bar_visible:
            if (not self._prev_visible) or (self._bar_length != self._prev_length):
                self._prev_length = self._bar_length
                fb.fill(0)
                fb.rect(0, 0, self._bar_length, self._bar_thickness, 1)
                self._display.blit(fb, 0, self._y)
                self._display.show()
        else:
            if self._prev_visible:
                fb.fill(0)
                self._display.blit(fb, 0, self._y)
                self._display.show()

        self._prev_visible = self._bar_visible


class _BrightnessController:
    def __init__(self, display: SSD1306I2C, active: int = 255, screensaver: int = 1) -> None:
        self._display = display
        self._brightness_active = active
        self._brightness_screensaver = screensaver

    def get_active(self) -> int:
        return self._brightness_active

    def get_screensaver(self) -> int:
        return self._brightness_screensaver

    def set_screensaver(self, level: int) -> None:
        level = max(0, min(255, level))
        self._brightness_screensaver = level

    async def reset(self) -> None:
        await self.set_brightness(level=self._brightness_active)

    async def set_brightness(self, level: int) -> None:
        level = max(0, min(255, level))
        self._display.write_cmd(0x81)
        self._display.write_cmd(level)


class _ScreensaverController:
    def __init__(self, screensaver: Screensaver, brightness: _BrightnessController, bar: _BarRenderer) -> None:
        self._screensaver = screensaver
        self._brightness = brightness
        self._bar = bar
        self._last_activity_time = time.ticks_ms()

    def set_last_activity_time(self, value: int) -> None:
        self._last_activity_time = value

    def get_timeout(self) -> int:
        return self._screensaver.get_timeout()

    def set_timeout(self, value: int) -> None:
        return self._screensaver.set_timeout(value=value)

    def is_active(self) -> bool:
        return self._screensaver.is_active()

    def is_enabled(self) -> bool:
        return self._screensaver.is_enabled()

    def enable(self) -> None:
        self._screensaver.enable()

    def disable(self) -> None:
        self._screensaver.disable()

    async def activate(self) -> None:
        self._screensaver.activate()
        await self._brightness.set_brightness(level=self._brightness.get_screensaver())
        self._bar.hide()

    async def deactivate(self) -> None:
        self._screensaver.deactivate()
        await self._brightness.set_brightness(level=self._brightness.get_active())
        self._bar.show()

    async def tick(self) -> None:
        now = time.ticks_ms()
        idle_ms = time.ticks_diff(now, self._last_activity_time)
        timeout_s = self._screensaver.get_timeout()
        if timeout_s <= 0:
            if self._screensaver.is_active():
                await self.deactivate()
            return
        timeout_ms = timeout_s * 1000

        if self._screensaver.is_enabled():
            if idle_ms >= timeout_ms:
                await self.activate()
            else:
                remaining_ms = timeout_ms - idle_ms
                bar_len = (self._bar.display_width() * remaining_ms) // timeout_ms

                if self._screensaver.is_active():
                    await self.deactivate()

                if not self._bar.is_visible():
                    self._bar.show()

                self._bar.set_length(bar_len)
        else:
            if self._screensaver.is_active():
                await self.deactivate()


class DisplayController:
    def __init__(self, display: SSD1306I2C, screensaver: Screensaver) -> None:
        self._display: SSD1306I2C = display

        self._display_has_started: bool = False
        self._display.init_display()
        self._display_lock = asyncio.Lock()

        self._line_count = 5

        self._line_state = _LineState(line_count=self._line_count, display_width=self._display.width)
        self._line_renderer = _LineRenderer(display=self._display, state=self._line_state)
        self._bar_renderer = _BarRenderer(display=self._display, line_count=self._line_count)
        self._brightness = _BrightnessController(display=self._display)
        self._screensaver_ctrl = _ScreensaverController(
            screensaver=screensaver,
            brightness=self._brightness,
            bar=self._bar_renderer
        )

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
        return self._line_state.map_line(line)

    async def set_last_activity_time(self, value: int) -> None:
        self._screensaver_ctrl.set_last_activity_time(value)

    def screensaver_get_timeout(self) -> int:
        return self._screensaver_ctrl.get_timeout()

    def screensaver_set_timeout(self, value: int) -> None:
        return self._screensaver_ctrl.set_timeout(value=value)

    def screensaver_is_active(self) -> bool:
        return self._screensaver_ctrl.is_active()

    def screensaver_is_enabled(self) -> bool:
        return self._screensaver_ctrl.is_enabled()

    def screensaver_enable(self) -> None:
        self._screensaver_ctrl.enable()

    def screensaver_disable(self) -> None:
        self._screensaver_ctrl.disable()

    async def activate_screensaver(self) -> None:
        await self._screensaver_ctrl.activate()

    async def deactivate_screensaver(self) -> None:
        await self._screensaver_ctrl.deactivate()

    async def screensaver_drive(self):
        while True:
            await asyncio.sleep(1)
            await self._screensaver_ctrl.tick()

    def display_width(self) -> int:
        return self._display.width

    async def clear_line(self, line: int) -> None:
        self._line_state.clear_line(line)

    async def write_to_line(self, line: int, text: str) -> None:
        self._line_state.write_to_line(line, text)

    async def set_line_alignment(self, line: int, alignment: str) -> None:
        self._line_state.set_line_alignment(line, alignment)

    async def add_highlight(self, line: int) -> None:
        self._line_state.add_highlight(line)

    async def remove_highlight(self, line: int) -> None:
        self._line_state.remove_highlight(line)

    async def enable_scrolling(self, line: int) -> None:
        self._line_state.enable_scrolling(line)

    async def disable_scrolling(self, line: int) -> None:
        self._line_state.disable_scrolling(line)

    async def set_scroll_speed(self, line: int, speed: int) -> None:
        self._line_state.set_scroll_speed(line, speed)

    async def show_bar(self) -> None:
        self._bar_renderer.show()

    async def hide_bar(self) -> None:
        self._bar_renderer.hide()

    def get_brightness_screensaver(self) -> int:
        return self._brightness.get_screensaver()

    def set_brightness_screensaver(self, level: int) -> None:
        self._brightness.set_screensaver(level)

    def get_brightness(self) -> int:
        return self._brightness.get_active()

    async def reset_brightness(self) -> None:
        await self._brightness.reset()

    async def set_brightness(self, level: int):
        await self._brightness.set_brightness(level)

    async def _drive_all_lines(self) -> None:
        while True:
            try:
                dirty = False
                scrolling_active = False
                if self._display_has_started:
                    scrolling_active = any(
                        self._line_state.scroll_enabled[idx] and self._line_state.lines_data[idx]
                        for idx in range(self._line_state.line_count())
                    )
                    async with self._display_lock:
                        dirty = self._line_renderer.render()

                await asyncio.sleep_ms(30 if (dirty or scrolling_active) else 100)

            except Exception as e:
                print(f"[DISPLAY_CONTROLLER] Drive Lines Error: {e}")

    async def _drive_timer_bar(self) -> None:
        while True:
            try:
                async with self._display_lock:
                    self._bar_renderer.step(self._display_has_started)
                await asyncio.sleep_ms(60)

            except Exception as e:
                print(f"[DISPLAY_CONTROLLER] Driver Bar Error: {e}")
