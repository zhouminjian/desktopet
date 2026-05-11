"""
感知系统模块
监听用户键盘/鼠标操作频率，识别用户状态
"""

from pynput import keyboard, mouse
from typing import Callable, Optional
import threading
import time

from core.config import PetConfig


class UserActivityMonitor:
    """
    用户活动监视器
    监听键盘敲击和鼠标点击，计算用户活跃度

    性能优化：
    - 移除 mouse move 监听（每秒上千次事件，获取锁开销大，且与 click 重复）
    - 使用 time.monotonic() 替代 datetime.now()（快 14 倍）
    - _check_window 在锁外执行，仅计数器操作在锁内
    """

    TYPING_THRESHOLD = PetConfig.TYPING_THRESHOLD
    IDLE_THRESHOLD = PetConfig.IDLE_THRESHOLD

    def __init__(self):
        # 计数器
        self._key_count = 0
        self._mouse_click_count = 0

        # 时间窗口
        self._window_start = time.monotonic()
        self._window_size = PetConfig.TYPING_FREQUENCY_WINDOW_SECONDS

        # 监听器
        self._keyboard_listener: Optional[keyboard.Listener] = None
        self._mouse_listener: Optional[mouse.Listener] = None

        # 回调函数
        self.on_typing_intensive: Optional[Callable[[int], None]] = None
        self.on_user_idle: Optional[Callable[[], None]] = None
        self.on_activity_detected: Optional[Callable[[str], None]] = None

        # 状态标记
        self._typing_intensive_triggered = False
        self._idle_triggered = False

        self._running = False
        self._lock = threading.Lock()

    def start(self) -> bool:
        try:
            self._running = True

            self._keyboard_listener = keyboard.Listener(
                on_press=self._on_key_press
            )
            self._keyboard_listener.start()

            # 仅监听点击，不监听移动（移动事件频率过高导致卡顿）
            self._mouse_listener = mouse.Listener(
                on_click=self._on_mouse_click,
            )
            self._mouse_listener.start()

            print("[感知] 活动监视器已启动")
            return True

        except Exception as e:
            print(f"[感知] 启动失败: {e}")
            self._running = False
            return False

    def stop(self):
        self._running = False

        if self._keyboard_listener:
            self._keyboard_listener.stop()
            self._keyboard_listener = None

        if self._mouse_listener:
            self._mouse_listener.stop()
            self._mouse_listener = None

        print("[感知] 活动监视器已停止")

    def _on_key_press(self, key):
        """键盘按下回调 - 仅在锁内递增计数器"""
        with self._lock:
            self._key_count += 1
            if self._idle_triggered:
                self._idle_triggered = False

    def _on_mouse_click(self, x, y, button, pressed):
        """鼠标点击回调"""
        if pressed:
            with self._lock:
                self._mouse_click_count += 1
                if self._idle_triggered:
                    self._idle_triggered = False

    def check_window(self) -> None:
        """
        检查时间窗口，计算频率并触发回调。
        由外部定时器（如 _on_update）调用，不在 pynput 回调线程中执行。
        """
        now = time.monotonic()
        with self._lock:
            elapsed = now - self._window_start
            if elapsed < self._window_size:
                return
            key_count = self._key_count
            self._window_start = now
            self._key_count = 0

        # 锁外执行回调（避免阻塞 pynput 线程）
        keys_per_minute = key_count * (60 / elapsed)

        if keys_per_minute > self.TYPING_THRESHOLD:
            if not self._typing_intensive_triggered:
                self._typing_intensive_triggered = True
                if self.on_typing_intensive:
                    self.on_typing_intensive(key_count)
                if self.on_activity_detected:
                    self.on_activity_detected("typing_intensive")
        else:
            self._typing_intensive_triggered = False

    def check_idle(self) -> bool:
        """
        检查用户是否处于空闲状态。
        由外部定时器调用。
        """
        now = time.monotonic()
        with self._lock:
            elapsed = now - self._window_start
            total_activity = self._key_count + self._mouse_click_count

        if elapsed > PetConfig.IDLE_CHECK_INTERVAL:
            if total_activity < self.IDLE_THRESHOLD:
                if not self._idle_triggered:
                    self._idle_triggered = True
                    if self.on_user_idle:
                        self.on_user_idle()
                    if self.on_activity_detected:
                        self.on_activity_detected("idle")
                return True

        return False

    def get_current_stats(self) -> dict:
        """获取当前活动统计"""
        now = time.monotonic()
        with self._lock:
            elapsed = now - self._window_start
            return {
                "key_count": self._key_count,
                "mouse_clicks": self._mouse_click_count,
                "elapsed_seconds": elapsed,
                "keys_per_minute": self._key_count * (60 / max(elapsed, 1)),
            }
