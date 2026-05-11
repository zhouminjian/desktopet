"""
气泡管理器
统一调度所有气泡提示，处理优先级、冷却、位置跟随

提示优先级（数字越小优先级越高）：
1. 升级/成长阶段
2. 饥饿/心情低落
3. 交互反馈（抚摸/喂食）
4. 打字鼓励
5. 普通随机提示
"""

import time
from data.dialogues import PersonalityDialogues
from core.config import PetConfig
from PySide6.QtCore import QPoint


# 优先级常量
PRIORITY_LEVEL_UP = 1
PRIORITY_LOW_STAT = 2
PRIORITY_INTERACTION = 3
PRIORITY_ENCOURAGE = 4
PRIORITY_NORMAL = 5


class BubbleManager:
    """
    气泡提示统一管理器

    使用方式：
    - 调用对应方法触发提示，管理器自动处理冷却和优先级
    - 外部需设置 bubble（SpeechBubble 实例）和 target_widget（主窗口）
    """

    def __init__(self):
        self.bubble = None
        self.target_widget = None
        self._offset = None

        # 冷却追踪
        self._cooldowns: dict[str, float] = {}

    def setup(self, bubble, target_widget, offset=None):
        self.bubble = bubble
        self.target_widget = target_widget
        self._offset = offset or QPoint(0, PetConfig.BUBBLE_OFFSET_Y)

    def _can_show(self, key: str, cooldown: float) -> bool:
        if self.bubble is None or self.bubble.isVisible():
            return False
        last = self._cooldowns.get(key, 0.0)
        return (time.time() - last) > cooldown

    def _record(self, key: str) -> None:
        self._cooldowns[key] = time.time()

    def _show(self, key: str, text: str, duration: int, cooldown: float) -> None:
        if not self._can_show(key, cooldown):
            return
        self.bubble.show_text(text, duration=duration)
        if hasattr(self.target_widget, '_update_bubble_position'):
            self.target_widget._update_bubble_position()
        else:
            self.bubble.position_beside(self.target_widget, self._offset)
        self._record(key)

    def _position(self) -> None:
        if self.bubble and self.target_widget:
            if hasattr(self.target_widget, '_update_bubble_position'):
                self.target_widget._update_bubble_position()
            else:
                self.bubble.position_beside(self.target_widget, self._offset)

    # ---- 各类提示 ----

    def show_level_up(self, new_level: int, exp_for_next: int) -> None:
        self._show(
            "level_up",
            f"升级啦！现在 Lv.{new_level}\n下一级需要: {exp_for_next} 经验",
            PetConfig.BUBBLE_LEVEL_UP_DURATION,
            0,
        )

    def show_stage_change(self, stage_name: str) -> None:
        message = PersonalityDialogues.STAGE_MESSAGES.get(stage_name, "成长了！")
        self._show(
            "stage_change",
            f" {message}",
            PetConfig.BUBBLE_STAGE_CHANGE_DURATION,
            0,
        )

    def show_hunger(self, engine) -> None:
        dialogue = engine.get_dialogue("hungry")
        hunger = engine.stats.hunger
        hunger_level = "很饿" if hunger < PetConfig.HUNGER_CRITICAL_THRESHOLD else "有点饿"
        self._show(
            "hunger",
            f"{dialogue}\n[{hunger_level}] 饱食度: {hunger:.0f}/100\n快给我喂食吧！",
            PetConfig.BUBBLE_HUNGRY_NOTIFY_DURATION,
            PetConfig.BUBBLE_HUNGRY_NOTIFY_INTERVAL,
        )

    def show_happiness_low(self, engine, animation_callback=None) -> None:
        if animation_callback:
            animation_callback("lie", 1)
        text = PersonalityDialogues.get_tip("PLAY_INVITE", engine.name)
        self._show(
            "happiness_low",
            text,
            PetConfig.BUBBLE_PETTED_DURATION,
            PetConfig.HAPPINESS_NOTIFY_INTERVAL,
        )

    def show_lie_hover_tip(self, name: str) -> None:
        """lie 状态下鼠标悬停提示"""
        text = PersonalityDialogues.get_tip("LIE_HOVER_TIPS", name)
        self._show("lie_hover", text, PetConfig.BUBBLE_PETTED_DURATION, 3)

    def show_petted(self, engine) -> None:
        personality = engine.get_primary_personality()
        dialogue = PersonalityDialogues.get_contextual_dialogue(
            personality, engine.stats, engine.name
        )
        self._show(
            "petted",
            dialogue,
            PetConfig.BUBBLE_PETTED_DURATION,
            0,
        )

    def show_typing_encourage(self) -> None:
        self._show(
            "typing",
            PersonalityDialogues.get_tip("ENCOURAGE_LINES"),
            PetConfig.BUBBLE_TYPING_INTENSIVE_DURATION,
            PetConfig.BUBBLE_TYPING_ENCOURAGE_COOLDOWN,
        )

    def show_sleep(self, name: str) -> None:
        self._show(
            "sleep",
            PersonalityDialogues.get_tip("SLEEP_TIPS", name),
            PetConfig.BUBBLE_SLEEP_DURATION,
            0,
        )

    def show_energy_sleep(self, name: str) -> None:
        """精力不足自动触发睡眠提示"""
        self._show(
            "energy_sleep",
            PersonalityDialogues.get_tip("ENERGY_SLEEP_TIPS", name),
            PetConfig.BUBBLE_SLEEP_DURATION,
            0,
        )

    def show_energy_tired(self, name: str) -> None:
        """精力疲劳提示（精力≤20但>15）"""
        self._show(
            "energy_tired",
            PersonalityDialogues.get_tip("ENERGY_TIRED_TIPS", name),
            PetConfig.BUBBLE_PETTED_DURATION,
            60,
        )

    def show_wake(self, name: str) -> None:
        self._show(
            "wake",
            PersonalityDialogues.get_tip("WAKE_TIPS", name),
            PetConfig.BUBBLE_WAKE_DURATION,
            0,
        )

    def show_wake_refusal(self, name: str, reason) -> None:
        """睡眠中互动被拒绝时显示原因"""
        messages = {
            "energy_low": f"{name}太累了...精力不足，让我再睡会儿吧",
            "hunger_low": f"{name}好饿...没力气起来，先喂我点吃的吧",
            "just_woke": f"{name}刚躺下...让我再休息一下",
        }
        text = messages.get(reason, f"{name}还想再睡一会儿...")
        self._show("wake_refusal", text, PetConfig.BUBBLE_WAKE_REFUSAL_DURATION, PetConfig.BUBBLE_WAKE_REFUSAL_COOLDOWN)

    def show_cooldown_tip(self, name: str) -> None:
        self._show(
            "cooldown",
            PersonalityDialogues.get_tip("COOLDOWN_TIPS", name),
            PetConfig.BUBBLE_COOLDOWN_TIP_DURATION,
            0,
        )

    def show_hungry_refuse(self, name: str) -> None:
        self._show(
            "hungry_refuse",
            f"{name}好饿...\n快喂我吃的才能互动！",
            PetConfig.BUBBLE_HUNGRY_REFUSE_DURATION,
            0,
        )

    def show_energy_low_refuse(self, name: str) -> None:
        self._show(
            "energy_low_refuse",
            f"{name}太累了...精力不足\n让我先睡一会儿吧",
            PetConfig.BUBBLE_HUNGRY_REFUSE_DURATION,
            0,
        )

    def show_walk_encourage(self) -> None:
        import random
        msg = random.choice(PetConfig.WALK_ENCOURAGE_MESSAGES)
        self._show("walk_encourage", msg, PetConfig.BUBBLE_WALK_ENCOURAGE_DURATION, 0)

    def update_position(self) -> None:
        self._position()
