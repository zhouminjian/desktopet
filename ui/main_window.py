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


# 引入核心引擎
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.engine import PetEngine, PetState, PetStats


class PetSignals(QObject):
    """信号类 - 用于前后端通信，保持变量传递一致"""
    stats_updated = Signal(PetStats)  # 属性更新信号
    state_changed = Signal(PetState)  # 状态变化信号
    feed_requested = Signal()  # 喂食请求信号
    pet_requested = Signal()  # 抚摸请求信号
    hunger_changed = Signal(float)  # 饱食度变化信号 (新值)
    exp_gained = Signal(int)  # 获得经验信号 (数量)


class PetMainWindow(QMainWindow):
    """
    宠物主窗体
    特性：透明背景、置顶显示、无边框、鼠标穿透拖拽
    """
    
    # 窗口尺寸常量 - 默认尺寸，会根据实际图片调整
    WINDOW_WIDTH = 128
    WINDOW_HEIGHT = 128
    MAX_WINDOW_SIZE = 128  # 最大窗口尺寸限制（保持128x128）
    
    # 动画帧率
    FPS = 24
    FRAME_INTERVAL = 1000 // FPS  # 约42ms
    
    def __init__(self, engine: PetEngine, parent=None):
        """
        初始化主窗体
        
        Args:
            engine: 宠物引擎实例 (Model层)
        """
        super().__init__(parent)
        
        self.engine = engine
        self.signals = PetSignals()
        
        # 拖拽相关变量
        self._dragging = False
        self._drag_offset = QPoint()
        
        # 3D模式支持
        self._3d_mode = False
        self._3d_viewer: Pet3DViewer | None = None
        self._3d_model_path: str | None = None
        
        # 动画相关 - 序列帧系统
        self._current_frame = 0
        self._frame_counter = 0  # 帧计数器，控制动画速度
        self._animation_frames: dict[str, list[QPixmap]] = {}  # 各状态的多帧动画
        self._current_animation = "idle"  # 当前播放的动画名称
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._on_animation_frame)
        
        # 吸附动画相关
        self._walk_timer = QTimer(self)
        self._walk_timer.timeout.connect(self._on_snap_step)  # 改为吸附动画步进
        self._walk_pause_timer = QTimer(self)  # 不再使用，保留兼容
        
        # 状态更新定时器 (每秒更新一次属性)
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._on_update)
        self._update_timer.start(1000)  # 1秒间隔
        
        # 自动动作定时器 (空闲时随机执行动作)
        self._action_timer = QTimer(self)
        self._action_timer.timeout.connect(self._on_auto_action)
        self._action_timer.start(15000)  # 每15秒尝试一次
        
        # 动作间隔范围 - 使用正态分布生成更自然的随机间隔
        self._action_interval_mean = 15000  # 平均15秒
        self._action_interval_std = 5000    # 标准差5秒（大部分在10-20秒之间）
        self._action_interval_min = 3000    # 最少3秒
        self._action_interval_max = 45000   # 最多45秒
        
        # 动作权重配置（概率 = 权重/总权重）
        self._action_weights = {
            self.PetAction.IDLE_BLINK: 85,      # 85% - 发呆眨眼
            # self.PetAction.WALK_AROUND: 0,    # 禁用
            # self.PetAction.PLAY_CUTE: 0,      # 禁用（悬停时已自动触发maimeng）
            self.PetAction.SNAP_TO_EDGE: 15,    # 15% - 吸附到边缘
            # self.PetAction.JUMP: 0,           # 禁用
            # self.PetAction.ROLL: 0,            # 禁用
        }
        
        # 空闲动画计数器 - 长时间不动时触发小动画
        self._idle_time = 0
        self._last_action_time = 0
        self._last_interaction_time = time.time()  # 上次互动时间（初始化为当前时间）
        self._is_sleeping = False  # 是否在睡觉
        self._is_blinking = False
        
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
        self._is_hovering = False  # 鼠标是否悬停
        
        # 图片资源缓存
        self._pixmaps: dict[str, QPixmap] = {}
        
        # 对话框引用（用于跟随移动）
        self._bubble = None
        self._bubble_offset = QPoint(0, -70)  # 对话框默认偏移
        
        # 初始化UI
        self._setup_window()
        self._connect_signals()
        self._load_resources()
        self._init_3d_viewer()
        
        # 启动动画循环
        self._animation_timer.start(self.FRAME_INTERVAL)
    
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
            screen.width() - self.WINDOW_WIDTH - 20,
            screen.height() - self.WINDOW_HEIGHT - 80
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
    
    def _load_resources(self):
        """加载图片资源 - 自动扫描子目录作为状态"""
        # 获取资源目录
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        assets_dir = os.path.join(base_dir, "assets", "animations")
        
        # 如果没有资源目录，使用占位色块
        self._has_resources = os.path.exists(assets_dir)
        self._use_placeholder = True  # 默认使用占位图
        
        if self._has_resources:
            loaded_any = False
            
            # 自动扫描所有子目录，目录名作为状态名
            for item in os.listdir(assets_dir):
                state_path = os.path.join(assets_dir, item)
                if os.path.isdir(state_path) and not item.startswith('.'):
                    # 子目录作为状态名
                    state = item
                    frames = self._load_animation_frames_from_dir(state_path)
                    if frames:
                        if len(frames) == 1:
                            # 单帧，存入 _pixmaps
                            self._pixmaps[state] = frames[0]
                        else:
                            # 多帧动画，存入 _animation_frames
                            self._animation_frames[state] = frames
                        loaded_any = True
                        print(f"[资源] 加载状态 '{state}': {len(frames)} 帧")
            
            # 备选处理：lie -> sleep (躺下就是睡觉)
            if "sleep" not in self._pixmaps and "sleep" not in self._animation_frames:
                if "lie" in self._pixmaps:
                    self._pixmaps["sleep"] = self._pixmaps["lie"]
                    print("[资源] 使用 lie 作为 sleep 备选")
                elif "lie" in self._animation_frames:
                    self._animation_frames["sleep"] = self._animation_frames["lie"]
                    print("[资源] 使用 lie 动画作为 sleep 备选")
            
            # 备选处理：tired -> idle (累了就是发呆)
            if "idle" not in self._pixmaps and "idle" not in self._animation_frames:
                if "tired" in self._pixmaps:
                    self._pixmaps["idle"] = self._pixmaps["tired"]
                    print("[资源] 使用 tired 作为 idle 备选")
                elif "tired" in self._animation_frames:
                    self._animation_frames["idle"] = self._animation_frames["tired"]
                    print("[资源] 使用 tired 动画作为 idle 备选")
            
            # 如果没有 walk，创建占位动画
            if "walk" not in self._pixmaps and "walk" not in self._animation_frames:
                self._create_walk_placeholder()
                print("[资源] 创建 walk 占位动画")
            
            if loaded_any:
                self._use_placeholder = False
                # 根据加载的图片调整窗口大小
                self._adjust_window_size()
        
        # 如果完全没有资源，创建全部占位图
        if self._use_placeholder:
            print("[资源] 未找到图片资源，使用占位图")
            self._create_placeholder_pixmaps()
    
    def _init_3d_viewer(self):
        """初始化3D查看器（已归档到3D/目录，暂不启用）"""
        # self._3d_viewer = Pet3DViewer(self)
        # self._3d_viewer.setGeometry(0, 0, self.WINDOW_WIDTH, self.WINDOW_HEIGHT)
        # self._3d_viewer.hide()
        # self._3d_viewer.clicked.connect(self._on_3d_clicked)
        # self._3d_viewer.loaded.connect(self._on_3d_model_loaded)
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
        self._animation_timer.start(self.FRAME_INTERVAL)
        self.update()  # 重绘2D层
        print("[2D] 回到2D模式")
    
    def _on_3d_clicked(self):
        """3D模型被点击（已归档）"""
        pass
    
    def _on_3d_model_loaded(self, success: bool, message: str):
        """3D模型加载完成回调（已归档）"""
        pass
    
    def _load_animation_frames(self, assets_dir: str, state_name: str) -> list:
        """
        加载指定状态的动画帧 (兼容旧方法)
        支持格式: state_0.png, state_1.png, ...
        """
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
        """
        从状态目录加载所有图片帧
        加载目录下所有 .png 文件，按文件名排序
        
        Args:
            state_dir: 状态目录路径 (如 assets/animations/idle/)
        
        Returns:
            加载成功的 QPixmap 列表
        """
        frames = []
        
        # 获取所有png文件并排序
        png_files = sorted([f for f in os.listdir(state_dir) if f.endswith('.png')])
        
        for filename in png_files:
            img_path = os.path.join(state_dir, filename)
            pixmap = QPixmap(img_path)
            if not pixmap.isNull():
                frames.append(pixmap)
        
        return frames
    
    def _adjust_window_size(self):
        """根据加载的图片调整窗口大小"""
        # 收集所有加载的图片尺寸
        all_pixmaps = []
        for frames in self._animation_frames.values():
            all_pixmaps.extend(frames)
        for pixmap in self._pixmaps.values():
            all_pixmaps.append(pixmap)
        
        if not all_pixmaps:
            return
        
        # 计算最常见的尺寸（取第一个作为参考）
        sample = all_pixmaps[0]
        img_width = sample.width()
        img_height = sample.height()
        
        # 如果图片大于最大限制，按比例缩小
        max_size = self.MAX_WINDOW_SIZE
        if img_width > max_size or img_height > max_size:
            scale = min(max_size / img_width, max_size / img_height)
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)
        else:
            new_width = img_width
            new_height = img_height
        
        # 更新窗口尺寸
        if new_width != self.WINDOW_WIDTH or new_height != self.WINDOW_HEIGHT:
            print(f"[资源] 调整窗口大小: {self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT} -> {new_width}x{new_height} (原图: {img_width}x{img_height})")
            self.WINDOW_WIDTH = new_width
            self.WINDOW_HEIGHT = new_height
            self.setFixedSize(self.WINDOW_WIDTH, self.WINDOW_HEIGHT)
    
    def _create_walk_placeholder(self):
        """创建行走状态的占位动画（左右摇摆效果）"""
        from PySide6.QtGui import QPainter, QBrush, QPen
        
        color = QColor(150, 200, 255)  # 蓝色
        frames = []
        
        for offset_x in [-3, 3]:  # 左右摇摆
            pixmap = QPixmap(self.WINDOW_WIDTH, self.WINDOW_HEIGHT)
            pixmap.fill(Qt.transparent)
            
            painter = QPainter(pixmap)
            center_x = 64 + offset_x
            center_y = 64
            
            # 绘制圆形主体
            size = 100
            x = center_x - size // 2
            y = center_y - size // 2
            
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor(80, 80, 80), 2))
            painter.drawEllipse(x, y, size, size)
            
            # 绘制简单表情
            eye_offset_y = 0
            painter.setPen(QPen(Qt.black, 3))
            painter.drawEllipse(35 + offset_x, 45 - eye_offset_y, 15, 15)  # 左眼
            painter.drawEllipse(78 + offset_x, 45 - eye_offset_y, 15, 15)  # 右眼
            painter.drawArc(45 + offset_x, 65 - eye_offset_y, 38, 25, 0, 180 * 16)  # 微笑
            
            # 绘制行走状态标识
            painter.setPen(QPen(Qt.white, 2))
            painter.drawText(10, 100, 108, 20, Qt.AlignCenter, "walk")
            
            painter.end()
            frames.append(pixmap)
        
        self._animation_frames["walk"] = frames
    
    def _create_eating_placeholder(self):
        """创建进食状态的占位图"""
        from PySide6.QtGui import QPainter, QBrush, QPen
        
        color = QColor(150, 255, 150)  # 绿色
        pixmap = QPixmap(self.WINDOW_WIDTH, self.WINDOW_HEIGHT)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        center_x, center_y = 64, 64
        
        # 绘制圆形主体
        size = 100
        x = center_x - size // 2
        y = center_y - size // 2
        
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor(80, 80, 80), 2))
        painter.drawEllipse(x, y, size, size)
        
        # 绘制开心表情（眨眼）
        painter.setPen(QPen(Qt.black, 3))
        painter.drawEllipse(35, 45, 15, 15)  # 左眼
        painter.drawEllipse(78, 45, 15, 15)  # 右眼
        
        # 大嘴巴（吃东西）
        painter.drawEllipse(50, 70, 28, 20)  # 吃东西的嘴
        
        # 绘制食物
        painter.setBrush(QBrush(QColor(200, 100, 50)))  # 棕色食物
        painter.drawEllipse(55, 85, 18, 12)
        
        # 状态文字
        painter.setPen(QPen(Qt.white, 2))
        painter.drawText(10, 100, 108, 20, Qt.AlignCenter, "eating")
        
        painter.end()
        self._pixmaps["eating"] = pixmap
    
    def _create_placeholder_pixmaps(self):
        """创建占位图片序列帧 - 包含呼吸感动画"""
        colors = {
            "idle": QColor(255, 200, 150),    # 橘色 - 发呆
            "walk": QColor(150, 200, 255),    # 蓝色 - 行走
            "sleep": QColor(200, 150, 255),  # 紫色 - 睡觉
            "eating": QColor(150, 255, 150),  # 绿色 - 进食
            "hungry": QColor(255, 100, 100),  # 红色 - 饿了
        }
        
        # 创建单帧静态图（向后兼容）
        for state_name, color in colors.items():
            self._pixmaps[state_name] = self._create_single_frame(state_name, color, 0)
        
        # 创建idle状态的呼吸动画序列（4帧）
        self._animation_frames["idle"] = [
            self._create_single_frame("idle", colors["idle"], 0),   # 正常
            self._create_single_frame("idle", colors["idle"], 1),   # 稍大（吸气）
            self._create_single_frame("idle", colors["idle"], 2),   # 最大
            self._create_single_frame("idle", colors["idle"], 1),   # 稍大（呼气）
        ]
        
        # 创建walk状态的行走动画序列（2帧，左右摇摆）
        self._animation_frames["walk"] = [
            self._create_single_frame("walk", colors["walk"], 0, offset_x=-2),  # 左倾
            self._create_single_frame("walk", colors["walk"], 0, offset_x=2),   # 右倾
        ]
    
    def _create_single_frame(self, state_name: str, color: QColor, breath_phase: int = 0, offset_x: int = 0) -> QPixmap:
        """创建单帧图片 - 支持呼吸效果和偏移
        
        Args:
            state_name: 状态名称
            color: 主体颜色
            breath_phase: 呼吸相位 (0=正常, 1=稍大, 2=最大)
            offset_x: 水平偏移（用于行走摇摆）
        """
        pixmap = QPixmap(self.WINDOW_WIDTH, self.WINDOW_HEIGHT)
        pixmap.fill(Qt.transparent)
        
        from PySide6.QtGui import QPainter, QBrush, QPen, QFont
        painter = QPainter(pixmap)
        
        # 呼吸效果：根据相位调整大小
        size_offsets = {0: 0, 1: 3, 2: 6}
        size_offset = size_offsets.get(breath_phase, 0)
        
        # 中心坐标 + 行走偏移
        center_x = 64 + offset_x
        center_y = 64 - size_offset // 2  # 呼吸时稍微上下移动
        
        # 绘制圆形主体（带呼吸缩放）
        base_size = 108
        size = base_size + size_offset
        x = center_x - size // 2
        y = center_y - size // 2
        
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor(80, 80, 80), 2))
        painter.drawEllipse(x, y, size, size)
        
        # 绘制简单表情（随呼吸微调位置）
        eye_offset_y = size_offset // 3
        painter.setPen(QPen(Qt.black, 3))
        painter.drawEllipse(35 + offset_x, 45 - eye_offset_y, 15, 15)  # 左眼
        painter.drawEllipse(78 + offset_x, 45 - eye_offset_y, 15, 15)  # 右眼
        
        # 根据状态绘制不同表情
        if state_name == "sleep":
            painter.drawLine(35 + offset_x, 52 - eye_offset_y, 50 + offset_x, 52 - eye_offset_y)
            painter.drawLine(78 + offset_x, 52 - eye_offset_y, 93 + offset_x, 52 - eye_offset_y)
            painter.drawArc(45 + offset_x, 65 - eye_offset_y, 38, 25, 0, 180 * 16)  # 微笑
        elif state_name == "hungry":
            painter.drawArc(45 + offset_x, 75 - eye_offset_y, 38, 20, 0, -180 * 16)  # 哭脸
        else:
            painter.drawArc(45 + offset_x, 65 - eye_offset_y, 38, 25, 0, 180 * 16)  # 微笑
        
        # 绘制状态文字
        painter.setFont(QFont("Microsoft YaHei", 10))
        painter.setPen(QPen(Qt.white, 2))
        painter.drawText(10, 100, 108, 20, Qt.AlignCenter, state_name)
        
        painter.end()
        return pixmap
    
    def _get_current_pixmap(self) -> QPixmap:
        """获取当前帧的图片 - 支持序列帧动画"""
        # 优先级: 强制动画 > 悬停动画 > 引擎状态
        if self._force_animation:
            # 强制动画（如拖拽后的oneeyes）
            state_name = self._force_animation
        elif self._hover_animation:
            # 悬停动画（卖萌）
            state_name = self._hover_animation
        else:
            # 根据引擎状态选择动画
            state_map = {
                PetState.IDLE: "idle",
                PetState.WALK: "walk",
                PetState.SLEEP: "sleep",
                PetState.EATING: "eating",
                PetState.DRAGGING: "idle",  # 拖拽时显示idle
            }
            state_name = state_map.get(self.engine.state, "idle")
        
        # 如果饿了且状态不为eating/sleep，显示饿了表情（阈值35）
        if self.engine.stats.hunger <= 35 and self.engine.state != PetState.EATING and not self._is_sleeping:
            state_name = "hungry"
            # 调试输出（首次切换到hungry时）
            if self._current_animation != "hungry":
                print(f"[动画] 切换到hungry状态 (饱食度:{self.engine.stats.hunger:.0f}), frames={len(self._animation_frames.get('hungry', []))}")
        
        # 更新当前动画名称（用于序列帧）
        if self._current_animation != state_name:
            self._current_animation = state_name
            self._current_frame = 0  # 切换动画时重置帧
        
        # 尝试获取序列帧
        frames = self._animation_frames.get(state_name, [])
        if frames and len(frames) > 0:
            return frames[self._current_frame % len(frames)]
        
        # 回退到单帧图片
        pixmap = self._pixmaps.get(state_name)
        if pixmap:
            return pixmap
        
        # 如果state_name不在_pixmaps中，尝试idle的序列帧
        idle_frames = self._animation_frames.get("idle", [])
        if idle_frames:
            return idle_frames[self._current_frame % len(idle_frames)]
        
        # 最后回退到idle单帧
        return self._pixmaps.get("idle")
    
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
        
        pixmap = self._get_current_pixmap()
        if not pixmap:
            print(f"[绘制] 警告: 无图片可绘制 (_pixmaps={len(self._pixmaps)}, _animation_frames={len(self._animation_frames)})")
            return
        
        if self._paint_count % 60 == 1:
            print(f"[绘制] 绘制图片: {pixmap.width()}x{pixmap.height()}, isNull={pixmap.isNull()}")
        
        # 获取图片和窗口尺寸
        img_width = pixmap.width()
        img_height = pixmap.height()
        win_width = self.width()
        win_height = self.height()
        
        # 计算缩放
        if img_width != win_width or img_height != win_height:
            scaled_pixmap = pixmap.scaled(
                win_width, win_height,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        else:
            scaled_pixmap = pixmap
        
        # 计算绘制位置（居中）
        draw_x = (win_width - scaled_pixmap.width()) // 2
        draw_y = (win_height - scaled_pixmap.height()) // 2
        
        # 应用变换：旋转（翻滚）、缩放（跳跃）、位移
        painter.translate(win_width // 2, win_height // 2)
        
        # 翻滚旋转
        if hasattr(self, '_is_rolling') and self._is_rolling and hasattr(self, '_roll_angle'):
            painter.rotate(self._roll_angle)
        
        # 跳跃时的轻微缩放（跳起时变大，落地时恢复）
        if hasattr(self, '_is_jumping') and self._is_jumping and hasattr(self, '_jump_time'):
            # 跳跃前半段变大，后半段恢复
            jump_progress = min(1.0, self._jump_time / 600)
            if jump_progress < 0.5:
                scale = 1.0 + 0.15 * (jump_progress * 2)  # 最大放大到 1.15
            else:
                scale = 1.0 + 0.15 * ((1 - jump_progress) * 2)  # 逐渐恢复
            painter.scale(scale, scale)
        
        # 卖萌时的歪头效果
        if hasattr(self, '_is_cute') and self._is_cute:
            painter.rotate(15)  # 歪头15度
        
        # 眨眼的轻微缩放（垂直方向压扁）
        if self._is_blinking:
            painter.scale(1.0, 0.85)  # 垂直压扁15%
        
        painter.translate(-win_width // 2, -win_height // 2)
        
        # 绘制图片
        painter.drawPixmap(draw_x, draw_y, scaled_pixmap)
    
    def mousePressEvent(self, event):
        """鼠标按下 - 开始拖拽或显示菜单"""
        if event.button() == Qt.LeftButton:
            # 饥饿状态拒绝互动
            if self.engine.stats.hunger <= 35 and self.engine.state != PetState.EATING:
                self._show_hungry_refuse()
                return
            
            self._update_interaction_time()  # 记录互动
            self._dragging = True
            self._hover_timer.stop()
            self._hover_animation = None
            self._drag_offset = event.pos()
            self._drag_start_window_pos = (self.x(), self.y())
            self.engine.set_state(PetState.DRAGGING)
        elif event.button() == Qt.RightButton:
            self._update_interaction_time()  # 记录互动
            self._show_context_menu(event.pos())
    
    def mouseMoveEvent(self, event):
        """鼠标移动 - 拖拽窗口"""
        if self._dragging:
            new_pos = self.mapToGlobal(event.pos() - self._drag_offset)
            self.move(new_pos)
    
    def mouseReleaseEvent(self, event):
        """鼠标释放 - 区分点击和拖拽"""
        if event.button() == Qt.LeftButton and self._dragging:
            self._dragging = False
            self.engine.set_state(PetState.IDLE)
            
            # 用窗口位置变化判断是否真正拖拽
            window_dx = self.x() - self._drag_start_window_pos[0]
            window_dy = self.y() - self._drag_start_window_pos[1]
            drag_distance = (window_dx ** 2 + window_dy ** 2) ** 0.5
            
            if drag_distance > 10:
                # 拖拽 → 吸附到边缘 + oneeyes
                self.engine.add_activity(int(drag_distance))
                self._start_force_animation("oneeyes", wait_time=1)
                self.perform_action(self.PetAction.SNAP_TO_EDGE)
            else:
                # 纯点击 → 检查点击冷却
                if self._is_click_cooldown():
                    self._show_cooldown_tip()
                else:
                    self._start_force_animation("oneeyes", wait_time=1)
                    self._do_pet()  # 点击增加经验
    
    def enterEvent(self, event):
        """鼠标进入 - 触发maimeng"""
        self._is_hovering = True
        self._update_interaction_time()  # 记录互动
        if not self._dragging:
            self._start_hover_animation()
    
    def leaveEvent(self, event):
        """鼠标离开 - 立即恢复idle"""
        self._is_hovering = False
        self._hover_timer.stop()
        self._hover_animation = None
        self._current_frame = 0
        self.update()
    
    def _start_hover_animation(self):
        """悬停maimeng动画"""
        if self.engine.stats.hunger <= 35 and self.engine.state != PetState.EATING:
            self._show_hungry_refuse()
            return
        if self._force_animation:
            return
        
        cute_resource = None
        if "maimeng" in self._pixmaps or "maimeng" in self._animation_frames:
            cute_resource = "maimeng"
        elif "play_cute" in self._pixmaps or "play_cute" in self._animation_frames:
            cute_resource = "play_cute"
        
        if cute_resource:
            self._hover_animation = cute_resource
            self._current_frame = 0
            self._hover_timer.stop()
            self.update()
    
    def _is_click_cooldown(self) -> bool:
        """是否处于点击冷却期（仅oneeyes强制动画期间，不影响悬浮和吸附）"""
        return self._force_animation is not None
    
    def _start_force_animation(self, anim_name: str, wait_time: int = 1):
        """启动强制动画（播放1轮+等待后恢复idle）"""
        if anim_name in self._pixmaps or anim_name in self._animation_frames:
            self._hover_timer.stop()
            self._hover_animation = None
            self._force_animation = anim_name
            self._force_anim_cycles = 0
            self._force_anim_wait_time = wait_time
            self._current_frame = 0
            print(f"[动画] 强制播放 '{anim_name}'（1轮+{wait_time}秒冷却）")
            self.update()
    
    def _show_hungry_refuse(self):
        """饥饿时拒绝互动"""
        if self._bubble:
            self._bubble.show_text(f"{self.engine.name}好饿...\n快喂我吃的才能互动！", duration=3000)
            self._update_bubble_position()
    
    def _show_cooldown_tip(self):
        """冷却中提示"""
        import random
        tips = [
            f"别急嘛~让{self.engine.name}缓一下",
            f"点太快啦！{self.engine.name}还没准备好",
            f"等一下下嘛~",
            f"太快了！{self.engine.name}有点晕",
        ]
        if self._bubble:
            self._bubble.show_text(random.choice(tips), duration=2000)
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
        status_text = f"🍖 饱食度: {self.engine.stats.hunger:.0f} | ❤️ 心情: {self.engine.stats.happiness:.0f}"
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
        
        # 退出
        exit_action = menu.addAction("❌ 退出")
        exit_action.triggered.connect(self._on_exit)
        
        menu.exec(self.mapToGlobal(pos))
    
    def _do_feed(self):
        """执行喂食"""
        old_hunger = self.engine.stats.hunger
        success = self.engine.feed()
        if success:
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
    
    def _on_engine_stats_change(self, stats: PetStats):
        """引擎属性变化回调"""
        self.signals.stats_updated.emit(stats)
        self.update()  # 重绘显示状态变化
    
    def _on_engine_state_change(self, state: PetState):
        """引擎状态变化回调"""
        self.signals.state_changed.emit(state)
        self.update()
    
    def _on_animation_frame(self):
        """动画帧更新 - 序列帧系统，支持循环间隔"""
        # 如果处于暂停状态，不更新帧
        if self._anim_cycle_pause:
            return
        
        self._frame_counter += 1
        
        # 获取当前动画序列
        frames = self._animation_frames.get(self._current_animation, [])
        if not frames:
            frames = [self._pixmaps.get(self._current_animation, QPixmap())]
        
        if frames and len(frames) > 1:
            # sleep动画: 每10帧(约400ms)切换，循环不暂停
            # 其他动画: 每6帧(约250ms)切换
            frame_interval = 10 if self._is_sleeping else 6
            if self._frame_counter % frame_interval == 0:
                prev_frame = self._current_frame
                self._current_frame = (self._current_frame + 1) % len(frames)
                
                # 检测完成一个完整循环（回到第0帧）
                if self._current_frame == 0 and prev_frame == len(frames) - 1:
                    if not self._is_sleeping:
                        self._on_anim_cycle_complete()
                    else:
                        self.update()  # sleep循环不暂停
                else:
                    self.update()
        else:
            # 单帧: 每12帧(约500ms)重绘，产生轻微呼吸缩放效果
            if self._frame_counter % 12 == 0:
                self.update()
    
    def _on_hover_anim_end(self):
        """悬停动画结束 - 恢复idle（仅当鼠标已离开时）"""
        if not self._is_hovering:
            print("[悬停] 卖萌动画结束，恢复idle")
            self._hover_animation = None
            self._current_frame = 0
            self.update()
    
    def _on_anim_cycle_complete(self):
        """完成一个动画循环 - 处理强制动画或暂停"""
        # 如果是强制动画（如拖拽后的oneeyes）
        if self._force_animation:
            self._force_anim_cycles += 1
            print(f"[动画] 强制动画 '{self._force_animation}' 完成循环 #{self._force_anim_cycles}")
            
            # 检查是否完成要求的轮数
            if self._force_anim_cycles >= 1 and self._force_anim_wait_time > 0:
                # 完成1轮后，进入等待期
                print(f"[动画] 强制动画进入等待期 {self._force_anim_wait_time}秒")
                self._anim_cycle_pause = True
                self._anim_pause_timer.start(self._force_anim_wait_time * 1000)
                return
            elif self._force_anim_cycles >= 1:
                # 完成且无需等待，直接结束
                self._force_animation = None
                self._force_anim_cycles = 0
                self._current_frame = 0
                print("[动画] 强制动画结束，恢复正常状态")
                self.update()
                return
            # 否则继续播放下一轮
        
        # 正常动画循环，暂停5秒（但刚从强制动画恢复时跳过暂停）
        self._anim_cycle_count += 1
        if self._anim_cycle_count <= 1:
            # 第一个循环不暂停，避免强制动画结束后误触发冷却
            self.update()
            return
        self._anim_cycle_pause = True
        print(f"[动画] 完成循环 #{self._anim_cycle_count}，暂停5秒...")
        self._anim_pause_timer.start(5000)  # 5秒暂停
    
    def _on_anim_pause_end(self):
        """暂停结束 - 继续动画或结束强制动画"""
        self._anim_cycle_pause = False
        
        # 如果是强制动画的等待期结束
        if self._force_animation and self._force_anim_cycles >= 1:
            print("[动画] 强制动画等待期结束，恢复正常状态")
            self._force_animation = None
            self._force_anim_cycles = 0
            self._force_anim_wait_time = 0
            self._current_frame = 0
            self._anim_cycle_count = 0  # 重置正常动画循环计数
            self.update()
            return
        
        print(f"[动画] 暂停结束，继续播放")
    
    def _on_update(self):
        """定时更新 - 检查空闲时间，1分钟无互动触发sleep"""
        self.engine.update()
        
        # 空闲检测：1分钟无互动触发sleep
        if not self._is_sleeping and self.engine.state == PetState.IDLE and not self._dragging:
            import time
            idle_seconds = time.time() - self._last_interaction_time
            if idle_seconds >= 60:
                self._action_sleep()
    
    def _update_interaction_time(self):
        """更新最后互动时间"""
        import time
        self._last_interaction_time = time.time()
        # 如果在睡觉，唤醒
        if self._is_sleeping:
            self._wake_up()
    
    # ============ 动作系统框架 ============
    
    class PetAction:
        """动作类型枚举"""
        IDLE_BLINK = "idle_blink"        # 发呆眨眼（空闲小动画）
        SNAP_TO_EDGE = "snap_to_edge"    # 吸附到边缘
        JUMP = "jump"                     # 跳跃动作
        ROLL = "roll"                     # 翻滚动作
        PLAY_CUTE = "play_cute"          # 卖萌动作
        WALK_AROUND = "walk_around"     # 周围走动
        SLEEP = "sleep"                   # 睡觉
        # 预留接口：可在此添加更多动作类型
    
    def perform_action(self, action_type: str = None):
        """
        执行宠物动作 - 对外接口
        
        Args:
            action_type: 动作类型，None时使用加权随机选择
        """
        import random
        
        # 如果没有指定动作，使用加权随机选择
        if action_type is None:
            action_type = self._weighted_random_action()
        
        print(f"[动作] 开始执行: {action_type}")
        
        # 如果是贴边动作，强制直接调用不经过随机选择
        if action_type == self.PetAction.SNAP_TO_EDGE:
            print("[动作] 强制执行贴边动作")
            self._action_snap_to_edge()
            return
        
        # 记录动作时间
        self._last_action_time = 0
        
        # 动作分发
        if action_type == self.PetAction.IDLE_BLINK:
            self._action_idle_blink()
        elif action_type == self.PetAction.SNAP_TO_EDGE:
            self._action_snap_to_edge()
        elif action_type == self.PetAction.JUMP:
            self._action_jump()
        elif action_type == self.PetAction.ROLL:
            self._action_roll()
        elif action_type == self.PetAction.PLAY_CUTE:
            self._action_play_cute()
        elif action_type == self.PetAction.WALK_AROUND:
            self._action_walk_around()
        elif action_type == self.PetAction.SLEEP:
            self._action_sleep()
        else:
            print(f"[动作] 未知动作类型: {action_type}")
    
    def _weighted_random_action(self) -> str:
        """
        根据权重随机选择动作
        权重越大，被选中的概率越高
        """
        import random
        
        actions = list(self._action_weights.keys())
        weights = list(self._action_weights.values())
        
        # 使用 random.choices 进行加权随机选择
        chosen = random.choices(actions, weights=weights, k=1)[0]
        return chosen
    
    def _get_random_interval(self) -> int:
        """
        使用正态分布生成随机动作间隔
        大部分间隔在 mean ± std 范围内，偶尔有长短不一的间隔
        """
        import random
        
        # 使用正态分布生成
        interval = random.gauss(self._action_interval_mean, self._action_interval_std)
        
        # 限制在最小和最大范围内
        interval = max(self._action_interval_min, min(self._action_interval_max, interval))
        
        return int(interval)
    
    def _action_idle_blink(self):
        """
        动作: 发呆眨眼（最常见的空闲动画）
        不移动位置，只改变表情产生眨眼效果
        """
        print("[动作-眨眼] 😊 眨一下眼睛~")
        
        # 临时改变帧索引产生眨眼效果
        if "idle" in self._animation_frames and len(self._animation_frames["idle"]) >= 2:
            # 如果有idle动画，切换到特定帧模拟眨眼
            original_frame = self._current_frame
            self._current_frame = 1  # 切换到第2帧（通常是不同的表情）
            self.update()
            
            # 200ms后恢复
            QTimer.singleShot(200, lambda: self._restore_frame_after_blink(original_frame))
        else:
            # 如果没有动画帧，触发一次重绘产生轻微缩放效果
            self._is_blinking = True
            self.update()
            QTimer.singleShot(200, self._end_blink)
    
    def _restore_frame_after_blink(self, original_frame: int):
        """眨眼后恢复原帧"""
        self._current_frame = original_frame
        self.update()
    
    def _end_blink(self):
        """结束眨眼状态"""
        self._is_blinking = False
        self.update()
    
    def _action_sleep(self):
        """动作: 睡觉 - 1分钟无互动触发"""
        if self._is_sleeping:
            return
        self._is_sleeping = True
        self.engine.set_state(PetState.SLEEP)
        self._current_animation = "sleep"
        self._current_frame = 0
        print("[动作-睡觉] 💤 1分钟无互动，进入睡眠")
        # 显示睡觉提示
        if self._bubble:
            import random
            tips = [f"{self.engine.name}困了...zzZ", f"💤 呼噜呼噜~", f"{self.engine.name}睡着了~"]
            self._bubble.show_text(random.choice(tips), duration=3000)
            self._update_bubble_position()
        self.update()
    
    def _wake_up(self):
        """唤醒 - 互动时触发"""
        if not self._is_sleeping:
            return
        self._is_sleeping = False
        self.engine.set_state(PetState.IDLE)
        self._current_animation = "idle"
        self._current_frame = 0
        print("[动作-睡觉] 😴 被唤醒")
        # 显示唤醒提示
        if self._bubble:
            import random
            tips = [f"嗯？{self.engine.name}醒了~", f"啊...不想起来...", f"唔...怎么了？"]
            self._bubble.show_text(random.choice(tips), duration=2000)
            self._update_bubble_position()
        self.update()
    
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
        
        margin = 5
        
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
        if abs(nearest_dist) <= margin + 5:
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
            target_y = screen.height() - self.WINDOW_HEIGHT - 60
        
        self._start_move_animation(target_x, target_y, f"吸附-{nearest_edge}")
    
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
        jump_height = 80  # 跳跃高度（像素）
        jump_duration = 600  # 总时长（毫秒）
        
        # 创建跳跃动画计时器
        self._jump_time = 0
        self._jump_timer = QTimer(self)
        self._jump_timer.timeout.connect(lambda: self._on_jump_step(original_x, original_y, jump_height, jump_duration))
        self._jump_timer.start(16)  # 60fps
        
        # 设置跳跃状态（可以通过引擎状态反映到表情）
        self._is_jumping = True
    
    def _on_jump_step(self, original_x: int, original_y: int, jump_height: int, duration: int):
        """跳跃动画单步"""
        self._jump_time += 16
        progress = min(1.0, self._jump_time / duration)
        
        # 抛物线运动: y = 4 * h * x * (1-x)
        height_offset = int(4 * jump_height * progress * (1 - progress))
        
        # 稍微左右摇摆
        wobble = int(5 * (0.5 - abs(progress - 0.5)))
        
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
        roll_duration = 800  # 总时长（毫秒）
        
        self._roll_time = 0
        self._roll_timer = QTimer(self)
        self._roll_timer.timeout.connect(lambda: self._on_roll_step(roll_duration))
        self._roll_timer.start(16)  # 60fps
        
        self._is_rolling = True
    
    def _on_roll_step(self, duration: int):
        """翻滚动画单步"""
        self._roll_time += 16
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
        cute_duration = 1500  # 总时长（毫秒）
        
        self._cute_time = 0
        self._cute_timer = QTimer(self)
        self._cute_timer.timeout.connect(lambda: self._on_cute_step(cute_duration))
        self._cute_timer.start(50)  # 20fps，产生明显的摇摆感
        
        self._is_cute = True
        self._cute_original_x = self.x()
    
    def _on_cute_step(self, duration: int):
        """卖萌动画单步"""
        self._cute_time += 50
        progress = min(1.0, self._cute_time / duration)
        
        # 正弦波摇摆
        import math
        wobble = int(8 * math.sin(progress * 4 * math.pi))
        
        new_x = self._cute_original_x + wobble
        self.move(new_x, self.y())
        
        if progress >= 1.0:
            self._cute_timer.stop()
            self._is_cute = False
            self.move(self._cute_original_x, self.y())
            print("[动作-卖萌] 卖萌结束~")
    
    def _action_walk_around(self):
        """动作5: 周围走动 - 在当前位置附近小范围移动"""
        import random
        
        print("[动作-走动] 🚶 周围走走~")
        
        # 在当前位置附近随机选择一个目标点
        current_x = self.x()
        current_y = self.y()
        
        # 随机偏移 (-100 到 +100 像素)
        offset_x = random.randint(-100, 100)
        offset_y = random.randint(-50, 50)
        
        # 确保不会跑出屏幕
        screen = QApplication.primaryScreen().geometry()
        target_x = max(50, min(screen.width() - self.WINDOW_WIDTH - 50, current_x + offset_x))
        target_y = max(50, min(screen.height() - self.WINDOW_HEIGHT - 80, current_y + offset_y))
        
        # 使用现有的位移动画
        self._start_move_animation(target_x, target_y, "周围走动")
    
    def _on_auto_action(self):
        """
        自动动作触发 - 使用加权随机和正态分布间隔
        让动作看起来更自然、不机械
        """
        # 只在发呆状态且不在拖拽时触发
        if self.engine.state != PetState.IDLE or self._dragging:
            # 如果不是发呆状态，延迟检查
            self._action_timer.start(1000)
            return
        
        # 使用加权随机选择动作（发呆眨眼最常见，翻滚最罕见）
        action = self._weighted_random_action()
        
        print(f"[自动] 触发动作: {action}")
        self.perform_action(action)
        
        # 使用正态分布生成下一次间隔（大部分在10-20秒之间，偶尔短或长）
        next_interval = self._get_random_interval()
        print(f"[自动] 下次动作将在 {next_interval/1000:.1f} 秒后")
        self._action_timer.start(next_interval)
    
    def on_interact(self, interact_type: str = "pet"):
        """外部互动接口 (pet/feed/click)"""
        self._update_interaction_time()  # 记录互动
        
        # 饥饿时拒绝互动（喂食除外）
        if self.engine.stats.hunger <= 35 and self.engine.state != PetState.EATING:
            if interact_type != "feed":
                self._show_hungry_refuse()
                return
        
        # 吸附动画进行中
        if hasattr(self, '_anim_target'):
            return
        
        if interact_type == "pet":
            # 点击冷却检查
            if self._is_click_cooldown():
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
        
        # 启动动画定时器
        self.engine.set_state(PetState.WALK)
        self._walk_timer.start(1000 // 60)  # 60fps
        
        print(f"[动作] {action_name} 开始移动，距离: {distance:.0f}像素")
    
    def set_bubble(self, bubble, offset: QPoint = QPoint(0, -70)):
        """设置对话框引用，用于跟随移动"""
        self._bubble = bubble
        self._bubble_offset = offset
    
    def _update_bubble_position(self):
        """更新对话框位置 - 以宠物为中心，贴边决定气泡起点角，箭头指向宠物"""
        if not self._bubble or not self._bubble.isVisible():
            return
        
        # 获取Pii位置和屏幕信息
        pii_top_left = self.mapToGlobal(QPoint(0, 0))
        pii_x = pii_top_left.x()
        pii_y = pii_top_left.y()
        screen = QApplication.primaryScreen().geometry()
        bubble_width = self._bubble.width()
        bubble_height = self._bubble.height()
        gap = 5  # 气泡与宠物的间距
        
        # 判断Pii贴在哪个边
        margin = 10
        dist_left = pii_x
        dist_right = screen.width() - pii_x - self.WINDOW_WIDTH
        dist_top = pii_y
        dist_bottom = screen.height() - pii_y - self.WINDOW_HEIGHT
        
        # 根据贴边位置决定气泡起点角和箭头方向
        arrow_direction = "down"
        
        if dist_right < margin:  # 贴右边 → 气泡在左上角，箭头从右下角指向宠物
            bubble_x = pii_x - bubble_width - gap
            bubble_y = pii_y - bubble_height - gap
            arrow_direction = "right-down"
        elif dist_left < margin:  # 贴左边 → 气泡在右上角，箭头从左下角指向宠物
            bubble_x = pii_x + self.WINDOW_WIDTH + gap
            bubble_y = pii_y - bubble_height - gap
            arrow_direction = "left-down"
        elif dist_bottom < margin:  # 贴底边 → 气泡在左上角，箭头从右下角指向宠物
            bubble_x = pii_x - bubble_width - gap
            bubble_y = pii_y - bubble_height - gap
            arrow_direction = "right-down"
        elif dist_top < margin:  # 贴顶边 → 气泡在左下角，箭头从右上角指向宠物
            bubble_x = pii_x - bubble_width - gap
            bubble_y = pii_y + self.WINDOW_HEIGHT + gap
            arrow_direction = "right-up"
        else:  # 不贴边 → 默认上方居中，箭头向下
            bubble_x = pii_x + (self.WINDOW_WIDTH - bubble_width) // 2
            bubble_y = pii_y - bubble_height - gap
            arrow_direction = "down"
        
        # 确保不超出屏幕边界
        bubble_x = max(5, min(screen.width() - bubble_width - 5, bubble_x))
        bubble_y = max(5, min(screen.height() - bubble_height - 5, bubble_y))
        
        # 设置箭头方向并移动
        self._bubble.set_arrow_direction(arrow_direction)
        self._bubble.move(bubble_x, bubble_y)
    
    def _on_snap_step(self):
        """动画步进 - 通用实现，同时更新对话框位置"""
        if not hasattr(self, '_anim_target'):
            print(f"[动作-步进] 动画中断: _anim_target不存在")
            self._walk_timer.stop()
            self.engine.set_state(PetState.IDLE)
            return
        
        # 调试输出前3帧和最后3帧
        if self._anim_progress < 0.15 or self._anim_progress > 0.85:
            current_pos = (self.x(), self.y())
            print(f"[动作-步进] 进度={self._anim_progress:.2f}, 位置={current_pos}, 目标={self._anim_target}")
        
        # 进度增加（0.5秒完成，60fps = 30帧）
        self._anim_progress += 1 / 30
        
        if self._anim_progress >= 1.0:
            # 动画完成
            self.move(self._anim_target[0], self._anim_target[1])
            self._update_bubble_position()  # 更新对话框位置
            self._walk_timer.stop()
            self.engine.set_state(PetState.IDLE)
            print(f"[动作] {self._anim_name} 完成")
            delattr(self, '_anim_target')
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
        self._animation_timer.stop()
        self._walk_timer.stop()
        self._walk_pause_timer.stop()
        self._action_timer.stop()  # 停止动作定时器
        self._anim_pause_timer.stop()  # 停止动画暂停定时器
        self._hover_timer.stop()  # 停止悬停定时器
        self.close()
        # 使用 os._exit 强制终止，不清理 Python 对象，确保进程立即结束
        import os
        os._exit(0)
    
    def closeEvent(self, event):
        """关闭事件"""
        self._update_timer.stop()
        self._animation_timer.stop()
        self._walk_timer.stop()
        self._walk_pause_timer.stop()
        self._anim_pause_timer.stop()
        self._hover_timer.stop()
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
    engine = PetEngine("Pii")
    
    # 创建窗口
    window = PetMainWindow(engine)
    window.show()
    
    # 连接信号用于调试输出
    def on_stats_change(stats):
        print(f"[状态更新] 饱食度: {stats.hunger:.1f}, 心情: {stats.happiness:.1f}")
    
    window.signals.stats_updated.connect(on_stats_change)
    
    print("\n窗口已启动，按Ctrl+C或右键菜单退出\n")
    
    sys.exit(app.exec())
