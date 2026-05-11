"""
行为控制器
管理睡眠/唤醒逻辑、自动动作触发、动作分发

将原本散落在 main_window.py 中的行为逻辑集中到此处，
窗口层只负责接收回调并执行具体视觉表现。
"""

import time
import random
from enum import Enum
from typing import Optional

from core.engine import PetEngine, PetState
from core.config import PetConfig


class PetAction:
    """动作类型枚举"""
    IDLE_BLINK = "idle_blink"
    SNAP_TO_EDGE = "snap_to_edge"
    WALK_AROUND = "walk_around"
    JUMP = "jump"
    ROLL = "roll"
    PLAY_CUTE = "play_cute"
    SLEEP = "sleep"
    LIE = "lie"


class BehaviorController:
    """
    行为控制器

    通过回调与窗口层解耦，窗口层设置以下回调：
    - on_perform_action(action_type)  执行具体动画表现
    - on_sleep()                      进入睡眠
    - on_wake_up()                    唤醒
    """

    def __init__(self, engine: PetEngine):
        self.engine = engine

        # 互动时间追踪
        self._last_interaction_time: float = time.time()

        # IDLE 开始时间（用于 walk 最小等待判断）
        self._idle_since: float = time.time()

        # 睡眠状态
        self._is_sleeping: bool = False

        # 自动动作配置
        self._action_weights = PetConfig.ACTION_WEIGHTS
        self._action_interval_mean = PetConfig.AUTO_ACTION_INTERVAL_MEAN
        self._action_interval_std = PetConfig.AUTO_ACTION_INTERVAL_STD
        self._action_interval_min = PetConfig.AUTO_ACTION_INTERVAL_MIN
        self._action_interval_max = PetConfig.AUTO_ACTION_INTERVAL_MAX
        self._last_action_time: float = 0.0

        # 回调（由窗口层设置）
        self.on_perform_action = None
        self.on_sleep = None
        self.on_wake_up = None
        self.on_tired = None  # 精力疲劳回调

    # ---- 互动时间 ----

    def update_interaction_time(self) -> None:
        """记录互动时间（非睡眠状态下调用）"""
        self._last_interaction_time = time.time()

    def is_sleeping(self) -> bool:
        return self._is_sleeping

    # ---- 睡眠 ----

    def check_sleep(self, is_dragging: bool) -> None:
        """每秒调用，检测是否应进入睡眠（能量低/饥饿/无互动，任一满足即进入）"""
        if self._is_sleeping:
            return
        if is_dragging:
            return

        # 强制睡眠：精力或饱食度不足时，无论当前状态（IDLE/EATING/WALK 等）都强制进入睡眠
        if self.engine.stats.energy <= PetConfig.WAKE_ENERGY_THRESHOLD:
            self.enter_sleep(reason="energy_low")
            return
        if self.engine.stats.hunger <= PetConfig.WAKE_HUNGER_THRESHOLD:
            self.enter_sleep(reason="hunger_low")
            return

        # 精力疲劳：精力≤20时触发 tired 动画提示（不进入睡眠）
        if self.engine.stats.energy <= PetConfig.ENERGY_TIRED_THRESHOLD:
            if self.on_tired:
                self.on_tired()
            return

        # 无互动睡眠：仅在 IDLE 状态时检测
        if self.engine.state != PetState.IDLE:
            return
        idle_seconds = time.time() - self._last_interaction_time
        if idle_seconds >= PetConfig.SLEEP_IDLE_TIME:
            self.enter_sleep(reason="idle")

    def enter_sleep(self, reason: str = "idle") -> None:
        """
        进入睡眠。
        Args:
            reason: 触发原因 ("energy_low" / "hunger_low" / "idle")
        """
        if self._is_sleeping:
            return
        self._is_sleeping = True
        self._sleep_reason = reason
        self.engine.set_state(PetState.SLEEP)
        if self.on_sleep:
            self.on_sleep(reason)

    def get_wake_refusal_reason(self) -> Optional[str]:
        """
        检查是否满足唤醒条件，返回拒绝原因（字符串 key），全部满足返回 None。
        三者必须同时满足才允许唤醒：精力>阈值、饱食度>阈值、互动时间已重置。
        """
        if self.engine.stats.energy <= PetConfig.WAKE_ENERGY_THRESHOLD:
            return "energy_low"
        if self.engine.stats.hunger <= PetConfig.WAKE_HUNGER_THRESHOLD:
            return "hunger_low"
        idle_seconds = time.time() - self._last_interaction_time
        if idle_seconds < PetConfig.WAKE_MIN_IDLE_TIME:
            return "just_woke"
        return None

    def wake_up(self) -> bool:
        """
        尝试唤醒宠物，返回是否成功。
        精力>阈值 且 饱食度>阈值 且 互动冷却已过 才允许唤醒。
        注意：_last_interaction_time 由调用方（交互事件）更新，此处不再重复设置，
        否则会导致 idle_seconds 始终为 0，5秒冷却检查永远失败。
        """
        if not self._is_sleeping:
            return True

        reason = self.get_wake_refusal_reason()
        if reason is not None:
            return False

        self._is_sleeping = False
        self._idle_since = time.time()
        self.engine.set_state(PetState.IDLE)
        if self.on_wake_up:
            self.on_wake_up()

        # 唤醒后立即检查：精力或饱食度不满足则强制回睡眠
        if self.engine.stats.energy <= PetConfig.WAKE_ENERGY_THRESHOLD:
            self.enter_sleep(reason="energy_low")
            return False
        if self.engine.stats.hunger <= PetConfig.WAKE_HUNGER_THRESHOLD:
            self.enter_sleep(reason="hunger_low")
            return False
        return True

    # ---- Walk 判断 ----

    def can_walk(self) -> bool:
        """IDLE 状态且已空闲足够长时间，允许触发 walk"""
        if self._is_sleeping:
            return False
        if self.engine.state != PetState.IDLE:
            return False
        return (time.time() - self._idle_since) >= PetConfig.WALK_MIN_IDLE_TIME

    def record_idle_start(self) -> None:
        """记录进入 IDLE 的时间（状态切到 IDLE 时调用）"""
        self._idle_since = time.time()

    # ---- 自动动作 ----

    def choose_weighted_action(self) -> str:
        actions = list(self._action_weights.keys())
        weights = list(self._action_weights.values())
        if not self.can_walk():
            # 过滤掉 walk_around
            filtered = [(a, w) for a, w in zip(actions, weights) if a != PetAction.WALK_AROUND]
            if filtered:
                actions, weights = zip(*filtered)
            else:
                actions, weights = [PetAction.IDLE_BLINK], [1]
        return random.choices(actions, weights=weights, k=1)[0]

    def get_random_interval(self) -> int:
        interval = random.gauss(self._action_interval_mean, self._action_interval_std)
        return int(max(self._action_interval_min, min(self._action_interval_max, interval)))

    def try_auto_action(self, is_dragging: bool) -> bool:
        """
        尝试触发自动动作，返回是否触发。
        仅在 IDLE 状态且未拖拽时触发。
        """
        if self.engine.state != PetState.IDLE:
            return False
        if is_dragging:
            return False

        action = self.choose_weighted_action()
        if self.on_perform_action:
            self.on_perform_action(action)
        return True
