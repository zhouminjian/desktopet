"""
桌面宠物 Pii - 程序入口
启动桌面宠物应用程序

阶段1: 生存 - 实现核心功能
阶段2: 动效 - 生动化
阶段3: 进化 - 感知与成长
"""

import sys
import os

# 确保模块导入路径正确
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QSizePolicy
from PySide6.QtCore import Qt, QPoint, QTimer, Signal, QObject
from PySide6.QtGui import QColor

from core.engine import PetEngine, PetState, PetStats, PersonalityTrait, GrowthStage
from data.dialogues import PersonalityDialogues
from core.database import PetDatabase
from core.perception import UserActivityMonitor
from core.config import PetConfig
from ui.main_window import PetMainWindow
from ui.components import SpeechBubble, FloatingText
from ui.bubble_manager import BubbleManager


class CrossThreadSignals(QObject):
    """跨线程信号载体，用于将 pynput 后台线程的安全地派发到主线程"""
    typing_intensive = Signal(int)


class PersonalitySelector(QDialog):
    """
    性格选择对话框
    让用户选择宠物的性格，支持预填当前值
    """

    def __init__(self, parent=None, initial_name: str = "Pii", initial_personality: PersonalityTrait = None):
        super().__init__(parent)

        self.selected_personality = None
        self.pet_name = "Pii"

        is_edit = initial_personality is not None
        self.setWindowTitle("更改宠物名字和性格" if is_edit else "选择你的宠物性格")
        self.setFixedSize(700, 320)
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
            QLabel {
                font-family: "Microsoft YaHei";
                font-size: 14px;
                color: #333;
            }
            QPushButton {
                font-family: "Microsoft YaHei";
                font-size: 13px;
                padding: 10px 20px;
                border-radius: 8px;
                border: 2px solid #ddd;
                background-color: white;
            }
            QPushButton:hover {
                background-color: #e8f4f8;
                border-color: #4a90d9;
            }
            QPushButton:pressed {
                background-color: #d0e8f0;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        title_text = "🐱 更改宠物名字和性格：" if is_edit else "🐱 请选择你的 Pii 的性格："
        title = QLabel(title_text)
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #4a90d9;")
        layout.addWidget(title)

        desc = QLabel("性格会影响 Pii 的行为方式和说话风格哦~")
        desc.setStyleSheet("font-size: 12px; color: #666; margin-bottom: 10px;")
        layout.addWidget(desc)

        # 宠物名称输入框
        name_layout = QHBoxLayout()
        name_label = QLabel("宠物名称：")
        name_label.setStyleSheet("font-size: 13px; color: #333;")
        name_layout.addWidget(name_label)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Pii")
        self._name_input.setText(initial_name)
        self._name_input.setStyleSheet("""
            QLineEdit {
                font-family: "Microsoft YaHei";
                font-size: 13px;
                padding: 8px;
                border-radius: 6px;
                border: 2px solid #ddd;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #4a90d9;
            }
        """)
        self._name_input.setFixedWidth(200)
        name_layout.addWidget(self._name_input)
        name_layout.addStretch()

        layout.addLayout(name_layout)
        layout.addSpacing(10)

        # 性格按钮布局
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        personalities = [
            (PersonalityTrait.PLAYFUL, "活泼", "好动爱玩，元气满满"),
            (PersonalityTrait.GENTLE, "温柔", "温顺粘人，安静陪伴"),
            (PersonalityTrait.LAZY, "慵懒", "爱睡爱躺，佛系生活"),
            (PersonalityTrait.CURIOUS, "好奇", "探索发现，十万个为什么"),
        ]

        self._personality_btns = {}
        for personality, name, desc_text in personalities:
            btn = QPushButton(f"{name}\n{desc_text}")
            btn.setMinimumHeight(90)
            btn.setMinimumWidth(140)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            is_current = (personality == initial_personality)
            btn.setStyleSheet(self._btn_style(selected=is_current))
            btn.clicked.connect(lambda checked, p=personality: self._on_select(p))
            btn_layout.addWidget(btn, 1)
            self._personality_btns[personality] = btn

        layout.addLayout(btn_layout)

        # 初始选中
        if initial_personality is not None:
            self.selected_personality = initial_personality

        # 确定按钮 - 居中
        confirm_layout = QHBoxLayout()
        confirm_layout.addStretch()
        self._confirm_btn = QPushButton("确 定")
        self._confirm_btn.setMinimumWidth(120)
        self._confirm_btn.setMinimumHeight(36)
        self._confirm_btn.setStyleSheet("""
            QPushButton {
                font-family: "Microsoft YaHei";
                font-size: 14px;
                font-weight: bold;
                padding: 8px 30px;
                border-radius: 8px;
                border: 2px solid #4a90d9;
                background-color: #4a90d9;
                color: white;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
        """)
        self._confirm_btn.clicked.connect(self._on_confirm)
        confirm_layout.addWidget(self._confirm_btn)
        confirm_layout.addStretch()

        layout.addLayout(confirm_layout)
        layout.addStretch()

    @staticmethod
    def _btn_style(selected: bool = False) -> str:
        base = """
            QPushButton {
                font-family: "Microsoft YaHei";
                font-size: 12px;
                padding: 6px;
                border-radius: 8px;
                border: 2px solid #ddd;
                background-color: white;
            }
            QPushButton:hover {
                background-color: #fff3e0;
                border-color: #ff9800;
            }
        """
        if selected:
            base += """
            QPushButton {
                border-color: #4a90d9;
                background-color: #e8f4f8;
            }
            """
        return base

    def _on_select(self, personality: PersonalityTrait):
        self.selected_personality = personality
        for p, btn in self._personality_btns.items():
            btn.setStyleSheet(self._btn_style(selected=(p == personality)))

    def _on_confirm(self):
        name = self._name_input.text().strip()
        if name:
            self.pet_name = name
        self.accept()


def show_personality_selector() -> tuple[PersonalityTrait, str]:
    """显示性格选择对话框，返回性格和宠物名称"""
    dialog = PersonalitySelector()
    if dialog.exec() == QDialog.Accepted and dialog.selected_personality:
        return dialog.selected_personality, dialog.pet_name
    return PersonalityTrait.GENTLE, "Pii"  # 默认返回温柔性格和默认名称


def main():
    """
    主函数 - 启动桌面宠物
    
    阶段1 + 阶段2 + 阶段3: 完整功能
    """
    
    # 启用高分屏支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    # 创建应用实例
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    # 初始化数据库
    db = PetDatabase()
    
    # 尝试加载存档
    saved_data = db.load()
    
    if saved_data:
        # 有存档，恢复宠物
        print("[启动] 发现存档，恢复宠物...")
        engine = PetEngine.from_dict(saved_data)
        personality = engine.get_primary_personality()
        print(f"[启动] 恢复成功: {engine.name} (Lv.{engine.stats.level} {engine.growth_stage.display_name})")
    else:
        # 无存档，新建宠物
        print("[启动] 创建新宠物...")
        personality, pet_name = show_personality_selector()
        print(f"[启动] 已选择性格: {personality.value}, 名称: {pet_name}")
        
        # 创建宠物引擎 (Model层)
        print("[启动] 初始化宠物引擎...")
        engine = PetEngine(name=pet_name)
        engine.personality = [personality]
    
    # 创建主窗口 (View层)
    print("[启动] 创建主窗口...")
    window = PetMainWindow(engine)
    
    # 创建对话气泡和管理器
    bubble = SpeechBubble()
    window.set_bubble(bubble, QPoint(0, -70))

    bubble_mgr = BubbleManager()
    bubble_mgr.setup(bubble, window)
    window.bubble_mgr = bubble_mgr

    # 创建浮动文字组件(用于显示数值变化)
    floating_text = FloatingText()

    # 初始化感知系统
    monitor = UserActivityMonitor()

    # 连接信号 - 实现前后端通信
    def on_stats_change(stats: PetStats):
        """属性变化时触发气泡提示 + 自动存档"""
        import time
        current_time = time.time()

        # 睡眠状态下不触发常规状态气泡和强制动画
        if engine.state != PetState.SLEEP:
            if stats.hunger <= PetConfig.HUNGER_LOW_THRESHOLD:
                bubble_mgr.show_hunger(engine)

            if stats.happiness < PetConfig.HAPPINESS_LOW_THRESHOLD:
                bubble_mgr.show_happiness_low(engine, animation_callback=window._start_force_animation)

        _last_save = getattr(on_stats_change, '_last_save', 0)
        if current_time - _last_save >= PetConfig.AUTO_SAVE_INTERVAL:
            db.save(engine.to_dict())
            on_stats_change._last_save = current_time

    def on_state_change(state: PetState):
        state_names = {
            PetState.IDLE: "发呆", PetState.WALK: "行走",
            PetState.SLEEP: "睡觉", PetState.EATING: "进食",
            PetState.DRAGGING: "被拖拽",
        }
        print(f"[状态] 切换至: {state_names.get(state, state.name)}")

    def on_level_up(new_level: int):
        print(f"[成长] 升级到 Lv.{new_level}！")
        bubble_mgr.show_level_up(new_level, engine.get_exp_for_next_level())

    def on_stage_change(new_stage: GrowthStage):
        print(f"[成长] 进入{new_stage.display_name}阶段！")
        bubble_mgr.show_stage_change(new_stage.name)

    _last_typing_remind_time = 0.0

    def on_typing_intensive(key_count: int):
        nonlocal _last_typing_remind_time
        import time
        now = time.time()
        if now - _last_typing_remind_time < PetConfig.TYPING_INTENSIVE_COOLDOWN:
            return
        _last_typing_remind_time = now
        bubble_mgr.show_typing_encourage()

    # 跨线程信号：pynput 回调在后台线程触发，通过信号安全地派发到主线程
    cross_signals = CrossThreadSignals()
    cross_signals.typing_intensive.connect(on_typing_intensive)

    # 绑定引擎回调
    engine.on_stats_change = on_stats_change
    engine.on_state_change = on_state_change
    engine.on_level_up = on_level_up
    engine.on_stage_change = on_stage_change
    
    # 绑定窗口信号
    window.signals.stats_updated.connect(on_stats_change)
    window.signals.state_changed.connect(on_state_change)
    
    # 绑定抚摸信号
    def on_pet():
        window.on_interact("pet")

    window.signals.pet_requested.connect(on_pet)
    
    # 绑定喂食信号 - 触发动作
    def on_feed():
        """喂食时触发动作"""
        window.on_interact("feed")
    
    window.signals.feed_requested.connect(on_feed)
    
    # 绑定浮动文字信号 - 显示数值变化
    def on_hunger_change(increase: float):
        """饱食度变化时显示浮动文字"""
        floating_text.show_value(
            f"+{increase:.0f} 饱食度",
            QColor(255, 150, 100),  # 橘色
            window,
            QPoint(0, -60)
        )
    
    def on_exp_gain(amount: int):
        """获得经验时显示浮动文字"""
        floating_text.show_value(
            f"+{amount} 经验",
            QColor(255, 215, 0),  # 金色
            window,
            QPoint(0, -85)
        )
    
    window.signals.hunger_changed.connect(on_hunger_change)
    window.signals.exp_gained.connect(on_exp_gain)

    # 绑定更改名字和性格信号
    def on_change_personality():
        current_personality = engine.get_primary_personality()
        dialog = PersonalitySelector(
            initial_name=engine.name,
            initial_personality=current_personality,
        )
        result = dialog.exec()
        if result == QDialog.Accepted and dialog.selected_personality:
            engine.name = dialog.pet_name
            engine.personality = [dialog.selected_personality]
            db.save(engine.to_dict())
            bubble.show_text(
                f"好~以后叫我{engine.name}吧！\n性格变成了{dialog.selected_personality.value}~",
                duration=4000,
            )
            QTimer.singleShot(100, window._update_bubble_position)
            print(f"[设置] 更改成功: {engine.name} ({dialog.selected_personality.value})")
        else:
            bubble.show_text("没关系~保持现在的样子就好！", duration=3000)
            QTimer.singleShot(100, window._update_bubble_position)

    window.signals.change_personality_requested.connect(on_change_personality)
    
    # 启动活动监视器
    monitor.on_typing_intensive = lambda key_count: cross_signals.typing_intensive.emit(key_count)
    monitor.start()

    # 定时检查打字频率窗口（从主线程调用，避免 pynput 回调线程阻塞）
    _perception_timer = QTimer()
    _perception_timer.timeout.connect(monitor.check_window)
    _perception_timer.start(PetConfig.UPDATE_TIMER_INTERVAL)
    
    # 显示主窗口
    window.show()
    
    # 显示欢迎气泡
    greeting = engine.get_dialogue("greeting")
    exp_needed = engine.get_exp_for_next_level()
    bubble.show_text(
        f"嗨！我是{engine.name}~ {greeting}\n"
        f"Lv.{engine.stats.level} | 经验:{engine.stats.exp}/{exp_needed}\n"
        f"右键点击喂食",
        duration=PetConfig.BUBBLE_GREETING_DURATION,
    )
    QTimer.singleShot(100, window._update_bubble_position)
    
    print("[启动] 桌面宠物已启动!")
    print("=" * 40)
    print(f"性格: {personality.value}")
    print(f"等级: Lv.{engine.stats.level} ({engine.growth_stage.display_name})")
    print(f"经验: {engine.stats.exp}/{exp_needed}")
    print("操作指南:")
    print("  - 左键按住拖拽: 移动宠物位置")
    print("  - 右键点击: 打开菜单(喂食/抚摸/退出)")
    print("  - 喂食: +饱食度，+10经验")
    print("  - 抚摸: +心情，+5经验")
    print("  - 每分钟在线: +1经验")
    print("  - 高强度打字时: 宠物会送鼓励")
    print("=" * 40)
    
    # 启动事件循环
    exit_code = app.exec()
    
    # 程序退出前保存
    print("[退出] 保存宠物数据...")
    save_data = engine.to_dict()
    db.save(save_data)
    monitor.stop()
    
    return sys.exit(exit_code)


if __name__ == "__main__":
    main()
