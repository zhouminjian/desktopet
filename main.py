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
sys.path.insert(0, current_dir)

from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QSizePolicy
from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtGui import QColor

from core.engine import PetEngine, PetState, PetStats, PersonalityTrait, PersonalityDialogues, GrowthStage
from core.database import PetDatabase
from core.perception import UserActivityMonitor
from ui.main_window import PetMainWindow
from ui.components import SpeechBubble, FloatingText


class PersonalitySelector(QDialog):
    """
    性格选择对话框
    让用户选择宠物的性格
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.selected_personality = None
        self.pet_name = "Pii"  # 默认宠物名称
        
        self.setWindowTitle("选择你的宠物性格")
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
        title = QLabel("🐱 请选择你的 Pii 的性格：")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #4a90d9;")
        layout.addWidget(title)
        
        # 说明文字
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
        
        # 按钮布局 - 自适应宽度
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        personalities = [
            (PersonalityTrait.PLAYFUL, "活泼", "好动爱玩，元气满满"),
            (PersonalityTrait.GENTLE, "温柔", "温顺粘人，安静陪伴"),
            (PersonalityTrait.LAZY, "慵懒", "爱睡爱躺，佛系生活"),
            (PersonalityTrait.CURIOUS, "好奇", "探索发现，十万个为什么"),
        ]
        
        for personality, name, desc_text in personalities:
            btn = QPushButton(f"{name}\n{desc_text}")
            btn.setMinimumHeight(90)
            btn.setMinimumWidth(140)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setStyleSheet("""
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
            """)
            btn.clicked.connect(lambda checked, p=personality: self._on_select(p))
            btn_layout.addWidget(btn, 1)  # 权重1，平均分配空间
        
        layout.addLayout(btn_layout)
        layout.addStretch()
    
    def _on_select(self, personality: PersonalityTrait):
        """选择性格"""
        self.selected_personality = personality
        # 获取用户输入的名称，如果没输入则使用默认值
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
    
    # 创建对话气泡
    bubble = SpeechBubble()
    window.set_bubble(bubble, QPoint(0, -70))  # 设置气泡跟随窗口
    
    # 创建浮动文字组件(用于显示数值变化)
    floating_text = FloatingText()
    
    # 初始化感知系统
    monitor = UserActivityMonitor()
    
    # 饥饿提示计时器（防止重复提示）
    _last_hunger_notify_time = 0
    
    # 连接信号 - 实现前后端通信
    def on_stats_change(stats: PetStats):
        """属性变化时更新气泡提示 - 使用性格对话"""
        nonlocal _last_hunger_notify_time
        import time
        
        # 饿了时显示性格化的提示（阈值35，每30秒最多提示一次）
        current_time = time.time()
        if stats.hunger <= 35 and not bubble.isVisible():
            if current_time - _last_hunger_notify_time > 30:  # 30秒间隔
                dialogue = engine.get_dialogue("hungry")
                hunger_level = "很饿" if stats.hunger < 20 else "有点饿"
                bubble.show_text(f"{dialogue}\n[{hunger_level}] 饱食度: {stats.hunger:.0f}/100\n快给我喂食吧！", duration=5000)
                bubble.position_beside(window, QPoint(0, -70))
                _last_hunger_notify_time = current_time
        
        # 实时存档：30秒防抖，避免频繁IO
        _last_save = getattr(on_stats_change, '_last_save', 0)
        if current_time - _last_save >= 30:
            save_data = engine.to_dict()
            db.save(save_data)
            on_stats_change._last_save = current_time
    
    def on_state_change(state: PetState):
        """状态变化时输出日志"""
        state_names = {
            PetState.IDLE: "发呆",
            PetState.WALK: "行走",
            PetState.SLEEP: "睡觉",
            PetState.EATING: "进食",
            PetState.DRAGGING: "被拖拽"
        }
        print(f"[状态] 切换至: {state_names.get(state, state.name)}")
    
    def on_level_up(new_level: int):
        """升级回调"""
        print(f"[成长] 🎉 升级到 Lv.{new_level}！")
        bubble.show_text(f"🎉 升级啦！现在 Lv.{new_level}\n下一级需要: {engine.get_exp_for_next_level()} 经验", duration=3000)
        bubble.position_beside(window, QPoint(0, -90))
    
    def on_stage_change(new_stage: GrowthStage):
        """成长阶段变化回调"""
        print(f"[成长] 🌟 进入{new_stage.display_name}阶段！")
        stage_messages = {
            GrowthStage.TEEN: "我长大一点了！开始对世界好奇~",
            GrowthStage.ADULT: "我已经完全长大了！会更好地陪伴主人！"
        }
        message = stage_messages.get(new_stage, "成长了！")
        bubble.show_text(f"🌟 {message}", duration=4000)
        bubble.position_beside(window, QPoint(0, -90))
    
    # 设置用户活动监听回调
    def on_typing_intensive(key_count: int):
        """检测到高强度打字时，宠物给予鼓励"""
        if not bubble.isVisible():
            encourage_lines = [
                "主人加油！打字辛苦了~ 休息一下喝点水吧！",
                "哇，主人工作好认真！别忘了我一直在陪着你哦~",
                "检测到高强度工作！送上一杯虚拟咖啡 ☕",
                "工作再忙也要记得休息，我会一直在这里的~"
            ]
            import random
            message = random.choice(encourage_lines)
            bubble.show_text(message, duration=5000)
            bubble.position_beside(window, QPoint(0, -80))
    
    # 绑定引擎回调
    engine.on_stats_change = on_stats_change
    engine.on_state_change = on_state_change
    engine.on_level_up = on_level_up
    engine.on_stage_change = on_stage_change
    
    # 绑定窗口信号
    window.signals.stats_updated.connect(on_stats_change)
    window.signals.state_changed.connect(on_state_change)
    
    # 绑定抚摸信号 - 显示性格对话和动作
    def on_pet():
        """被抚摸时显示性格化对话和动作"""
        dialogue = engine.get_dialogue("petted")
        bubble.show_text(dialogue, duration=2500)
        bubble.position_beside(window, QPoint(0, -60))
        # 触发抚摸动作
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
    
    # 启动活动监视器
    monitor.on_typing_intensive = on_typing_intensive
    monitor.start()
    
    # 显示主窗口
    window.show()
    
    # 显示欢迎气泡 - 使用性格化问候（简化版，避免超出屏幕）
    greeting = engine.get_dialogue("greeting")
    exp_needed = engine.get_exp_for_next_level()
    bubble.show_text(
        f"嗨！我是{engine.name}~ {greeting}\n"
        f"Lv.{engine.stats.level} | 经验:{engine.stats.exp}/{exp_needed}\n"
        f"右键点击喂食", 
        duration=4000
    )
    # 使用智能位置更新（根据贴边位置自动调整）
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
