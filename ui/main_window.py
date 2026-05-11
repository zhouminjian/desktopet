"""
桌面宠物主窗体 (View层)
实现透明置顶窗口、鼠标拖拽、动画显示
"""

from PySide6.QtWidgets import QMainWindow, QWidget, QApplication, QMenu, QSystemTrayIcon, QGraphicsDropShadowEffect
from PySide6.QtCore import Qt, QTimer, QPoint, QSize, Signal, QObject
from PySide6.QtGui import QPainter, QPixmap, QColor, QCursor, QIcon, QAction
import sys
import os
import time

from core.engine import PetEngine, PetState, PetStats
from core.config import PetConfig
from core.behavior import BehaviorController, PetAction
from ui.interaction_controller import InteractionController
from ui.animation_player import AnimationPlayer, AnimationPlayerSignals

class PetSignals(QObject):
    """信号类 - 用于前后端通信，保持变量传递一致"""
    stats_updated = Signal(PetStats)  # 属性更新信号
    state_changed = Signal(PetState)  # 状态变化信号
    feed_requested = Signal()  # 喂食请求信号
    pet_requested = Signal()  # 抚摸请求信号
    hunger_changed = Signal(float)  # 饱食度变化信号 (新值)
    exp_gained = Signal(int)  # 获得经验信号 (数量)
    change_personality_requested = Signal()  # 更改名字和性格


class PetMainWindow(QMainWindow):
    """
    宠物主窗体
    特性：透明背景、置顶显示、无边框、鼠标穿透拖拽
    """
    
    # 窗口尺寸常量 - 默认尺寸，会根据实际图片调整
    WINDOW_WIDTH = PetConfig.WINDOW_WIDTH
    WINDOW_HEIGHT = PetConfig.WINDOW_HEIGHT
    MAX_WINDOW_SIZE = PetConfig.MAX_WINDOW_SIZE

    # 动画帧率
    FPS = PetConfig.FPS
    FRAME_INTERVAL = PetConfig.FRAME_INTERVAL
    
    def __init__(self, engine: PetEngine, parent=None):
        """
        初始化主窗体
        
        Args:
            engine: 宠物引擎实例 (Model层)
        """
        super().__init__(parent)
        
        self.engine = engine
        self.signals = PetSignals()

        self.animation_player = AnimationPlayer(engine)
        self.animation_player.signals.animation_frame_updated.connect(self.update)
        self.animation_player.on_walk_cycle_complete = self.on_walk_cycle_complete

        self.interaction_controller = InteractionController(self, engine, self)
        self.interaction_controller.play_animation_requested.connect(self._start_force_animation)
        self.interaction_controller.snap_to_edge_requested.connect(lambda: self.perform_action(PetAction.SNAP_TO_EDGE))
        self.interaction_controller.pet_requested.connect(self._do_pet)
        self.interaction_controller.show_cooldown_tip_requested.connect(self._show_cooldown_tip)
        self.interaction_controller.show_hungry_refuse_requested.connect(self._show_hungry_refuse)
        self.interaction_controller.show_energy_low_refuse_requested.connect(self._show_energy_low_refuse)
        self.interaction_controller.context_menu_requested.connect(self._show_context_menu)
        self.interaction_controller.hover_animation_requested.connect(self.animation_player.start_hover_animation)
        self.interaction_controller.hover_animation_ended.connect(self.animation_player.end_hover_animation)
        self.interaction_controller.lie_hover_tip_requested.connect(self._show_lie_hover_tip)

        # 行为控制器（睡眠、自动动作、互动时间追踪）
        self.behavior = BehaviorController(engine)
        self.behavior.on_sleep = self._on_behavior_sleep
        self.behavior.on_wake_up = self._on_behavior_wake_up
        self.behavior.on_perform_action = self.perform_action
        self.behavior.on_tired = self._on_tired

        self.interaction_controller.pet_requested.connect(lambda: self.behavior.update_interaction_time())
        self.interaction_controller.context_menu_requested.connect(lambda _: self.behavior.update_interaction_time())

        # 窗口移动动画相关
        self._walk_timer = QTimer(self)
        self._walk_timer.timeout.connect(self._on_snap_step)
        self._anim_target: tuple[int, int] | None = None
        self._anim_start: tuple[int, int] | None = None
        self._anim_progress: float = 0.0
        self._anim_name: str = ""

        # 动作动画状态（由PetMainWindow控制，非AnimationPlayer）
        self._is_jumping: bool = False
        self._jump_time: int = 0
        self._jump_timer: QTimer = QTimer(self)
        
        self._is_rolling: bool = False
        self._roll_time: int = 0
        self._roll_angle: int = 0
        self._roll_timer: QTimer = QTimer(self)

        self._is_cute: bool = False
        self._cute_time: int = 0
        self._cute_timer: QTimer = QTimer(self)
        self._cute_original_x: int = 0

        # Walk 漫步状态
        self._is_walking: bool = False
        self._walk_target_cycles: int = 0
        self._walk_completed_cycles: int = 0

        # 3D模式支持（已归档）
        self._3d_mode = False
        self._3d_viewer = None
        self._3d_model_path: str | None = None
        
        # 状态更新定时器 (每秒更新一次属性)
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._on_update)
        self._update_timer.start(PetConfig.UPDATE_TIMER_INTERVAL)

        # 自动动作定时器 (空闲时随机执行动作)
        self._action_timer = QTimer(self)
        self._action_timer.timeout.connect(self._on_auto_action)
        self._action_timer.start(PetConfig.AUTO_ACTION_INTERVAL_MEAN)

        # 气泡组件引用（由外部通过 set_bubble 设置）
        self._bubble = None
        self._bubble_offset = QPoint(0, PetConfig.BUBBLE_OFFSET_Y)
        self.bubble_mgr = None  # BubbleManager 实例，由 main.py 设置

        # 初始化UI
        self._setup_window()
        self._connect_signals()
    
    def _setup_window(self):
        """配置窗口属性 - 透明置顶无边框"""
        # 设置窗口标志
        self.setWindowFlags(
            Qt.FramelessWindowHint |      # 无边框
            Qt.WindowStaysOnTopHint |     # 置顶显示
            Qt.Tool |                     # 不在任务栏显示
            Qt.WindowDoesNotAcceptFocus   # 不获取焦点
        )
        
        # 设置透明背景
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        
        # 设置窗口大小
        self.setFixedSize(self.WINDOW_WIDTH, self.WINDOW_HEIGHT)
        
        # 默认位置 - 屏幕右下角（任务栏上方）
        screen = QApplication.primaryScreen().geometry()
        self.move(
            screen.width() - self.WINDOW_WIDTH - PetConfig.DEFAULT_SCREEN_MARGIN_X,
            screen.height() - self.WINDOW_HEIGHT - PetConfig.DEFAULT_SCREEN_MARGIN_BOTTOM
        )
        
        # 设置窗口标题（调试用）
        self.setWindowTitle("Pii - 桌面宠物")
        
        # 强制显示窗口（确保不被隐藏）
        self.show()
        self.raise_()
        
        # 启用鼠标追踪，用于检测悬停
        self.setMouseTracking(True)
    
    def _connect_signals(self):
        """连接前后端信号 - 保持变量一致"""
        # 引擎 -> UI
        self.engine.on_stats_change = self._on_engine_stats_change
        self.engine.on_state_change = self._on_engine_state_change
        
        # UI -> 引擎 (通过信号)
        self.signals.feed_requested.connect(self._do_feed)
        self.signals.pet_requested.connect(self._do_pet)
        
        # InteractionController -> UI (更新互动时间)
        self.interaction_controller.pet_requested.connect(self._update_interaction_time)

    def _init_3d_viewer(self):
        """初始化3D查看器（已归档到3D/目录，暂不启用）"""
        self._3d_viewer = None
    
    def enable_3d_mode(self, glb_path: str | None = None):
        """
        启用3D模式（已归档，使用2D模式）
        """
        print("[3D] 3D模式已归档，继续使用2D模式")
        # self._3d_mode = True
        # self._3d_model_path = glb_path
        # self._animation_timer.stop()
        # self._3d_viewer.show()
        # self._3d_viewer.raise_()
        # if glb_path and os.path.exists(glb_path):
        #     self._3d_viewer.load_model(glb_path)
        
        print("[3D] 3D模式已启用")
    
    def disable_3d_mode(self):
        """禁用3D模式，回到2D序列帧"""
        self._3d_mode = False
        if self._3d_viewer:
            self._3d_viewer.hide()
        self.update()  # 重绘2D层
        print("[2D] 回到2D模式")
    
    def _on_3d_clicked(self):
        """3D模型被点击（已归档）"""
        pass
    
    def _on_3d_model_loaded(self, success: bool, message: str):
        """3D模型加载完成回调（已归档）"""
        pass

    def paintEvent(self, event):
        """绘制事件 - 绘制宠物图片，支持缩放、旋转和特殊效果"""
        # 调试输出（每10次绘制输出一次）
        if not hasattr(self, '_paint_count'):
            self._paint_count = 0
        self._paint_count += 1
        if self._paint_count % 60 == 1:  # 约每2.5秒输出一次
            print(f"[绘制] paintEvent 被调用 #{self._paint_count}, 窗口: ({self.x()},{self.y()}) {self.width()}x{self.height()}, 可见: {self.isVisible()}")
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)  # 平滑缩放

        pixmap = self.animation_player.get_current_pixmap(self.engine.state, self.engine.stats.hunger, self.behavior.is_sleeping())
        if not pixmap:
            return

        win_width = self.width()
        win_height = self.height()

        # 用 Source 模式清空画布，避免残留和 alpha 混合黑边
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.transparent)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        # 应用变换：旋转（翻滚）、缩放（跳跃）、位移
        painter.translate(win_width // 2, win_height // 2)

        # 翻滚旋转
        if hasattr(self, '_is_rolling') and self._is_rolling and hasattr(self, '_roll_angle'):
            painter.rotate(self._roll_angle)

        # 跳跃时的轻微缩放
        if hasattr(self, '_is_jumping') and self._is_jumping and hasattr(self, '_jump_time'):
            jump_progress = min(1.0, self._jump_time / PetConfig.JUMP_DURATION)
            if jump_progress < 0.5:
                scale = 1.0 + PetConfig.JUMP_SCALE_FACTOR * (jump_progress * 2)
            else:
                scale = 1.0 + PetConfig.JUMP_SCALE_FACTOR * ((1 - jump_progress) * 2)
            painter.scale(scale, scale)

        # 卖萌歪头
        if hasattr(self, '_is_cute') and self._is_cute:
            painter.rotate(PetConfig.CUTE_TILT_ANGLE)

        painter.translate(-win_width // 2, -win_height // 2)

        # 图片与窗口尺寸不一致时，缩放后再绘制
        img_width = pixmap.width()
        img_height = pixmap.height()
        if img_width != win_width or img_height != win_height:
            draw_pixmap = pixmap.scaled(
                win_width, win_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        else:
            draw_pixmap = pixmap

        # 绘制图片（居中）
        draw_x = (win_width - draw_pixmap.width()) // 2
        draw_y = (win_height - draw_pixmap.height()) // 2
        painter.drawPixmap(draw_x, draw_y, draw_pixmap)
    
    def mousePressEvent(self, event):
        """鼠标按下 - 委托给交互控制器"""
        self.interaction_controller.mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """鼠标移动 - 委托给交互控制器"""
        self.interaction_controller.mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """鼠标释放 - 委托给交互控制器"""
        self.interaction_controller.mouseReleaseEvent(event)
    
    def enterEvent(self, event):
        """鼠标进入 - 委托给交互控制器"""
        self.interaction_controller.enterEvent(event)
    
    def leaveEvent(self, event):
        """鼠标离开 - 委托给交互控制器"""
        self.interaction_controller.leaveEvent(event)
    
    def _start_force_animation(self, anim_name: str, wait_time: int = 1):
        """启动强制动画（播放1轮+等待后恢复idle）"""
        self.animation_player.start_force_animation(anim_name, wait_time)
        self.update()
    
    def _show_hungry_refuse(self):
        """饥饿时拒绝互动"""
        if self.bubble_mgr:
            self.bubble_mgr.show_hungry_refuse(self.engine.name)
            self._update_bubble_position()

    def _show_energy_low_refuse(self):
        """精力不足时拒绝互动"""
        if self.bubble_mgr:
            self.bubble_mgr.show_energy_low_refuse(self.engine.name)
            self._update_bubble_position()

    def _show_lie_hover_tip(self):
        """lie 状态下鼠标悬停提示"""
        if self.bubble_mgr:
            self.bubble_mgr.show_lie_hover_tip(self.engine.name)
            self._update_bubble_position()

    def _show_cooldown_tip(self):
        """冷却中提示"""
        if self.bubble_mgr:
            self.bubble_mgr.show_cooldown_tip(self.engine.name)
            self._update_bubble_position()
    
    def _show_context_menu(self, pos):
        """显示右键菜单"""
        menu = QMenu(self)
        
        # 等级和经验值信息
        exp_needed = self.engine.get_exp_for_next_level()
        level_text = f"🐱 {self.engine.name} | Lv.{self.engine.stats.level} ({self.engine.growth_stage.display_name})"
        exp_text = f"⭐ 经验: {self.engine.stats.exp}/{exp_needed}"
        
        level_action = menu.addAction(level_text)
        level_action.setEnabled(False)
        exp_action = menu.addAction(exp_text)
        exp_action.setEnabled(False)
        menu.addSeparator()
        
        # 状态信息
        status_text = f"🍖 饱食度: {self.engine.stats.hunger:.0f} | ❤️ 心情: {self.engine.stats.happiness:.0f} | ⚡ 精力: {self.engine.stats.energy:.0f}"
        status_action = menu.addAction(status_text)
        status_action.setEnabled(False)
        menu.addSeparator()
        
        # 喂食选项
        feed_action = menu.addAction("🍖 喂食 (+10经验)")
        feed_action.triggered.connect(self.signals.feed_requested.emit)
        
        # 抚摸选项
        pet_action = menu.addAction("👋 抚摸 (+5经验)")
        pet_action.triggered.connect(self.signals.pet_requested.emit)

        menu.addSeparator()

        # 更改名字和性格
        edit_action = menu.addAction("✏️ 更改名字和性格")
        edit_action.triggered.connect(self.signals.change_personality_requested.emit)

        menu.addSeparator()

        # 退出
        exit_action = menu.addAction("❌ 退出")
        exit_action.triggered.connect(self._on_exit)
        
        menu.exec(self.mapToGlobal(pos))
    
    def _do_feed(self):
        """执行喂食"""
        old_hunger = self.engine.stats.hunger
        was_sleeping = self.behavior.is_sleeping()
        success = self.engine.feed()
        if success:
            # engine.feed() 会把状态设置为 EATING。
            # 我们播放强制动画并在2秒后恢复正确的引擎状态。
            self._start_force_animation("eating", wait_time=1)
            restore_state = PetState.SLEEP if was_sleeping else PetState.IDLE
            QTimer.singleShot(2000, lambda: self.engine.set_state(restore_state))

            self.update()  # 重绘
            # 发送数值变化信号
            hunger_increase = self.engine.stats.hunger - old_hunger
            self.signals.hunger_changed.emit(hunger_increase)
            self.signals.exp_gained.emit(self.engine.EXP_PER_FEED)
    
    def _do_pet(self):
        """执行抚摸"""
        self.engine.pet()
        self.update()
        # 发送经验获得信号
        self.signals.exp_gained.emit(self.engine.EXP_PER_PET)
        # 显示智能互动气泡
        if self.bubble_mgr:
            self.bubble_mgr.show_petted(self.engine)
    
    def _on_engine_stats_change(self, stats: PetStats):
        """引擎属性变化回调"""
        self.signals.stats_updated.emit(stats)
        self.update()  # 重绘显示状态变化
    
    def _on_engine_state_change(self, state: PetState):
        """引擎状态变化回调"""
        if state == PetState.IDLE:
            self.behavior.record_idle_start()
        self.signals.state_changed.emit(state)
        self.update()



    def _on_update(self):
        """定时更新 - 引擎衰减 + 睡眠检测"""
        self.engine.update()
        self.behavior.check_sleep(self.interaction_controller.is_dragging())
        self.animation_player.set_is_dragging(self.interaction_controller.is_dragging())
        # 精力恢复后清除 tired 动画
        if (self.animation_player._force_animation == "tired" or self.animation_player._tired_hold):
            if self.engine.stats.energy > PetConfig.ENERGY_TIRED_THRESHOLD:
                ap = self.animation_player
                ap._force_animation = None
                ap._force_anim_cycles = 0
                ap._tired_hold = False
                ap._anim_cycle_pause = False
                ap._current_frame = 0

    def _update_interaction_time(self):
        """更新最后互动时间；若在睡眠中则尝试唤醒，唤醒失败时显示原因"""
        if self.behavior.is_sleeping():
            # 睡眠中：先尝试唤醒，唤醒成功后再更新时间（从唤醒时刻开始计算120秒）
            woke = self.behavior.wake_up()
            if woke:
                self.behavior.update_interaction_time()
            else:
                reason = self.behavior.get_wake_refusal_reason()
                self.bubble_mgr.show_wake_refusal(self.engine.name, reason)
                self._update_bubble_position()
        else:
            self.behavior.update_interaction_time()

    def _on_behavior_sleep(self, reason: str = "idle"):
        """行为控制器触发睡眠时的视觉回调"""
        # 清除所有强制/悬停/lie/tired 动画，确保 sleep 动画能正确显示
        ap = self.animation_player
        ap._force_animation = None
        ap._force_anim_cycles = 0
        ap._hover_animation = None
        ap._lie_hold = False
        ap._lie_reverse = False
        ap._lie_repeat_timer.stop()
        ap._tired_hold = False
        ap._anim_cycle_pause = False
        ap._current_frame = 0
        if self._bubble:
            if reason == "energy_low":
                self.bubble_mgr.show_energy_sleep(self.engine.name)
            else:
                self.bubble_mgr.show_sleep(self.engine.name)
            self._update_bubble_position()
        self.update()

    def _on_tired(self):
        """精力疲劳回调：触发 tired 动画 + 气泡提醒"""
        ap = self.animation_player
        # 已在播放 tired 则不重复触发
        if ap._force_animation == "tired":
            return
        ap.start_force_animation("tired")
        if self.bubble_mgr:
            self.bubble_mgr.show_energy_tired(self.engine.name)
            self._update_bubble_position()

    def _on_behavior_wake_up(self):
        """行为控制器触发唤醒时的视觉回调"""
        if self._bubble:
            self.bubble_mgr.show_wake(self.engine.name)
            self._update_bubble_position()
        self.update()
    
    def perform_action(self, action_type: str = None):
        """执行宠物动作 - 对外接口（分发给具体动作方法）"""
        if action_type is None:
            action_type = self.behavior.choose_weighted_action()

        print(f"[动作] 开始执行: {action_type}")

        action_map = {
            PetAction.IDLE_BLINK: self._action_idle_blink,
            PetAction.SNAP_TO_EDGE: self._action_snap_to_edge,
            PetAction.WALK_AROUND: self._action_walk_around,
            PetAction.JUMP: self._action_jump,
            PetAction.ROLL: self._action_roll,
            PetAction.PLAY_CUTE: self._action_play_cute,
        }
        handler = action_map.get(action_type)
        if handler:
            handler()
        else:
            print(f"[动作] 未知动作类型: {action_type}")
    
    def _action_idle_blink(self):
        """
        动作: 发呆眨眼（最常见的空闲动画）
        不移动位置，只改变表情产生眨眼效果
        """
        print("[动作-眨眼] 眨一下眼睛~")
        
        # 触发动画播放器的眨眼状态
        self.animation_player.set_is_blinking(True)
        self.update()
        QTimer.singleShot(PetConfig.BLINK_ANIM_DURATION, lambda: self.animation_player.set_is_blinking(False))
        QTimer.singleShot(PetConfig.BLINK_ANIM_DURATION, self.update)
    

    
    def _action_snap_to_edge(self):
        """动作1: 吸附到最近的屏幕边缘"""
        screen = QApplication.primaryScreen().geometry()
        current_x = self.x()
        current_y = self.y()
        
        # 计算到各边缘的距离
        dist_left = current_x
        dist_right = screen.width() - current_x - self.WINDOW_WIDTH
        dist_top = current_y
        dist_bottom = screen.height() - current_y - self.WINDOW_HEIGHT
        
        margin = PetConfig.SNAP_EDGE_MARGIN
        
        # 调试输出
        print(f"[动作-吸附] Pii位置: ({current_x}, {current_y}), 屏幕: {screen.width()}x{screen.height()}")
        print(f"[动作-吸附] 距离: 左={dist_left}, 右={dist_right}, 上={dist_top}, 下={dist_bottom}")
        
        # 找出最近的边缘
        distances = [
            (dist_left, 'left'),
            (dist_right, 'right'),
            (dist_top, 'top'),
            (dist_bottom, 'bottom')
        ]
        
        nearest_dist, nearest_edge = min(distances, key=lambda x: abs(x[0]))
        print(f"[动作-吸附] 最近边缘: {nearest_edge}, 距离: {nearest_dist}")
        
        # 如果距离边缘很近（小于margin+5），不需要移动
        if abs(nearest_dist) <= PetConfig.SNAP_ALREADY_CLOSE:
            print(f"[动作-吸附] 已紧贴{nearest_edge}边缘，无需移动，跳过摇摆")
            return
        
        # 计算目标位置
        target_x, target_y = current_x, current_y
        
        if nearest_edge == 'left':
            target_x = margin
        elif nearest_edge == 'right':
            target_x = screen.width() - self.WINDOW_WIDTH - margin
        elif nearest_edge == 'top':
            target_y = margin
        elif nearest_edge == 'bottom':
            target_y = screen.height() - self.WINDOW_HEIGHT - PetConfig.TASKBAR_CLEARANCE
        
        self._start_move_animation(target_x, target_y, f"吸附-{nearest_edge}")

    def _action_walk_around(self):
        """播放 walk 动画，按循环次数结束后自动停止"""
        # 如果引擎状态已经被外力打断（比如被拖拽了），则清理之前的状态并允许重新触发
        if self._is_walking and self.engine.state != PetState.WALK:
            self._is_walking = False

        if self._is_walking:
            return

        import random
        self._walk_target_cycles = random.randint(PetConfig.WALK_CYCLE_MIN, PetConfig.WALK_CYCLE_MAX)
        self._walk_completed_cycles = 0

        print(f"[动作-漫步] 目标{self._walk_target_cycles}次循环")

        self._is_walking = True
        self.engine.set_state(PetState.WALK)

        # 鼓励气泡（lie 动画期间不显示 walk 气泡）
        if self.bubble_mgr and not self.animation_player._lie_hold and self.animation_player._force_animation != "lie":
            self.bubble_mgr.show_walk_encourage()
            self._update_bubble_position()

    def on_walk_cycle_complete(self):
        """由 animation_player 在 walk 动画每完成一个循环时调用"""
        if not self._is_walking:
            return
        self._walk_completed_cycles += 1
        if self._walk_completed_cycles >= self._walk_target_cycles:
            self._end_walk()

    def _end_walk(self):
        """Walk 完成，恢复 IDLE"""
        self._is_walking = False
        self.behavior.record_idle_start()
        self.engine.set_state(PetState.IDLE)
        print("[动作-漫步] 结束")
        print("[动作-漫步] 结束，回到 IDLE")

    def _action_jump(self):
        """动作2: 跳跃 - 向上跳跃后落回原位"""
        # 防止重复触发
        if hasattr(self, '_is_jumping') and self._is_jumping:
            return
        
        print("[动作-跳跃] 🦘 跳跃！")
        
        # 3D模式已归档，使用2D动画
        
        # 获取当前位置
        original_x = self.x()
        original_y = self.y()
        
        # 跳跃参数
        jump_height = PetConfig.JUMP_HEIGHT
        jump_duration = PetConfig.JUMP_DURATION
        
        # 创建跳跃动画计时器
        self._jump_time = 0
        self._jump_timer = QTimer(self)
        self._jump_timer.timeout.connect(lambda: self._on_jump_step(original_x, original_y, jump_height, jump_duration))
        self._jump_timer.start(PetConfig.ACTION_FPS_INTERVAL)
        
        # 设置跳跃状态（可以通过引擎状态反映到表情）
        self._is_jumping = True
    
    def _on_jump_step(self, original_x: int, original_y: int, jump_height: int, duration: int):
        """跳跃动画单步"""
        self._jump_time += PetConfig.ACTION_FPS_INTERVAL
        progress = min(1.0, self._jump_time / duration)
        
        # 抛物线运动: y = 4 * h * x * (1-x)
        height_offset = int(4 * jump_height * progress * (1 - progress))
        
        # 稍微左右摇摆
        wobble = int(PetConfig.JUMP_WOBBLE * (0.5 - abs(progress - 0.5)))
        
        new_y = original_y - height_offset
        new_x = original_x + wobble
        
        self.move(new_x, new_y)
        
        if progress >= 1.0:
            self._jump_timer.stop()
            self._is_jumping = False
            # 回到原位
            self.move(original_x, original_y)
            print("[动作-跳跃] 落地~")
    
    def _action_roll(self):
        """动作3: 翻滚 - 360度旋转"""
        # 防止重复触发
        if hasattr(self, '_is_rolling') and self._is_rolling:
            return
        
        print("[动作-翻滚] 🔄 翻滚！")
        
        # 3D模式已归档，使用2D动画
        
        # 翻滚动画参数
        roll_duration = PetConfig.ROLL_DURATION
        
        self._roll_time = 0
        self._roll_timer = QTimer(self)
        self._roll_timer.timeout.connect(lambda: self._on_roll_step(roll_duration))
        self._roll_timer.start(PetConfig.ACTION_FPS_INTERVAL)
        
        self._is_rolling = True
    
    def _on_roll_step(self, duration: int):
        """翻滚动画单步"""
        self._roll_time += PetConfig.ACTION_FPS_INTERVAL
        progress = min(1.0, self._roll_time / duration)
        
        # 计算旋转角度 (0-360度)
        self._roll_angle = int(360 * progress)
        self.update()  # 触发重绘，应用旋转
        
        if progress >= 1.0:
            self._roll_timer.stop()
            self._is_rolling = False
            self._roll_angle = 0
            self.update()
            print("[动作-翻滚] 翻滚完成~")
    
    def _action_play_cute(self):
        """动作4: 卖萌 - 歪头+眨眼+左右摇摆"""
        # 防止重复触发
        if hasattr(self, '_is_cute') and self._is_cute:
            return
        
        print("[动作-卖萌] 🥺 卖萌中~")
        
        # 3D模式已归档，使用2D动画
        
        # 卖萌动画序列
        cute_duration = PetConfig.CUTE_DURATION
        
        self._cute_time = 0
        self._cute_timer = QTimer(self)
        self._cute_timer.timeout.connect(lambda: self._on_cute_step(cute_duration))
        self._cute_timer.start(PetConfig.CUTE_FPS_INTERVAL)
        
        self._is_cute = True
        self._cute_original_x = self.x()
    
    def _on_cute_step(self, duration: int):
        """卖萌动画单步"""
        self._cute_time += PetConfig.CUTE_FPS_INTERVAL
        progress = min(1.0, self._cute_time / duration)
        
        # 正弦波摇摆
        import math
        wobble = int(PetConfig.CUTE_WOBBLE * math.sin(progress * 4 * math.pi))
        
        new_x = self._cute_original_x + wobble
        self.move(new_x, self.y())
        
        if progress >= 1.0:
            self._cute_timer.stop()
            self._is_cute = False
            self.move(self._cute_original_x, self.y())
            print("[动作-卖萌] 卖萌结束~")

    def _on_auto_action(self):
        """自动动作定时器回调 - 委托给 BehaviorController"""
        # lie/tired 动画期间不触发自动动作（idle/walk/snap）
        if self.animation_player._force_animation in ("lie", "tired") or self.animation_player._lie_hold or self.animation_player._lie_reverse:
            self._action_timer.start(PetConfig.ACTION_FALLBACK_INTERVAL)
            return
        triggered = self.behavior.try_auto_action(self.interaction_controller.is_dragging())
        next_interval = self.behavior.get_random_interval()
        if not triggered:
            next_interval = 1000
        self._action_timer.start(next_interval)

    def on_interact(self, interact_type: str = "pet"):
        """外部互动接口 (pet/feed/click)"""
        self._update_interaction_time()  # 记录互动
        
        # 饥饿时拒绝互动（喂食除外）
        if self.engine.stats.hunger <= PetConfig.HUNGER_INTERACT_REFUSE_THRESHOLD and self.engine.state != PetState.EATING:
            if interact_type != "feed":
                self._show_hungry_refuse()
                return
        
        # 吸附动画进行中
        if hasattr(self, '_anim_target'):
            return
        
        if interact_type == "pet":
            # 点击冷却检查
            if self.interaction_controller._is_cooldown_active():
                self._show_cooldown_tip()
                return
            self._start_force_animation("oneeyes", wait_time=1)
        elif interact_type == "feed":
            pass  # 喂食由外部处理
    
    def _start_click_animation(self):
        """点击时触发oneeyes（已废弃，用_start_force_animation代替）"""
        self._start_force_animation("oneeyes", wait_time=1)
    
    # ============ 动画底层实现 ============
    
    def _start_move_animation(self, target_x: int, target_y: int, action_name: str):
        """
        启动位移动画 - 底层实现

        Args:
            target_x: 目标X坐标
            target_y: 目标Y坐标
            action_name: 动作名称（用于日志）
        """
        start_x = self.x()
        start_y = self.y()

        # 计算距离
        distance = ((target_x - start_x) ** 2 + (target_y - start_y) ** 2) ** 0.5

        if distance < 10:
            # 距离太近，直接移动
            self.move(target_x, target_y)
            return

        # 记录活动量
        self.engine.add_activity(int(distance))

        # 设置动画状态
        self._anim_target = (target_x, target_y)
        self._anim_start = (start_x, start_y)
        self._anim_progress = 0.0
        self._anim_name = action_name

        # 仅在非 walk 状态下设置 WALK（避免与 _action_walk_around 冲突）
        if not self._is_walking:
            self.engine.set_state(PetState.WALK)

        # 启动动画定时器
        self._walk_timer.start(PetConfig.ACTION_FPS_INTERVAL)

        print(f"[动作] {action_name} 开始移动，距离: {distance:.0f}像素")
    
    def set_bubble(self, bubble, offset: QPoint = QPoint(0, PetConfig.BUBBLE_OFFSET_Y)):
        """设置对话框引用，用于跟随移动"""
        self._bubble = bubble
        self._bubble_offset = offset
    
    def _update_bubble_position(self):
        """更新对话框位置 - 根据宠物贴边情况决定气泡方位和箭头方向"""
        if not self._bubble or not self._bubble.isVisible():
            return

        pii_top_left = self.mapToGlobal(QPoint(0, 0))
        pii_x = pii_top_left.x()
        pii_y = pii_top_left.y()
        # 使用 availableGeometry 获取包含多显示器且排除了任务栏的实际可用区域
        screen = self.screen().availableGeometry()
        bw = self._bubble.width()
        bh = self._bubble.height()
        gap = PetConfig.BUBBLE_GAP
        margin = PetConfig.BUBBLE_SCREEN_MARGIN

        dist_left = pii_x - screen.left()
        dist_right = screen.right() - (pii_x + self.WINDOW_WIDTH)
        dist_top = pii_y - screen.top()
        dist_bottom = screen.bottom() - (pii_y + self.WINDOW_HEIGHT)

        # 判断宠物在当前屏幕水平方向的偏左/偏右
        screen_mid_x = screen.left() + screen.width() // 2
        pet_center_x = pii_x + self.WINDOW_WIDTH // 2
        is_left_half = pet_center_x < screen_mid_x

        bubble_x = 0
        bubble_y = 0
        arrow_direction = "down"

        # 各边阈值不同：底部需要更大（任务栏上方有留白）
        edge_threshold_bottom = PetConfig.BUBBLE_EDGE_THRESHOLD_BOTTOM
        edge_threshold_top = PetConfig.BUBBLE_EDGE_THRESHOLD_TOP
        edge_threshold_side = PetConfig.SNAP_EDGE_MARGIN * 2

        if dist_right < edge_threshold_side:
            # 贴右边 → 气泡在左上方，箭头右下角指向宠物
            bubble_x = pii_x - bw - gap
            bubble_y = pii_y - bh - gap
            arrow_direction = "right-down"

        elif dist_left < edge_threshold_side:
            # 贴左边 → 气泡在右上方，箭头左下角指向宠物
            bubble_x = pii_x + self.WINDOW_WIDTH + gap
            bubble_y = pii_y - bh - gap
            arrow_direction = "left-down"

        elif dist_bottom < edge_threshold_bottom:
            # 贴底边 → 根据偏左/偏右决定气泡方位
            bubble_y = pii_y - bh - gap
            if is_left_half:
                # 偏左 → 气泡在右侧，箭头左下侧指向宠物
                bubble_x = pii_x + self.WINDOW_WIDTH + gap
                arrow_direction = "left-down"
            else:
                # 偏右 → 气泡在左侧，箭头右下侧指向宠物
                bubble_x = pii_x - bw - gap
                arrow_direction = "right-down"

        elif dist_top < edge_threshold_top:
            # 贴顶边 → 根据偏左/偏右决定气泡方位
            bubble_y = pii_y + self.WINDOW_HEIGHT + gap
            if is_left_half:
                # 偏左 → 气泡在右侧，箭头左上角指向宠物
                bubble_x = pii_x + self.WINDOW_WIDTH + gap
                arrow_direction = "left-up"
            else:
                # 偏右 → 气泡在左侧，箭头右上角指向宠物
                bubble_x = pii_x - bw - gap
                arrow_direction = "right-up"

        else:
            # 不贴边 → 默认上方居中，箭头向下
            bubble_x = pii_x + (self.WINDOW_WIDTH - bw) // 2
            bubble_y = pii_y - bh - gap
            arrow_direction = "down"

        # 确保不超出当前屏幕边界
        bubble_x = max(screen.left() + margin, min(screen.right() - bw - margin, bubble_x))
        bubble_y = max(screen.top() + margin, min(screen.bottom() - bh - margin, bubble_y))

        self._bubble.set_arrow_direction(arrow_direction)
        self._bubble.move(bubble_x, bubble_y)
    
    def _on_snap_step(self):
        """动画步进 - 通用实现，同时更新对话框位置"""
        if not hasattr(self, '_anim_target'):
            print(f"[动作-步进] 动画中断: _anim_target不存在")
            self._walk_timer.stop()
            if self.behavior.is_sleeping():
                self.engine.set_state(PetState.SLEEP)
            else:
                self.engine.set_state(PetState.IDLE)
            return
        
        # 调试输出前3帧和最后3帧
        if self._anim_progress < 0.15 or self._anim_progress > 0.85:
            current_pos = (self.x(), self.y())
            print(f"[动作-步进] 进度={self._anim_progress:.2f}, 位置={current_pos}, 目标={self._anim_target}")
        
        # 进度增加（按 MOVE_ANIM_DURATION_MS 和帧率计算每帧步进）
        total_frames = PetConfig.MOVE_ANIM_DURATION_MS / 1000.0 * PetConfig.MOVE_ANIM_FPS
        self._anim_progress += 1.0 / total_frames
        
        if self._anim_progress >= 1.0:
            # 位移动画完成
            self.move(self._anim_target[0], self._anim_target[1])
            self._update_bubble_position()
            self._walk_timer.stop()
            print(f"[动作] {self._anim_name} 位移完成")
            delattr(self, '_anim_target')

            # walk 状态下由 animation_player 循环回调控制结束，不动 state
            if not self._is_walking:
                if self.behavior.is_sleeping():
                    self.engine.set_state(PetState.SLEEP)
                else:
                    self.engine.set_state(PetState.IDLE)
            return
        
        # 缓动函数：ease-out
        t = self._anim_progress
        ease = 1 - (1 - t) ** 3
        
        # 计算当前位置
        current_x = int(self._anim_start[0] + (self._anim_target[0] - self._anim_start[0]) * ease)
        current_y = int(self._anim_start[1] + (self._anim_target[1] - self._anim_start[1]) * ease)
        
        self.move(current_x, current_y)
        self._update_bubble_position()  # 更新对话框位置
    
    def _on_exit(self):
        """退出程序 - 强制终止进程"""
        self._update_timer.stop()
        self.animation_player.stop_all_timers()
        self._action_timer.stop()
        self._walk_timer.stop()
        self.close()
        # 使用 os._exit 强制终止，不清理 Python 对象，确保进程立即结束
        import os
        os._exit(0)
    
    def closeEvent(self, event):
        """关闭事件"""
        self._update_timer.stop()
        self.animation_player.stop_all_timers()
        event.accept()


# ============ 模块自测试 ============
if __name__ == "__main__":
    print("=" * 40)
    print("模块测试: ui/main_window.py")
    print("=" * 40)
    print("\n[说明] 此模块需要PySide6运行")
    print("[说明] 将启动一个可交互的测试窗口")
    print("[说明] 操作指南:")
    print("  - 左键按住: 拖拽宠物")
    print("  - 右键点击: 打开菜单(喂食/抚摸/退出)")
    print("  - 观察: 饱食度每秒下降，饿了会变红")
    print("\n" + "=" * 40)
    
    # 创建应用
    app = QApplication(sys.argv)
    
    # 创建引擎
    engine = PetEngine()
    
    # 创建窗口
    window = PetMainWindow(engine)
    window.show()
    
    # 连接信号用于调试输出
    def on_stats_change(stats):
        print(f"[状态更新] 饱食度: {stats.hunger:.1f}, 心情: {stats.happiness:.1f}")
    
    window.signals.stats_updated.connect(on_stats_change)
    
    print("\n窗口已启动，按Ctrl+C或右键菜单退出\n")
    
    sys.exit(app.exec())
