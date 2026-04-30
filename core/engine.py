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


class PetState(Enum):
    """宠物状态枚举"""
    IDLE = auto()       # 静止/发呆
    WALK = auto()       # 行走
    SLEEP = auto()      # 睡觉
    EATING = auto()     # 进食中
    DRAGGING = auto()   # 被拖拽中


class GrowthStage(Enum):
    """成长阶段枚举"""
    BABY = auto()       # 幼年 - 依赖、撒娇多
    TEEN = auto()       # 少年 - 好奇、偶尔倔强
    ADULT = auto()      # 青年 - 责任感与陪伴感强
    
    @property
    def display_name(self) -> str:
        """显示名称"""
        names = {
            GrowthStage.BABY: "幼年",
            GrowthStage.TEEN: "少年",
            GrowthStage.ADULT: "青年"
        }
        return names.get(self, "未知")


class PersonalityTrait(Enum):
    """性格标签枚举"""
    PLAYFUL = "活泼"     # 喜欢玩耍，互动频率高
    GENTLE = "温柔"      # 温顺，撒娇多
    LAZY = "慵懒"        # 容易困，移动少
    CURIOUS = "好奇"     # 探索欲强


class PersonalityDialogues:
    """
    性格对话库
    根据不同性格返回不同风格的话术
    """
    
    DIALOGUES = {
        PersonalityTrait.PLAYFUL: {
            "hungry": ["饿死啦饿死啦！快给我吃的！", "肚子咕咕叫~我要吃饭！", "主人主人，零食时间到啦！"],
            "petted": ["哈哈好痒！再来再来！", "耶！主人陪我玩啦！", "蹭蹭~最喜欢主人了！"],
            "idle": ["无聊死了...来玩嘛~", "那边有什么？让我看看！", "我在数蚂蚁，1只2只..."],
            "greeting": ["主人你来啦！想我了吗？", "耶！新的一天开始咯！", "今天也要元气满满！"]
        },
        PersonalityTrait.GENTLE: {
            "hungry": ["那个...我有点饿了...", "如果可以的话，能给我一点吃的吗？", "肚子有点不舒服..."],
            "petted": ["好温暖...", "被主人摸摸好幸福...", "最喜欢主人的手了..."],
            "idle": ["静静陪伴在主人身边，真好...", "阳光好舒服...", "想就这样一直陪着你..."],
            "greeting": ["欢迎回来，我一直在等你...", "能见到你真好...", "今天也辛苦了..."]
        },
        PersonalityTrait.LAZY: {
            "hungry": ["饿了...但是不想动...", "有没有食物自动飞到我嘴里...", "吃饭好麻烦..."],
            "petted": ["呼噜...好困...", "摸完让我继续睡...", "嗯...还行吧..."],
            "idle": ["ZZZ...", "睡觉是最好的...", "动一动好累..."],
            "greeting": ["哦...你来了...", "让我再睡五分钟...", "早...早安..."]
        },
        PersonalityTrait.CURIOUS: {
            "hungry": ["我闻到食物的味道了！在哪？", "让我研究一下这个食物的成分...", "肚子在发出奇怪的声音！"],
            "petted": ["这就是人类的抚摸行为吗？", "触觉反馈很有趣！", "我的毛发摩擦系数如何？"],
            "idle": ["那是什么？让我看看！", "为什么云会动？", "这个世界的奥秘太多了..."],
            "greeting": ["今天有什么新发现？", "我又学会了一招！", "这个世界真奇妙！"]
        }
    }
    
    @classmethod
    def get_dialogue(cls, personality: PersonalityTrait, context: str, index: int = None) -> str:
        """
        获取性格对话
        
        Args:
            personality: 性格类型
            context: 情境 (hungry/petted/idle/greeting)
            index: 指定索引，None则随机
        
        Returns:
            对应话术
        """
        import random
        
        dialogues = cls.DIALOGUES.get(personality, {}).get(context, ["喵~"])
        if index is not None:
            return dialogues[index % len(dialogues)]
        return random.choice(dialogues)
    
    @classmethod
    def get_random_idle_line(cls, personality: PersonalityTrait) -> str:
        """获取随机的idle台词"""
        return cls.get_dialogue(personality, "idle")
    
    @classmethod
    def get_greeting(cls, personality: PersonalityTrait) -> str:
        """获取欢迎语"""
        return cls.get_dialogue(personality, "greeting")


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
    hunger: float = 80.0        # 饱食度，默认80
    happiness: float = 70.0     # 心情值
    energy: float = 100.0       # 精力值
    hygiene: float = 100.0      # 清洁度
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
            hunger=data.get("hunger", 80.0),
            happiness=data.get("happiness", 70.0),
            energy=data.get("energy", 100.0),
            hygiene=data.get("hygiene", 100.0),
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
    HUNGER_DECAY_RATE_BASE = 1.0 / 60  # 基础饱食度每秒衰减值（每分钟掉1点）
    HUNGER_DECAY_ACTIVE = 2.5 / 60     # 活跃状态下的额外衰减（每分钟额外掉2.5点）
    HAPPINESS_DECAY_RATE = 0.5      # 心情每秒衰减值
    ENERGY_DECAY_RATE = 0.3         # 精力每秒衰减值
    
    FEED_VALUE = 30.0               # 每次喂食增加的饱食度
    MAX_STATS = 100.0               # 属性最大值
    
    # 活动量统计（用于计算消耗）
    ACTIVITY_DECAY_THRESHOLD = 100  # 活动量阈值，超过则认为"运动量大"
    
    # 成长系统常量
    EXP_PER_FEED = 10               # 喂食获得经验
    EXP_PER_PET = 5                 # 抚摸获得经验
    EXP_PER_MINUTE = 1              # 每分钟在线获得经验
    LEVEL_UP_BASE = 100             # 每级所需基础经验（逐级增加）
    
    # 成长阶段解锁等级
    STAGE_LEVELS = {
        GrowthStage.BABY: 1,        # 幼年: 1-4级
        GrowthStage.TEEN: 5,        # 少年: 5-9级
        GrowthStage.ADULT: 10       # 青年: 10级以上
    }
    
    def __init__(self, name: str = "Pii"):
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
        处理属性自然衰减，根据活动量调整饥饿消耗
        """
        now = datetime.now()
        delta_seconds = (now - self._last_update).total_seconds()
        self._last_update = now
        
        if delta_seconds < 0.1:
            return
        
        # 检查活动量窗口（每60秒重置一次统计）
        activity_window_seconds = (now - self._activity_window_start).total_seconds()
        if activity_window_seconds > 60:
            self._activity_count = 0
            self._activity_window_start = now
        
        # 计算饥饿衰减率：基础值 + 根据活动量调整
        # 活动量大（行走多）→ 消耗快，符合常规
        is_active = self._activity_count > self.ACTIVITY_DECAY_THRESHOLD
        hunger_decay = self.HUNGER_DECAY_RATE_BASE
        if is_active:
            hunger_decay += self.HUNGER_DECAY_ACTIVE  # 活跃状态额外消耗
        
        # 饱食度持续下降
        self.stats.hunger -= hunger_decay * delta_seconds
        
        # 饿了影响心情
        if self.stats.hunger < 30:
            self.stats.happiness -= self.HAPPINESS_DECAY_RATE * delta_seconds * 2
        else:
            self.stats.happiness -= self.HAPPINESS_DECAY_RATE * delta_seconds
        
        # 精力自然衰减
        if not self.stats.is_sleeping:
            self.stats.energy -= self.ENERGY_DECAY_RATE * delta_seconds
        else:
            # 睡觉恢复精力
            self.stats.energy += 5.0 * delta_seconds
        
        # 边界检查
        self.stats._clamp_values()
        
        # 每分钟获得在线经验
        exp_elapsed = (now - self._exp_update_time).total_seconds()
        if exp_elapsed >= 60:
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
    
    def feed(self) -> bool:
        """
        喂食操作 - 获得经验值
        
        Returns:
            bool: 是否成功喂食
        """
        if self.stats.hunger >= self.MAX_STATS:
            return False  # 已经吃饱了
        
        self.stats.hunger = min(self.MAX_STATS, self.stats.hunger + self.FEED_VALUE)
        self.stats.happiness = min(self.MAX_STATS, self.stats.happiness + 5.0)
        
        # 获得经验值
        self.add_exp(self.EXP_PER_FEED)
        
        # 临时进入进食状态
        self._set_state(PetState.EATING)
        
        if self.on_stats_change:
            self.on_stats_change(self.stats)
        
        return True
    
    def pet(self) -> None:
        """抚摸/互动操作 - 获得经验值"""
        self.stats.happiness = min(self.MAX_STATS, self.stats.happiness + 10.0)
        
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
        
        if self.stats.hunger < 20:
            status_parts.append("饿了")
        elif self.stats.hunger > 90:
            status_parts.append("饱饱的")
        
        if self.stats.energy < 20:
            status_parts.append("困倦")
        
        if self.stats.happiness < 30:
            status_parts.append("不开心")
        elif self.stats.happiness > 80:
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
        engine = cls(name=data.get("name", "Pii"))
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
