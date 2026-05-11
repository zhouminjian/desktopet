from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QPainter, QPixmap, QColor, QBrush, QPen, QFont
import os
import random

from core.engine import PetEngine, PetState
from core.config import PetConfig
from core.state_resolver import resolve_animation_state


class AnimationPlayerSignals(QObject):
    """动画播放器信号类"""
    animation_frame_updated = Signal()  # 动画帧更新信号，通知UI重绘


class AnimationPlayer(QObject):
    """
    动画播放器
    职责：管理动画帧、播放、循环、暂停等
    """

    def __init__(self, engine: PetEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.signals = AnimationPlayerSignals()

        # 动画帧率
        self.FPS = PetConfig.FPS
        self.FRAME_INTERVAL = PetConfig.FRAME_INTERVAL

        # 动画相关
        self._current_frame = 0
        self._frame_counter = 0  # 帧计数器，控制动画速度
        self._animation_frames: dict[str, list[QPixmap]] = {}  # 各状态的多帧动画
        self._current_animation = "idle"  # 当前播放的动画名称
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._on_animation_frame)

        # 吸附动画相关
        self._walk_timer = QTimer(self) # TODO: move walk animation logic out of animation player
        # self._walk_timer.timeout.connect(self._on_snap_step) # This connection will be made in main_window

        # 动画循环间隔控制
        self._anim_cycle_count = 0  # 当前循环次数
        self._anim_cycle_pause = False  # 是否处于暂停状态
        self._anim_pause_timer = QTimer(self)  # 暂停定时器
        self._anim_pause_timer.timeout.connect(self._on_anim_pause_end)
        self._anim_pause_timer.setSingleShot(True)

        # 强制动画状态（用于拖拽后的一次性动作）
        self._force_animation = None  # 强制播放的动画名称
        self._force_anim_cycles = 0  # 强制动画已播放循环数
        self._force_anim_wait_time = 0  # 强制动画结束后等待时间(秒)

        # 鼠标悬停/交互动画状态
        self._hover_animation = None  # 悬停触发的动画
        self._hover_timer = QTimer(self)  # 悬停动画定时器
        self._hover_timer.timeout.connect(self._on_hover_anim_end)
        self._hover_timer.setSingleShot(True)
        self._is_hovering = False  # 鼠标是否悬停 (This should probably be in InteractionController, but for now keep it here for hover anim)

        # 眨眼状态
        self._is_blinking = False

        # Tired 动画：播完一次后保持，不循环
        self._tired_hold = False

        # Lie 动画循环播放：正序播完后倒序播回第一帧，随机30-60秒再次播放
        self._lie_hold = False
        self._lie_reverse = False  # 是否正在倒序播放
        self._lie_repeat_timer = QTimer(self)
        self._lie_repeat_timer.setSingleShot(True)
        self._lie_repeat_timer.timeout.connect(self._on_lie_repeat)

        # Walk 循环完成回调（由 main_window 设置）
        self.on_walk_cycle_complete = None
        
        # 图片资源缓存
        self._pixmaps: dict[str, QPixmap] = {}
        self._has_resources = False
        self._use_placeholder = True

        self.load_resources()
        self._animation_timer.start(self.FRAME_INTERVAL)
    
    def load_resources(self):
        """加载图片资源 - 自动扫描子目录作为状态"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        assets_dir = os.path.join(base_dir, "assets", "animations")
        
        self._has_resources = os.path.exists(assets_dir)
        self._use_placeholder = True  # 默认使用占位图
        
        if self._has_resources:
            loaded_any = False
            for item in os.listdir(assets_dir):
                state_path = os.path.join(assets_dir, item)
                if os.path.isdir(state_path) and not item.startswith('.'):
                    state = item
                    # 加载 PNG 帧
                    frames = self._load_animation_frames_from_dir(state_path)
                    if frames:
                        if len(frames) == 1:
                            self._pixmaps[state] = frames[0]
                        else:
                            self._animation_frames[state] = frames
                        loaded_any = True
                        print(f"[资源] 加载状态 '{state}': {len(frames)} 帧")
            
            if "sleep" not in self._pixmaps and "sleep" not in self._animation_frames:
                if "lie" in self._pixmaps:
                    self._pixmaps["sleep"] = self._pixmaps["lie"]
                    print("[资源] 使用 lie 作为 sleep 备选")
                elif "lie" in self._animation_frames:
                    self._animation_frames["sleep"] = self._animation_frames["lie"]
                    print("[资源] 使用 lie 动画作为 sleep 备选")
            
            if "idle" not in self._pixmaps and "idle" not in self._animation_frames:
                if "tired" in self._pixmaps:
                    self._pixmaps["idle"] = self._pixmaps["tired"]
                    print("[资源] 使用 tired 作为 idle 备选")
                elif "tired" in self._animation_frames:
                    self._animation_frames["idle"] = self._animation_frames["tired"]
                    print("[资源] 使用 tired 动画作为 idle 备选")
            
            if "walk" not in self._pixmaps and "walk" not in self._animation_frames:
                self._create_walk_placeholder()
                print("[资源] 创建 walk 占位动画")
            
            if loaded_any:
                self._use_placeholder = False
        
        if self._use_placeholder:
            print("[资源] 未找到图片资源，使用占位图")
            self._create_placeholder_pixmaps()
    
    def _load_animation_frames(self, assets_dir: str, state_name: str) -> list:
        """加载指定状态的动画帧 (兼容旧方法)"""
        frames = []
        frame_index = 0
        while True:
            img_path = os.path.join(assets_dir, f"{state_name}_{frame_index}.png")
            if os.path.exists(img_path):
                pixmap = QPixmap(img_path)
                if not pixmap.isNull():
                    frames.append(pixmap)
                frame_index += 1
            else:
                break
        return frames
    
    def _load_animation_frames_from_dir(self, state_dir: str) -> list:
        """从状态目录加载所有图片帧，统一缩放到窗口尺寸"""
        frames = []
        target_w, target_h = PetConfig.WINDOW_WIDTH, PetConfig.WINDOW_HEIGHT
        png_files = sorted([f for f in os.listdir(state_dir) if f.endswith('.png')])
        for filename in png_files:
            img_path = os.path.join(state_dir, filename)
            pixmap = QPixmap(img_path)
            if not pixmap.isNull():
                if pixmap.width() != target_w or pixmap.height() != target_h:
                    pixmap = pixmap.scaled(
                        target_w, target_h,
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                frames.append(pixmap)
            else:
                print(f"[ERROR] Failed to load image: {img_path} (isNull=True)")
        return frames

    def _create_walk_placeholder(self):
        """创建行走状态的占位动画（左右摇摆效果）"""
        color = QColor(150, 200, 255)  # 蓝色
        frames = []
        
        # Assume a default window size for placeholder if not set by main window
        win_width = PetConfig.WINDOW_WIDTH
        win_height = PetConfig.WINDOW_HEIGHT

        for offset_x in [-3, 3]:
            pixmap = QPixmap(win_width, win_height)
            pixmap.fill(Qt.transparent)
            
            painter = QPainter(pixmap)
            center_x = 64 + offset_x
            center_y = 64
            
            size = PetConfig.PLACEHOLDER_PET_BODY_SIZE
            x = center_x - size // 2
            y = center_y - size // 2
            
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor(80, 80, 80), 2))
            painter.drawEllipse(x, y, size, size)
            
            eye_offset_y = 0
            painter.setPen(QPen(Qt.black, 3))
            painter.drawEllipse(35 + offset_x, 45 - eye_offset_y, PetConfig.PLACEHOLDER_PET_EYE_SIZE, PetConfig.PLACEHOLDER_PET_EYE_SIZE)
            painter.drawEllipse(78 + offset_x, 45 - eye_offset_y, PetConfig.PLACEHOLDER_PET_EYE_SIZE, PetConfig.PLACEHOLDER_PET_EYE_SIZE)
            painter.drawArc(PetConfig.PLACEHOLDER_PET_MOUTH_ARC[0] + offset_x, PetConfig.PLACEHOLDER_PET_MOUTH_ARC[1] - eye_offset_y, PetConfig.PLACEHOLDER_PET_MOUTH_ARC[2], PetConfig.PLACEHOLDER_PET_MOUTH_ARC[3], PetConfig.PLACEHOLDER_PET_MOUTH_ARC[4], PetConfig.PLACEHOLDER_PET_MOUTH_ARC[5])
            
            painter.setPen(QPen(Qt.white, 2))
            painter.drawText(10, 100, PetConfig.PLACEHOLDER_PET_SIZE, 20, Qt.AlignCenter, "walk")
            
            painter.end()
            frames.append(pixmap)
        
        self._animation_frames["walk"] = frames
    
    def _create_eating_placeholder(self):
        """创建进食状态的占位图"""
        color = QColor(150, 255, 150)  # 绿色
        win_width = PetConfig.WINDOW_WIDTH
        win_height = PetConfig.WINDOW_HEIGHT
        pixmap = QPixmap(win_width, win_height)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        center_x, center_y = 64, 64
        
        size = PetConfig.PLACEHOLDER_PET_BODY_SIZE
        x = center_x - size // 2
        y = center_y - size // 2
        
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor(80, 80, 80), 2))
        painter.drawEllipse(x, y, size, size)
        
        painter.setPen(QPen(Qt.black, 3))
        painter.drawEllipse(35, 45, PetConfig.PLACEHOLDER_PET_EYE_SIZE, PetConfig.PLACEHOLDER_PET_EYE_SIZE)
        painter.drawEllipse(78, 45, PetConfig.PLACEHOLDER_PET_EYE_SIZE, PetConfig.PLACEHOLDER_PET_EYE_SIZE)
        
        painter.drawEllipse(50, 70, 28, 20)
        
        painter.setBrush(QBrush(QColor(200, 100, 50)))
        painter.drawEllipse(55, 85, 18, 12)
        
        painter.setPen(QPen(Qt.white, 2))
        painter.drawText(10, 100, PetConfig.PLACEHOLDER_PET_SIZE, 20, Qt.AlignCenter, "eating")
        
        painter.end()
        self._pixmaps["eating"] = pixmap
    
    def _create_placeholder_pixmaps(self):
        """创建占位图片序列帧 - 包含呼吸感动画"""
        colors = {
            "idle": QColor(255, 200, 150),
            "walk": QColor(150, 200, 255),
            "sleep": QColor(200, 150, 255),
            "eating": QColor(150, 255, 150),
            "hungry": QColor(255, 100, 100),
        }
        
        for state_name, color in colors.items():
            self._pixmaps[state_name] = self._create_single_frame(state_name, color, 0)
        
        self._animation_frames["idle"] = [
            self._create_single_frame("idle", colors["idle"], 0),
            self._create_single_frame("idle", colors["idle"], 1),
            self._create_single_frame("idle", colors["idle"], 2),
            self._create_single_frame("idle", colors["idle"], 1),
        ]
        
        self._animation_frames["walk"] = [
            self._create_single_frame("walk", colors["walk"], 0, offset_x=-2),
            self._create_single_frame("walk", colors["walk"], 0, offset_x=2),
        ]
    
    def _create_single_frame(self, state_name: str, color: QColor, breath_phase: int = 0, offset_x: int = 0) -> QPixmap:
        """创建单帧图片 - 支持呼吸效果和偏移"""
        win_width = PetConfig.WINDOW_WIDTH
        win_height = PetConfig.WINDOW_HEIGHT
        pixmap = QPixmap(win_width, win_height)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        
        size_offsets = {0: 0, 1: 3, 2: 6}
        size_offset = size_offsets.get(breath_phase, 0)
        
        center_x = 64 + offset_x
        center_y = 64 - size_offset // 2
        
        base_size = PetConfig.PLACEHOLDER_PET_SIZE
        size = base_size + size_offset
        x = center_x - size // 2
        y = center_y - size // 2
        
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor(80, 80, 80), 2))
        painter.drawEllipse(x, y, size, size)
        
        eye_offset_y = size_offset // 3
        painter.setPen(QPen(Qt.black, 3))
        painter.drawEllipse(35 + offset_x, 45 - eye_offset_y, PetConfig.PLACEHOLDER_PET_EYE_SIZE, PetConfig.PLACEHOLDER_PET_EYE_SIZE)
        painter.drawEllipse(78 + offset_x, 45 - eye_offset_y, PetConfig.PLACEHOLDER_PET_EYE_SIZE, PetConfig.PLACEHOLDER_PET_EYE_SIZE)
        
        if state_name == "sleep":
            painter.drawLine(35 + offset_x, 52 - eye_offset_y, 50 + offset_x, 52 - eye_offset_y)
            painter.drawLine(78 + offset_x, 52 - eye_offset_y, 93 + offset_x, 52 - eye_offset_y)
            painter.drawArc(45 + offset_x, 65 - eye_offset_y, 38, 25, 0, 180 * 16)
        elif state_name == "hungry":
            painter.drawArc(45 + offset_x, 75 - eye_offset_y, 38, 20, 0, -180 * 16)
        else:
            painter.drawArc(45 + offset_x, 65 - eye_offset_y, 38, 25, 0, 180 * 16)
        
        painter.setFont(QFont("Microsoft YaHei", 10))
        painter.setPen(QPen(Qt.white, 2))
        painter.drawText(10, 100, PetConfig.PLACEHOLDER_PET_SIZE, 20, Qt.AlignCenter, state_name)
        
        painter.end()
        return pixmap

    def _on_animation_frame(self):
        """动画帧更新 - 序列帧系统，支持循环间隔"""
        if self._anim_cycle_pause:
            return

        self._frame_counter += 1

        frames = self._animation_frames.get(self._current_animation, [])
        if not frames:
            frames = [self._pixmaps.get(self._current_animation, QPixmap())]

        if frames and len(frames) > 1:
            if self.engine.state == PetState.SLEEP:
                frame_interval = PetConfig.ANIM_FRAME_INTERVAL_SLEEP
            elif len(frames) > PetConfig.ANIM_VIDEO_FRAME_THRESHOLD:
                frame_interval = PetConfig.ANIM_FRAME_INTERVAL_VIDEO  # 帧数多的动画用快速播放
            else:
                frame_interval = PetConfig.ANIM_FRAME_INTERVAL_DEFAULT

            if self._frame_counter % frame_interval == 0:
                # lie 倒序播放：帧递减，到第0帧时进入保持
                if self._lie_reverse:
                    self._current_frame -= 1
                    if self._current_frame <= 0:
                        self._current_frame = 0
                        self._start_lie_hold()
                    else:
                        self.signals.animation_frame_updated.emit()
                    return

                prev_frame = self._current_frame
                self._current_frame = (self._current_frame + 1) % len(frames)

                if self._current_frame == 0 and prev_frame == len(frames) - 1:
                    if self.engine.state != PetState.SLEEP:
                        self._on_anim_cycle_complete()
                    else:
                        self.signals.animation_frame_updated.emit()
                else:
                    self.signals.animation_frame_updated.emit()
        else:
            if self._frame_counter % PetConfig.ANIM_SINGLE_FRAME_REDRAW == 0:
                self.signals.animation_frame_updated.emit()

    def _on_hover_anim_end(self):
        """悬停动画结束 - 恢复idle（仅当鼠标已离开时）"""
        if not self._is_hovering:
            print("[悬停] 卖萌动画结束，恢复idle")
            self._hover_animation = None
            self._current_frame = 0
            self.signals.animation_frame_updated.emit()

    def _start_lie_reverse(self):
        """lie 正序播完，开始倒序播放"""
        self._lie_reverse = True
        frames = self._animation_frames.get("lie", [])
        if frames:
            self._current_frame = len(frames) - 1  # 从最后一帧开始倒播
        self._force_anim_cycles = 0
        self._anim_cycle_count = 0
        print(f"[动画] lie 正序播完，开始倒序播放")

    def _start_lie_hold(self):
        """lie 倒序播完，保持第一帧，随机间隔后再次播放"""
        self._lie_hold = True
        self._lie_reverse = False
        self._current_frame = 0
        self._anim_cycle_pause = True
        self._force_anim_cycles = 0
        self._anim_cycle_count = 0
        repeat_ms = random.randint(PetConfig.LIE_REPEAT_MIN_MS, PetConfig.LIE_REPEAT_MAX_MS)
        print(f"[动画] lie 倒序播完，保持第一帧，{repeat_ms / 1000:.0f}秒后再次播放")
        self._lie_repeat_timer.start(repeat_ms)

    def _on_lie_repeat(self):
        """lie 重复播放：清除保持状态，重置到第一帧并继续正序"""
        self._lie_hold = False
        self._lie_reverse = False
        self._current_frame = 0
        self._force_anim_cycles = 0
        self._anim_cycle_count = 0
        self._anim_cycle_pause = False
        self.signals.animation_frame_updated.emit()

    def _on_anim_cycle_complete(self):
        """完成一个动画循环 - 处理强制动画或暂停"""
        if self._force_animation:
            self._force_anim_cycles += 1
            print(f"[动画] 强制动画 '{self._force_animation}' 完成循环 #{self._force_anim_cycles}")

            # lie 动画：正序播完后进入倒序播放
            if self._force_animation == "lie" and self._force_anim_cycles >= 1:
                self._start_lie_reverse()
                return

            # tired 动画：播完一次后保持，不循环，不恢复 idle
            if self._force_animation == "tired" and self._force_anim_cycles >= 1:
                self._tired_hold = True
                self._anim_cycle_pause = True
                self._force_anim_cycles = 0
                self._anim_cycle_count = 0
                print("[动画] tired 播放完毕，保持状态")
                return

            if self._force_anim_cycles >= 1 and self._force_anim_wait_time > 0:
                print(f"[动画] 强制动画进入等待期 {self._force_anim_wait_time}秒")
                self._anim_cycle_pause = True
                self._anim_pause_timer.start(self._force_anim_wait_time * 1000)
                return
            elif self._force_anim_cycles >= 1:
                self._force_animation = None
                self._force_anim_cycles = 0
                self._current_frame = 0
                print("[动画] 强制动画结束，恢复正常状态")
                self.signals.animation_frame_updated.emit()
                return

        # walk 动画不暂停，由外部回调控制结束
        if self._current_animation == "walk":
            self.signals.animation_frame_updated.emit()
            if self.on_walk_cycle_complete:
                self.on_walk_cycle_complete()
            return

        self._anim_cycle_count += 1
        if self._anim_cycle_count <= 1:
            self.signals.animation_frame_updated.emit()
            return
        self._anim_cycle_pause = True
        print(f"[动画] 完成循环 #{self._anim_cycle_count}，暂停{PetConfig.ANIM_CYCLE_PAUSE_DEFAULT / 1000}秒...")
        self._anim_pause_timer.start(PetConfig.ANIM_CYCLE_PAUSE_DEFAULT)

    def _on_anim_pause_end(self):
        """暂停结束 - 继续动画或结束强制动画"""
        self._anim_cycle_pause = False

        # lie 保持结束，重新播放
        if self._lie_hold:
            self._on_lie_repeat()
            return

        if self._force_animation and self._force_anim_cycles >= 1:
            print("[动画] 强制动画等待期结束，恢复正常状态")
            self._force_animation = None
            self._force_anim_cycles = 0
            self._force_anim_wait_time = 0
            self._current_frame = 0
            self._anim_cycle_count = 0

            # 如果鼠标仍在悬浮，恢复卖萌动画
            if self._is_hovering:
                print("[动画] 鼠标仍悬浮，恢复卖萌动画")
                self._hover_animation = "maimeng"
                self._current_frame = 0

            self.signals.animation_frame_updated.emit()
            return
        
        print(f"[动画] 暂停结束，继续播放")
        self.signals.animation_frame_updated.emit()

    def get_current_pixmap(self, pet_state: PetState, hunger_level: float, is_sleeping: bool) -> QPixmap:
        """获取当前帧的图片 - 支持序列帧动画"""
        state_name = resolve_animation_state(
            pet_state, hunger_level, is_sleeping,
            self._force_animation, self._hover_animation,
        )
        
        if self._current_animation != state_name:
            self._current_animation = state_name
            self._current_frame = 0
            self._anim_cycle_count = 0
            self._anim_cycle_pause = False
            self._lie_hold = False
            self._lie_reverse = False
            self._lie_repeat_timer.stop()
            self._tired_hold = False
        
        frames = self._animation_frames.get(state_name, [])
        if frames and len(frames) > 0:
            return frames[self._current_frame % len(frames)]
        
        pixmap = self._pixmaps.get(state_name)
        if pixmap:
            return pixmap

        idle_frames = self._animation_frames.get("idle", [])
        if idle_frames:
            return idle_frames[self._current_frame % len(idle_frames)]

        return self._pixmaps.get("idle")

    def start_force_animation(self, anim_name: str, wait_time: int = 1):
        """启动强制动画（播放1轮+等待后恢复idle）"""
        # lie 动画已在播放或保持中时，不重复触发（避免每秒重置导致永远播不完）
        if anim_name == "lie" and (self._force_animation == "lie" or self._lie_hold):
            return
        # tired 动画已在播放或保持中时，不重复触发
        if anim_name == "tired" and (self._force_animation == "tired" or self._tired_hold):
            return
        if anim_name in self._pixmaps or anim_name in self._animation_frames:
            self._hover_timer.stop()
            self._hover_animation = None
            # 新强制动画开始时，清除 lie/tired 所有状态
            self._lie_hold = False
            self._lie_reverse = False
            self._lie_repeat_timer.stop()
            self._tired_hold = False
            self._tired_hold = False
            self._anim_cycle_pause = False
            self._force_animation = anim_name
            self._force_anim_cycles = 0
            self._force_anim_wait_time = PetConfig.INTERACTION_COOLDOWN_TIME
            self._current_frame = 0
            print(f"[动画] 强制播放 '{anim_name}'（1轮+{wait_time}秒冷却）")
            self.signals.animation_frame_updated.emit()
    
    def start_hover_animation(self):
        """启动悬停动画"""
        # This logic should be moved to InteractionController, but for now, it's a placeholder
        # The conditions for starting hover animation should come from InteractionController
        # For now, just trigger the animation if resources exist.
        cute_resource = None
        if "maimeng" in self._pixmaps or "maimeng" in self._animation_frames:
            cute_resource = "maimeng"
        elif "play_cute" in self._pixmaps or "play_cute" in self._animation_frames:
            cute_resource = "play_cute"
        
        if cute_resource:
            self._is_hovering = True
            self._hover_animation = cute_resource
            self._current_frame = 0
            self._hover_timer.stop()
            self.signals.animation_frame_updated.emit()

    def end_hover_animation(self):
        """结束悬停动画"""
        self._is_hovering = False
        self._on_hover_anim_end() # Call internal handler

    def set_is_hovering(self, hovering: bool):
        """设置鼠标是否悬停状态"""
        self._is_hovering = hovering

    def set_is_blinking(self, blinking: bool):
        """设置眨眼状态"""
        self._is_blinking = blinking
        self.signals.animation_frame_updated.emit()

    def set_is_dragging(self, dragging: bool):
        """设置是否正在拖拽状态"""
        self._is_dragging = dragging

    def get_is_blinking(self) -> bool:
        """获取眨眼状态"""
        return self._is_blinking

    def stop_all_timers(self):
        """停止所有内部定时器"""
        self._animation_timer.stop()
        self._walk_timer.stop() # This timer should eventually be moved out
        self._anim_pause_timer.stop()
        self._hover_timer.stop()
        self._lie_repeat_timer.stop()
