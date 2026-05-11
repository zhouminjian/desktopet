"""
交互控制器模块

负责处理所有与用户鼠标交互相关的逻辑，包括：
- 点击与拖拽的区分
- 鼠标悬停的进入与离开
- 交互冷却判断
- 饥饿时拒绝交互的规则
- 交互后触发的动作（如吸附、强制动画）
"""

from PySide6.QtCore import QObject, Signal, QPoint, Qt, QTimer
from PySide6.QtGui import QMouseEvent
import time

from core.config import PetConfig
from core.engine import PetEngine, PetState

class InteractionController(QObject):
    """处理鼠标交互的核心逻辑"""
    
    # 定义信号，用于通知主窗口执行具体动作
    play_animation_requested = Signal(str, int)
    snap_to_edge_requested = Signal()
    pet_requested = Signal()
    show_cooldown_tip_requested = Signal()
    show_hungry_refuse_requested = Signal()
    show_energy_low_refuse_requested = Signal()
    context_menu_requested = Signal(QPoint)
    
    hover_animation_requested = Signal(str)
    hover_animation_ended = Signal()
    lie_hover_tip_requested = Signal()  # lie 状态下鼠标悬停提示
    
    def __init__(self, window: QObject, engine: PetEngine, parent: QObject = None):
        super().__init__(parent)
        self.window = window
        self.engine = engine

        self._dragging = False
        self._drag_offset = QPoint()
        self._drag_start_window_pos = (0, 0)
        self._last_click_time = 0.0 # 用于点击冷却
        self._is_hovering = False # 鼠标是否悬停

    def _is_cooldown_active(self) -> bool:
        """检查是否处于点击冷却期"""
        return (time.time() - self._last_click_time) < PetConfig.INTERACTION_COOLDOWN_TIME

    def is_dragging(self) -> bool:
        """返回当前是否正在拖拽"""
        return self._dragging
        
    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下事件处理"""
        if event.button() == Qt.LeftButton:
            # 饱食度或精力不足时拒绝互动（强制睡眠状态）
            if self.engine.stats.hunger <= PetConfig.HUNGER_INTERACT_REFUSE_THRESHOLD and self.engine.state != PetState.EATING:
                self.show_hungry_refuse_requested.emit()
                return
            if self.engine.stats.energy <= PetConfig.WAKE_ENERGY_THRESHOLD:
                self.show_energy_low_refuse_requested.emit()
                return

            self.window._update_interaction_time()  # 记录互动并尝试唤醒

            # 如果尝试唤醒后依然处于睡眠状态（例如被拒绝唤醒），则中止交互
            if self.window.behavior.is_sleeping():
                return

            self.engine.consume_energy()
            self._dragging = True
            self._drag_offset = event.pos()
            self._drag_start_window_pos = (self.window.x(), self.window.y())
            self.engine.set_state(PetState.DRAGGING)

        elif event.button() == Qt.RightButton:
            self.window._update_interaction_time()  # 记录互动
            self.context_menu_requested.emit(event.pos())

    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动事件处理"""
        if self._dragging:
            new_pos = self.window.mapToGlobal(event.pos() - self._drag_offset)
            self.window.move(new_pos)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """鼠标释放事件处理"""
        if event.button() == Qt.LeftButton and self._dragging:
            self._dragging = False

            # 如果在拖拽期间处于睡眠状态，恢复为SLEEP
            if self.window.behavior.is_sleeping():
                self.engine.set_state(PetState.SLEEP)
            else:
                self.engine.set_state(PetState.IDLE)

            window_dx = self.window.x() - self._drag_start_window_pos[0]
            window_dy = self.window.y() - self._drag_start_window_pos[1]
            drag_distance = (window_dx ** 2 + window_dy ** 2) ** 0.5
            
            if drag_distance > PetConfig.DRAG_DISTANCE_THRESHOLD:
                self.engine.add_activity(int(drag_distance))
                self.play_animation_requested.emit("oneeyes", PetConfig.INTERACTION_COOLDOWN_TIME)
                self.snap_to_edge_requested.emit()
            else:
                if self._is_cooldown_active():
                    self.show_cooldown_tip_requested.emit()
                else:
                    self.play_animation_requested.emit("oneeyes", PetConfig.INTERACTION_COOLDOWN_TIME)
                    self.pet_requested.emit()  # 点击增加经验
                    self._last_click_time = time.time()
    
    def enterEvent(self, event: QMouseEvent):
        """鼠标进入事件处理"""
        self._is_hovering = True
        self.window._update_interaction_time()
        ap = self.window.animation_player
        # lie/tired 动画期间不触发卖萌
        if ap._force_animation in ("lie", "tired") or ap._lie_hold or ap._lie_reverse:
            if ap._force_animation == "lie":
                self.lie_hover_tip_requested.emit()
            return
        if (not self._dragging
                and self.engine.stats.hunger > PetConfig.HUNGER_INTERACT_REFUSE_THRESHOLD
                and self.engine.stats.energy > PetConfig.WAKE_ENERGY_THRESHOLD):
            self.hover_animation_requested.emit("maimeng")

    def leaveEvent(self, event: QMouseEvent):
        """鼠标离开事件处理"""
        self._is_hovering = False
        ap = self.window.animation_player
        # lie/tired 动画期间不触发离开事件
        if ap._force_animation in ("lie", "tired") or ap._lie_hold or ap._lie_reverse:
            return
        self.hover_animation_ended.emit()
