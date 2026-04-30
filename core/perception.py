"""
感知系统模块
监听用户键盘/鼠标操作频率，识别用户状态
"""

from pynput import keyboard, mouse
from datetime import datetime, timedelta
from typing import Callable, Optional
import threading


class UserActivityMonitor:
    """
    用户活动监视器
    监听键盘敲击和鼠标移动/点击，计算用户活跃度
    """
    
    # 活动阈值定义
    TYPING_THRESHOLD = 100      # 1分钟内敲击超过此值认为是"高强度打字"
    IDLE_THRESHOLD = 10         # 5秒内操作少于此值认为是"空闲"
    
    def __init__(self):
        """初始化活动监视器"""
        # 计数器
        self._key_count = 0
        self._mouse_click_count = 0
        self._mouse_move_count = 0
        
        # 时间窗口（用于计算频率）
        self._window_start = datetime.now()
        self._window_size = 60  # 60秒窗口
        
        # 监听器
        self._keyboard_listener: Optional[keyboard.Listener] = None
        self._mouse_listener: Optional[mouse.Listener] = None
        
        # 回调函数
        self.on_typing_intensive: Optional[Callable[[int], None]] = None  # 高强度打字回调
        self.on_user_idle: Optional[Callable[[], None]] = None  # 用户空闲回调
        self.on_activity_detected: Optional[Callable[[str], None]] = None  # 通用活动检测
        
        # 状态标记（防止重复触发）
        self._typing_intensive_triggered = False
        self._idle_triggered = False
        
        # 运行标记
        self._running = False
        self._lock = threading.Lock()
    
    def start(self) -> bool:
        """
        启动监听器
        
        Returns:
            bool: 是否成功启动
        """
        try:
            self._running = True
            
            # 键盘监听
            self._keyboard_listener = keyboard.Listener(
                on_press=self._on_key_press
            )
            self._keyboard_listener.start()
            
            # 鼠标监听
            self._mouse_listener = mouse.Listener(
                on_click=self._on_mouse_click,
                on_move=self._on_mouse_move
            )
            self._mouse_listener.start()
            
            print("[感知] 活动监视器已启动")
            return True
            
        except Exception as e:
            print(f"[感知] 启动失败: {e}")
            self._running = False
            return False
    
    def stop(self):
        """停止监听器"""
        self._running = False
        
        if self._keyboard_listener:
            self._keyboard_listener.stop()
            self._keyboard_listener = None
            
        if self._mouse_listener:
            self._mouse_listener.stop()
            self._mouse_listener = None
            
        print("[感知] 活动监视器已停止")
    
    def _on_key_press(self, key):
        """键盘按下回调"""
        with self._lock:
            self._key_count += 1
            self._check_window()
            
            # 标记不再空闲
            if self._idle_triggered:
                self._idle_triggered = False
    
    def _on_mouse_click(self, x, y, button, pressed):
        """鼠标点击回调"""
        if pressed:  # 只统计按下
            with self._lock:
                self._mouse_click_count += 1
                self._check_window()
                
                if self._idle_triggered:
                    self._idle_triggered = False
    
    def _on_mouse_move(self, x, y):
        """鼠标移动回调 - 降低采样率避免过多事件"""
        with self._lock:
            # 每10次移动才计数一次，降低敏感度
            if self._mouse_move_count % 10 == 0:
                self._check_window()
                
                if self._idle_triggered:
                    self._idle_triggered = False
            self._mouse_move_count += 1
    
    def _check_window(self):
        """检查时间窗口，计算频率并触发回调"""
        now = datetime.now()
        elapsed = (now - self._window_start).total_seconds()
        
        if elapsed >= self._window_size:
            # 计算频率
            keys_per_minute = self._key_count * (60 / elapsed)
            
            # 检查高强度打字
            if keys_per_minute > self.TYPING_THRESHOLD:
                if not self._typing_intensive_triggered:
                    self._typing_intensive_triggered = True
                    if self.on_typing_intensive:
                        self.on_typing_intensive(self._key_count)
                    if self.on_activity_detected:
                        self.on_activity_detected("typing_intensive")
            else:
                self._typing_intensive_triggered = False
            
            # 重置窗口
            self._window_start = now
            self._key_count = 0
    
    def check_idle(self) -> bool:
        """
        检查用户是否处于空闲状态
        应在主循环中定期调用（如每5秒）
        
        Returns:
            bool: 是否空闲
        """
        now = datetime.now()
        elapsed = (now - self._window_start).total_seconds()
        
        # 如果在5秒内没有活动
        if elapsed > 5:
            total_activity = self._key_count + self._mouse_click_count
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
        with self._lock:
            now = datetime.now()
            elapsed = (now - self._window_start).total_seconds()
            
            return {
                "key_count": self._key_count,
                "mouse_clicks": self._mouse_click_count,
                "mouse_moves": self._mouse_move_count,
                "elapsed_seconds": elapsed,
                "keys_per_minute": self._key_count * (60 / max(elapsed, 1))
            }


# ============ 模块自测试 ============
if __name__ == "__main__":
    print("=" * 40)
    print("模块测试: core/perception.py")
    print("=" * 40)
    
    monitor = UserActivityMonitor()
    
    # 设置回调
    def on_typing(count):
        print(f"[感知] 检测到高强度打字！({count}次按键)")
    
    def on_idle():
        print("[感知] 检测到用户空闲...")
    
    def on_activity(activity_type):
        print(f"[感知] 活动类型: {activity_type}")
    
    monitor.on_typing_intensive = on_typing
    monitor.on_user_idle = on_idle
    monitor.on_activity_detected = on_activity
    
    # 启动
    if monitor.start():
        print("\n[说明] 监视器运行中，请进行键盘/鼠标操作")
        print("[说明] 按Ctrl+C停止测试\n")
        
        try:
            import time
            while True:
                time.sleep(1)
                stats = monitor.get_current_stats()
                if stats["key_count"] > 0:
                    print(f"  当前按键: {stats['key_count']}, 频率: {stats['keys_per_minute']:.1f}/min")
        except KeyboardInterrupt:
            print("\n停止测试...")
        finally:
            monitor.stop()
    else:
        print("[错误] 无法启动监听器，请检查权限")
