"""
桌面宠物核心引擎 (Model层)
管理宠物 Pii 的所有状态属性与成长逻辑
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Callable, Optional
from datetime import datetime
import json
import os

from core.config import PetConfig
from core.enums import PetState, GrowthStage, PersonalityTrait
from data.dialogues import PersonalityDialogues

# 向后兼容：允许 `from core.engine import PetState` 等旧写法
__all__ = ["PetStats", "PetEngine", "PetState", "GrowthStage", "PersonalityTrait"]


@dataclass
class PetStats:
    """宠物属性数据结构 - 前后端变量一致
    
    字段命名规范:
    - hunger: 饱食度 (0-100, 越低越饿)
    - happiness: 心情值 (0-100)
    - energy: 精力值 (0-100)
    - hygiene: 清洁度 (0-100)
    - level: 等级
    - exp: 经验值
    - age_days: 年龄(天)
    """
    hunger: float = PetConfig.DEFAULT_HUNGER      # 饱食度
    happiness: float = PetConfig.DEFAULT_HAPPINESS # 心情值
    energy: float = PetConfig.DEFAULT_ENERGY       # 精力值
    hygiene: float = PetConfig.DEFAULT_HYGIENE     # 清洁度
    level: int = 1              # 等级
    exp: int = 0                # 经验值
    age_days: int = 0           # 年龄天数
    
    # 状态标记
    is_sleeping: bool = False
    
    def __post_init__(self):
        """确保数值在有效范围内"""
        self._clamp_values()
    
    def _clamp_values(self):
        """将所有数值限制在0-100范围内"""
        self.hunger = max(0.0, min(100.0, self.hunger))
        self.happiness = max(0.0, min(100.0, self.happiness))
        self.energy = max(0.0, min(100.0, self.energy))
        self.hygiene = max(0.0, min(100.0, self.hygiene))
    
    def to_dict(self) -> dict:
        """转换为字典格式 - 用于存档和前后端传递"""
        return {
            "hunger": self.hunger,
            "happiness": self.happiness,
            "energy": self.energy,
            "hygiene": self.hygiene,
            "level": self.level,
            "exp": self.exp,
            "age_days": self.age_days,
            "is_sleeping": self.is_sleeping
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "PetStats":
        """从字典恢复 - 保持变量名一致"""
        return cls(
            hunger=data.get("hunger", PetConfig.DEFAULT_HUNGER),
            happiness=data.get("happiness", PetConfig.DEFAULT_HAPPINESS),
            energy=data.get("energy", PetConfig.DEFAULT_ENERGY),
            hygiene=data.get("hygiene", PetConfig.DEFAULT_HYGIENE),
            level=data.get("level", 1),
            exp=data.get("exp", 0),
            age_days=data.get("age_days", 0),
            is_sleeping=data.get("is_sleeping", False)
        )


class PetEngine:
    """
    宠物核心引擎
    管理状态变化、衰减逻辑、互动响应
    """
    
    # 常量定义 - 便于统一调整
    HUNGER_DECAY_RATE = PetConfig.HUNGER_DECAY_RATE             # 清醒饱食度衰减（每分钟掉1点）
    HUNGER_DECAY_SLEEP_RATE = PetConfig.HUNGER_DECAY_SLEEP_RATE  # 睡眠饱食度衰减（每5分钟掉1点）
    HAPPINESS_DECAY_RATE = PetConfig.HAPPINESS_DECAY_RATE       # 心情衰减（每分钟掉1点）
    HAPPINESS_LOW_HUNGER_DECAY_RATE = PetConfig.HAPPINESS_LOW_HUNGER_DECAY_RATE  # 饱食度≤35时心情衰减（每分钟掉2点）
    ENERGY_SLEEP_RECOVER_RATE = PetConfig.ENERGY_SLEEP_RECOVER_RATE  # 睡眠精力恢复
    ENERGY_AWAKE_RECOVER_RATE = PetConfig.ENERGY_AWAKE_RECOVER_RATE  # 清醒精力恢复
    ENERGY_INTERACT_COST = PetConfig.ENERGY_INTERACT_COST      # 交互精力消耗

    HAPPINESS_PET_GAIN = PetConfig.HAPPINESS_PET_GAIN
    HAPPINESS_FEED_GAIN = PetConfig.HAPPINESS_FEED_GAIN

    FEED_VALUE = PetConfig.FEED_VALUE
    MAX_STATS = PetConfig.MAX_STATS

    # 成长系统常量
    
    # 成长系统常量
    EXP_PER_FEED = PetConfig.EXP_PER_FEED               # 喂食获得经验
    EXP_PER_PET = PetConfig.EXP_PER_PET                 # 抚摸获得经验
    EXP_PER_MINUTE = PetConfig.EXP_PER_MINUTE_ONLINE              # 每分钟在线获得经验
    LEVEL_UP_BASE = PetConfig.LEVEL_UP_BASE_EXP             # 每级所需基础经验（逐级增加）
    
    # 成长阶段解锁等级
    STAGE_LEVELS = {
        GrowthStage.BABY: PetConfig.STAGE_LEVELS["BABY"],        # 幼年: 1-4级
        GrowthStage.TEEN: PetConfig.STAGE_LEVELS["TEEN"],        # 少年: 5-9级
        GrowthStage.ADULT: PetConfig.STAGE_LEVELS["ADULT"]       # 青年: 10级以上
    }
    
    def __init__(self, name: str = PetConfig.DEFAULT_PET_NAME):
        """
        初始化宠物引擎
        
        Args:
            name: 宠物名字，默认为"Pii"
        """
        self.name = name
        self.stats = PetStats()
        self.state = PetState.IDLE
        self.growth_stage = GrowthStage.BABY  # 默认幼年
        self.personality: list[PersonalityTrait] = []
        
        # 状态变化回调 - 用于通知UI层
        self.on_state_change: Optional[Callable[[PetState], None]] = None
        self.on_stats_change: Optional[Callable[[PetStats], None]] = None
        self.on_level_up: Optional[Callable[[int], None]] = None  # 升级回调
        self.on_stage_change: Optional[Callable[[GrowthStage], None]] = None  # 成长阶段变化
        
        # 记录上次更新时间
        self._last_update = datetime.now()
        self._exp_update_time = datetime.now()  # 经验值更新时间
        
        # 活动量统计（行走/移动距离累计，像素）
        self._activity_count = 0  # 活动量计数器
        self._activity_window_start = datetime.now()  # 统计窗口开始时间
    
    def update(self) -> None:
        """
        状态更新 - 每秒调用一次
        处理属性自然衰减
        """
        now = datetime.now()
        delta_seconds = (now - self._last_update).total_seconds()
        self._last_update = now

        if delta_seconds < PetConfig.UPDATE_MIN_DELTA:
            return

        # 饱食度衰减：睡眠时慢（5分钟-1点），清醒时正常（1分钟-1点）
        if self.state == PetState.SLEEP:
            self.stats.hunger -= self.HUNGER_DECAY_SLEEP_RATE * delta_seconds
        else:
            self.stats.hunger -= self.HUNGER_DECAY_RATE * delta_seconds

        # 心情衰减：饱食度≤35时加速衰减（每分钟2点），否则正常（每分钟1点）
        if self.stats.hunger <= PetConfig.HUNGER_LOW_THRESHOLD:
            self.stats.happiness -= self.HAPPINESS_LOW_HUNGER_DECAY_RATE * delta_seconds
        else:
            self.stats.happiness -= self.HAPPINESS_DECAY_RATE * delta_seconds

        # 精力恢复：睡眠快恢复，清醒慢恢复；交互消耗（由 consume_energy 处理）
        if self.state == PetState.SLEEP:
            self.stats.energy += self.ENERGY_SLEEP_RECOVER_RATE * delta_seconds
        else:
            self.stats.energy += self.ENERGY_AWAKE_RECOVER_RATE * delta_seconds

        # 边界检查
        self.stats._clamp_values()

        # 每分钟获得在线经验
        exp_elapsed = (now - self._exp_update_time).total_seconds()
        if exp_elapsed >= PetConfig.EXP_ONLINE_INTERVAL:
            self.add_exp(self.EXP_PER_MINUTE)
            self._exp_update_time = now

        # 通知UI更新
        if self.on_stats_change:
            self.on_stats_change(self.stats)
    
    def get_exp_for_next_level(self) -> int:
        """计算下一级所需经验（逐级递增）"""
        # 每级所需经验 = 基础值 * 当前等级
        return self.LEVEL_UP_BASE * self.stats.level
    
    def add_exp(self, amount: int) -> bool:
        """
        增加经验值
        
        Args:
            amount: 经验值数量
        
        Returns:
            bool: 是否升级
        """
        self.stats.exp += amount
        
        # 检查是否升级
        exp_needed = self.get_exp_for_next_level()
        if self.stats.exp >= exp_needed:
            self._level_up()
            return True
        return False
    
    def _level_up(self):
        """执行升级"""
        # 扣除升级所需经验
        exp_needed = self.get_exp_for_next_level()
        self.stats.exp -= exp_needed
        self.stats.level += 1
        
        print(f"[成长] 升级！当前等级: {self.stats.level}")
        
        # 检查成长阶段变化
        old_stage = self.growth_stage
        self._update_growth_stage()
        
        # 回调通知
        if self.on_level_up:
            self.on_level_up(self.stats.level)
        
        if old_stage != self.growth_stage and self.on_stage_change:
            self.on_stage_change(self.growth_stage)
    
    def _update_growth_stage(self):
        """根据等级更新成长阶段"""
        level = self.stats.level
        
        if level >= self.STAGE_LEVELS[GrowthStage.ADULT]:
            new_stage = GrowthStage.ADULT
        elif level >= self.STAGE_LEVELS[GrowthStage.TEEN]:
            new_stage = GrowthStage.TEEN
        else:
            new_stage = GrowthStage.BABY
        
        if new_stage != self.growth_stage:
            self.growth_stage = new_stage
            print(f"[成长] 成长阶段变化: {self.growth_stage.display_name}")
    
    def add_activity(self, distance: int) -> None:
        """
        记录活动量（行走/移动距离）
        
        Args:
            distance: 移动距离（像素）
        """
        self._activity_count += distance
        print(f"[活动] 当前活动量: {self._activity_count} 像素")

    def consume_energy(self, amount: float = None) -> None:
        """
        消耗精力值（由交互触发）

        Args:
            amount: 消耗量，默认取 ENERGY_INTERACT_COST
        """
        if amount is None:
            amount = self.ENERGY_INTERACT_COST
        self.stats.energy = max(0.0, self.stats.energy - amount)
        if self.on_stats_change:
            self.on_stats_change(self.stats)
    
    def feed(self) -> bool:
        """
        喂食操作 - 获得经验值
        
        Returns:
            bool: 是否成功喂食
        """
        if self.stats.hunger >= self.MAX_STATS:
            return False  # 已经吃饱了
        
        self.stats.hunger = min(self.MAX_STATS, self.stats.hunger + self.FEED_VALUE)
        self.stats.happiness = min(self.MAX_STATS, self.stats.happiness + self.HAPPINESS_FEED_GAIN)
        
        # 获得经验值
        self.add_exp(self.EXP_PER_FEED)
        
        # 临时进入进食状态
        self._set_state(PetState.EATING)
        
        if self.on_stats_change:
            self.on_stats_change(self.stats)
        
        return True
    
    def pet(self) -> None:
        """抚摸/互动操作 - 获得心情和经验值"""
        self.stats.happiness = min(self.MAX_STATS, self.stats.happiness + self.HAPPINESS_PET_GAIN)
        
        # 获得经验值
        self.add_exp(self.EXP_PER_PET)
        
        if self.on_stats_change:
            self.on_stats_change(self.stats)
    
    def set_state(self, state: PetState) -> None:
        """设置状态（外部调用）"""
        self._set_state(state)
    
    def _set_state(self, state: PetState) -> None:
        """内部状态设置"""
        if self.state != state:
            self.state = state
            self.stats.is_sleeping = (state == PetState.SLEEP)
            
            if self.on_state_change:
                self.on_state_change(state)
    
    def get_status_text(self) -> str:
        """获取状态描述文本"""
        status_parts = []
        
        if self.stats.hunger < PetConfig.HUNGER_CRITICAL_THRESHOLD:
            status_parts.append("饿了")
        elif self.stats.hunger > PetConfig.HUNGER_FULL_THRESHOLD:
            status_parts.append("饱饱的")
        
        if self.stats.energy < PetConfig.ENERGY_LOW_THRESHOLD:
            status_parts.append("困倦")

        if self.stats.happiness < PetConfig.HAPPINESS_LOW_THRESHOLD:
            status_parts.append("不开心")
        elif self.stats.happiness > PetConfig.HAPPINESS_HIGH_THRESHOLD:
            status_parts.append("开心")
        
        if not status_parts:
            status_parts.append("正常")
        
        return "、".join(status_parts)
    
    def get_primary_personality(self) -> PersonalityTrait:
        """获取主性格（第一个性格标签）"""
        if self.personality:
            return self.personality[0]
        return PersonalityTrait.GENTLE  # 默认温柔性格
    
    def get_dialogue(self, context: str) -> str:
        """
        获取当前性格的对话
        
        Args:
            context: 情境 (hungry/petted/idle/greeting)
        
        Returns:
            对应话术
        """
        personality = self.get_primary_personality()
        return PersonalityDialogues.get_dialogue(personality, context)
    
    def to_dict(self) -> dict:
        """完整序列化 - 用于存档"""
        return {
            "name": self.name,
            "stats": self.stats.to_dict(),
            "growth_stage": self.growth_stage.name,
            "personality": [p.value for p in self.personality],
            "state": self.state.name,
            "exp_update_time": self._exp_update_time.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "PetEngine":
        """从字典恢复引擎状态"""
        engine = cls(name=data.get("name", PetConfig.DEFAULT_PET_NAME))
        engine.stats = PetStats.from_dict(data.get("stats", {}))
        
        # 恢复成长阶段
        stage_name = data.get("growth_stage", "BABY")
        try:
            engine.growth_stage = GrowthStage[stage_name]
        except KeyError:
            engine.growth_stage = GrowthStage.BABY
        
        # 恢复性格
        personality_names = data.get("personality", [])
        engine.personality = [
            p for p in PersonalityTrait 
            if p.value in personality_names
        ]
        
        # 恢复状态（SLEEP强制改为IDLE，防止启动就睡觉）
        state_name = data.get("state", "IDLE")
        if state_name == "SLEEP":
            state_name = "IDLE"
        try:
            engine.state = PetState[state_name]
        except KeyError:
            engine.state = PetState.IDLE
        
        # 恢复经验更新时间
        exp_time_str = data.get("exp_update_time")
        if exp_time_str:
            from datetime import datetime
            try:
                engine._exp_update_time = datetime.fromisoformat(exp_time_str)
            except:
                engine._exp_update_time = datetime.now()
        
        return engine


# ============ 模块自测试 ============
if __name__ == "__main__":
    print("=" * 40)
    print("模块测试: core/engine.py")
    print("=" * 40)
    
    # 测试1: 初始化
    print("\n[测试1] 初始化引擎")
    engine = PetEngine("Pii")
    print(f"  宠物名: {engine.name}")
    print(f"  初始饱食度: {engine.stats.hunger}")
    print(f"  初始状态: {engine.state.name}")
    assert engine.stats.hunger == 80.0, "初始饱食度应为80"
    print("  ✓ 初始化通过")
    
    # 测试2: 饱食度衰减
    print("\n[测试2] 饱食度衰减模拟")
    import time
    initial_hunger = engine.stats.hunger
    time.sleep(1.1)  # 等待1秒
    engine.update()
    after_hunger = engine.stats.hunger
    decay = initial_hunger - after_hunger
    print(f"  1秒后饱食度: {initial_hunger} -> {after_hunger} (衰减: {decay:.2f})")
    assert decay >= 1.5, "饱食度应衰减约2点"
    print("  ✓ 衰减逻辑通过")
    
    # 测试3: 喂食操作
    print("\n[测试3] 喂食功能")
    engine.stats.hunger = 20.0  # 先设为饥饿
    result = engine.feed()
    print(f"  喂食前: 20.0, 喂食后: {engine.stats.hunger}")
    assert result == True, "喂食应成功"
    assert engine.stats.hunger == 50.0, "喂食后应为50 (20+30)"
    print("  ✓ 喂食逻辑通过")
    
    # 测试4: 数据序列化
    print("\n[测试4] 数据序列化")
    data = engine.to_dict()
    print(f"  序列化: {json.dumps(data, indent=2, ensure_ascii=False)[:150]}...")
    restored = PetEngine.from_dict(data)
    assert restored.name == engine.name
    assert restored.stats.hunger == engine.stats.hunger
    print("  ✓ 序列化/反序列化通过")
    
    # 测试5: 状态文本
    print("\n[测试5] 状态描述")
    engine.stats.hunger = 10.0
    engine.stats.happiness = 20.0
    status = engine.get_status_text()
    print(f"  状态描述: {status}")
    assert "饿了" in status and "不开心" in status
    print("  ✓ 状态描述通过")
    
    print("\n" + "=" * 40)
    print("所有测试通过! 引擎模块正常")
    print("=" * 40)
