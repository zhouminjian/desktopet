"""
公共枚举类型
避免 engine.py 与 data/dialogues.py 之间的循环导入
"""

from enum import Enum, auto


class PetState(Enum):
    """宠物状态枚举"""
    IDLE = auto()
    WALK = auto()
    SLEEP = auto()
    EATING = auto()
    DRAGGING = auto()


class GrowthStage(Enum):
    """成长阶段枚举"""
    BABY = auto()
    TEEN = auto()
    ADULT = auto()

    @property
    def display_name(self) -> str:
        names = {
            GrowthStage.BABY: "幼年",
            GrowthStage.TEEN: "少年",
            GrowthStage.ADULT: "青年",
        }
        return names.get(self, "未知")


class PersonalityTrait(Enum):
    """性格标签枚举"""
    PLAYFUL = "活泼"
    GENTLE = "温柔"
    LAZY = "慵懒"
    CURIOUS = "好奇"
