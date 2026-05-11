"""
状态解析器
统一决定当前应呈现的动画状态，消除分散在多处的优先级判断

优先级：强制动画 > 悬停动画 > 引擎状态 > 饥饿覆盖
"""

from core.engine import PetState
from core.config import PetConfig


# 引擎状态 → 动画状态名映射
_STATE_MAP = {
    PetState.IDLE: "idle",
    PetState.WALK: "walk",
    PetState.SLEEP: "sleep",
    PetState.EATING: "eating",
    PetState.DRAGGING: "idle",
}


def resolve_animation_state(
    pet_state: PetState,
    hunger: float,
    is_sleeping: bool,
    force_animation: str | None,
    hover_animation: str | None,
) -> str:
    """
    根据当前各项状态，返回应播放的动画状态名。

    优先级顺序：
    1. force_animation（点击反馈等强制动画）
    2. hover_animation（鼠标悬停卖萌）
    3. 饥饿覆盖（饱食度低且非进食/睡眠时）
    4. 引擎逻辑状态映射
    """
    # 1. 强制动画优先
    if force_animation:
        return force_animation

    # 2. 悬停动画
    if hover_animation:
        return hover_animation

    # 3. 饥饿覆盖
    if (
        hunger <= PetConfig.HUNGER_LOW_THRESHOLD
        and pet_state != PetState.EATING
        and not is_sleeping
    ):
        return "hungry"

    # 4. 引擎状态映射
    return _STATE_MAP.get(pet_state, "idle")
