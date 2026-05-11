# DesktopPet - 桌面宠物 Pii

一只生活在你屏幕上的数字伙伴，会发呆、卖萌、打盹、行走，还能感知你的操作节奏。

---

## 快速开始

**环境要求**
- Python 3.10+
- Windows 系统

**安装依赖**
```bash
pip install PySide6>=6.5.0 pynput
```

**启动**
```bash
python main.py
```

首次启动弹出性格选择与宠物命名窗口，之后 Pii 常驻在屏幕右下角。

---

## 项目结构

```text
desktopet/
├── assets/                     # 资源文件夹
│   ├── animations/             # 存放不同状态的序列帧
│   │   ├── idle/               # 发呆 (idle_0.png, idle_1.png, ...)
│   │   ├── maimeng/            # 卖萌 (鼠标悬停触发)
│   │   ├── oneeyes/            # 独眼 (点击触发)
│   │   ├── hungry/             # 饥饿
│   │   ├── sleep/              # 睡觉
│   │   ├── lie/                # 躺下（正序→倒序→保持→重复）
│   │   ├── tired/              # 疲惫（播放一次停在末帧）
│   │   ├── walk/               # 行走
│   │   └── eating/             # 进食
│   └── sounds/                 # 存放音效
├── core/                       # 逻辑核心
│   ├── config.py               # 集中配置 (PetConfig，130+ 常量)
│   ├── engine.py               # 宠物属性与状态管理 (PetEngine, PetState, PetStats)
│   ├── enums.py                # 公共枚举：PetState / GrowthStage / PersonalityTrait
│   ├── behavior.py             # 睡眠/唤醒/行为控制 (BehaviorController)
│   ├── state_resolver.py       # 动画状态解析 (resolve_animation_state)
│   ├── perception.py           # 键盘频率监听 (ActivityMonitor)
│   └── database.py             # 存档读写逻辑 (JSON)
├── ui/                         # 界面层
│   ├── main_window.py          # 透明窗体、信号连接、定时器调度
│   ├── animation_player.py     # 动画播放器（帧切换、强制动画生命周期）
│   ├── interaction_controller.py # 鼠标交互控制器（点击/拖拽/悬停）
│   ├── bubble_manager.py       # 气泡统一调度（优先级、冷却、定位）
│   └── components.py           # 对话气泡(SpeechBubble)、浮动文字、托盘图标
├── data/
│   └── dialogues.py            # 对话文案库 (PersonalityDialogues)
├── requirements.txt            # 依赖包列表
└── main.py                     # 程序入口 (信号连接、CrossThreadSignals)
```

---

## 架构设计

采用分层架构，职责清晰：

```
┌─────────────────────────────────────────┐
│  main.py  入口层：组装对象、绑定信号     │
└────────────────┬────────────────────────┘
                 │
   ┌─────────────┴─────────────┐
   │                           │
┌──▼──────────────┐   ┌───────▼────────────┐
│  Model 层       │   │  View 层            │
│  engine.py      │   │  main_window.py     │
│  PetStats       │   │  animation_player.py│
│  PetState/Stage │   │  components.py      │
│  growth system  │   │                     │
└──────┬──────────┘   └───────┬────────────┘
       │                      │
┌──────▼──────────┐   ┌───────▼────────────┐
│  Core 层        │   │  Controller 层      │
│  config.py      │   │  interaction_ctrl   │
│  state_resolver │   │  behavior.py        │
│  perception.py  │   │  bubble_manager.py  │
│  database.py    │   │                     │
└─────────────────┘   └────────────────────┘
```

**模块职责说明**

| 模块 | 职责 |
|------|------|
| `engine.py` | 状态机（IDLE/WALK/SLEEP/EATING/DRAGGING）、数值衰减、经验等级、成长阶段 |
| `config.py` | 130+ 可调参数集中管理：阈值、衰减率、冷却时间、经验倍率 |
| `enums.py` | 公共枚举，避免 engine 与 dialogues 之间循环导入 |
| `state_resolver.py` | 动画优先级判定：强制动画 > 悬停动画 > 饥饿覆盖 > 引擎状态 |
| `behavior.py` | 行为调度：自动动作选择、睡眠触发与唤醒、动作权重 |
| `perception.py` | pynput 监听键盘活跃度，高强度打字时触发鼓励气泡 |
| `database.py` | JSON 存档持久化，自动存档（每30秒）+ 退出存档 |
| `animation_player.py` | 动画资源扫描加载、序列帧播放、循环暂停、强制/悬停动画 |
| `interaction_controller.py` | 鼠标点击、拖拽、悬停判定，交互冷却（0.5秒） |
| `bubble_manager.py` | 气泡提示优先级调度（升级 > 状态低 > 交互 > 鼓励 > 普通） |
| `dialogues.py` | 4种性格对话库 + 智能上下文文案（时间/状态/里程碑） |

---

## 功能清单

### 基础交互

| 操作 | 触发动画 | 冷却 | 说明 |
|------|---------|------|------|
| 鼠标悬浮 | maimeng | 无 | 进入触发卖萌，离开恢复（lie/tired 期间例外） |
| 左键点击（无移动） | oneeyes | 1轮+0.5秒 | 点击增加经验值 |
| 左键拖拽（>5px移动） | 吸附+oneeyes | 1轮+0.5秒 | 拖拽后吸附到最近边缘 |
| 右键 | 上下文菜单 | 无 | 显示状态/喂食/退出 |
| 冷却期内点击 | 提示"太快了" | - | 仅点击有冷却 |

**交互阻止**（任一满足即拒绝，喂食除外）：
- 饱食度 <= 15 → 气泡"快喂我吃的才能互动！"
- 精力 <= 1 → 气泡"太累了...精力不足"

**睡眠保护**：睡眠中无法被随意打断，尝试唤醒失败时显示对应拒绝原因气泡。

### 数值系统

**属性**

| 属性 | 清醒衰减 | 睡眠衰减 | 恢复方式 |
|------|---------|---------|---------|
| 饱食度 | 1点/分钟 | 1点/5分钟 | 喂食(+30) |
| 心情值 | 1点/分钟（饥饿时2点/分钟） | 同清醒 | 抚摸(+1)、喂食(+5) |
| 精力值 | 清醒恢复+1/分钟 | 睡眠恢复+10/分钟 | 交互消耗-2/次 |

**低数值行为**

| 属性 | 阈值 | 行为 | 动画 |
|------|------|------|------|
| 饱食度 <= 15 | 饥饿 | 覆盖动画、心情加速衰减 | hungry |
| 饱食度 <= 1 | 极饿 | 强制睡眠，无法交互 | sleep |
| 心情值 <= 35 | 不开心 | 触发 lie 动画、邀玩气泡 | lie |
| 精力 <= 20 | 疲劳 | 触发 tired 动画、气泡提醒 | tired |
| 精力 <= 1 | 极疲劳 | 强制睡眠，无法交互 | sleep |

### 成长系统

- 经验值：喂食 +10，抚摸 +5，在线每分钟 +1
- 升级所需经验：基础值(100) x 当前等级（逐级递增）
- 成长阶段：幼年(BABY, Lv.1-4) → 少年(TEEN, Lv.5-9) → 青年(ADULT, Lv.10+)

### 睡眠系统

**睡眠触发条件**（任一满足即进入睡眠）：

| 触发条件 | 阈值 | 状态要求 |
|---------|------|---------|
| 精力不足 | <= 1 | 任意状态（强制睡眠） |
| 饱食度不足 | <= 1 | 任意状态（强制睡眠） |
| 长时间无互动 | >= 120 秒 | 仅 IDLE 状态 |

**唤醒条件**（需同时满足）：精力 > 1、饱食度 > 1、距上次互动 >= 5 秒。

### 动画系统

- PNG 序列帧，24fps 主定时器，支持多帧动画和单帧资源
- 9 种动画状态：idle / maimeng / oneeyes / hungry / sleep / eating / walk / lie / tired
- 动画优先级：强制动画 > 悬停动画 > 饥饿覆盖 > 引擎状态
- lie 生命周期：正序播放 → 倒序播放 → 保持 → 30-60秒后重复
- tired 动画：播放一次停在末帧，精力恢复后自动清除

### 智能互动气泡

点击小猫时的反馈不再是固定文案，而是根据 **时间 + 宠物状态 + 成长 + 性格** 多维度智能选择。

**条件优先级：**

| 优先级 | 维度 | 条件 | 示例 |
|--------|------|------|------|
| 1 | 时间-深夜 | 22:00-5:00 | "这么晚了还不睡？陪你熬夜~" |
| 2 | 状态-饥饿 | hunger <= 30 | "摸我不如喂我...肚子好饿" |
| 3 | 状态-精力低 | energy <= 40 | "有点累了...但被你摸还是很开心" |
| 4 | 状态-心情高 | happiness >= 80 | "今天超开心！因为有你陪着~" |
| 5 | 时间-早晨 | 6:00-9:00 | "早上好！今天也一起加油吧~" |
| 6 | 时间-午后 | 12:00-14:00 | "午饭吃了吗？别忘了吃饭哦~" |
| 7 | 成长-里程碑 | 每10天 | "我们已经在一起N天了呢~" |

命中条件后 50% 概率使用条件文案，50% 降级到通用性格文案。

### 智能感知

- pynput 全局键盘监听（后台线程，通过 Qt 信号安全派发到主线程）
- 1 分钟内键盘敲击超过 100 次 → 触发鼓励气泡
- 长时间无操作（120秒）→ 自动进入睡眠

### 对话气泡系统

- 支持多方向箭头，根据宠物贴边位置自动调整
- 多显示器支持：使用当前屏幕的可用区域计算边界
- 智能定位：确保不超出屏幕边界（含任务栏）
- 统一调度：优先级、冷却、位置跟随

### 性格选择

- 4 种性格：活泼 / 温柔 / 慵懒 / 好奇
- 性格影响：对话语气、上下文互动文案

### 数据持久化

- 存档位置：`%APPDATA%\DesktopPet\pii_save.json`
- 自动存档（每30秒）+ 退出存档
- 恢复时 SLEEP 状态强制改为 IDLE，避免启动即睡

---

## 关键技术点

**透明置顶窗口**
```python
self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
self.setAttribute(Qt.WA_TranslucentBackground)
self.setAttribute(Qt.WA_ShowWithoutActivating)
```

**信号系统**
- `PetSignals`：属性更新、状态变化、喂食请求、经验获取
- `InteractionController`：点击/拖拽/悬停/冷却，通过信号通知主窗口
- `CrossThreadSignals`：pynput 后台线程安全派发到主线程

**状态解析**
- `state_resolver.resolve_animation_state()` 是决定显示哪个动画的唯一依据
- 优先级：`force_animation` > `hover_animation` > 饥饿覆盖 > 引擎状态映射

---

## 开发动效素材

使用 AI 生成角色基础图片和动作视频，再通过 ffmpeg 逐帧拆出 PNG 序列帧：

```bash
# 白色背景视频按帧数转 png（去白底 + 保留透明通道）
ffmpeg -i walk1.mov -vf "colorkey=white:0.05:0.02,format=rgba" walk_%03d.png
```

---

## 运行原理

**启动流程**

```
main.py
  -> QApplication 初始化
  -> PetDatabase 加载存档
  -> 有存档 -> PetEngine.from_dict() 恢复
     无存档 -> PersonalitySelector 选择性格/命名
  -> PetMainWindow 创建主窗口
  -> SpeechBubble + BubbleManager 创建气泡系统
  -> UserActivityMonitor 启动键盘监听
  -> 进入事件循环
```

**主循环（每秒触发）**

```
engine.update()
  -> 饱食度/心情/精力 衰减或恢复
  -> 检查升级
  -> 通知 UI 更新

behavior.check_sleep()
  -> 精力/饱食度不足 -> 强制睡眠
  -> 连续无操作超时 -> 触发睡眠
  -> 精力疲劳 -> 触发 tired 动画提醒

animation_player._on_animation_frame()
  -> 按帧率切换动画帧，发射重绘信号
```

---

## 注意事项

1. **性能优化**：动画刷新率约24FPS；感知系统已移除鼠标移动监听，改用主线程定时器
2. **线程安全**：`pynput` 回调在后台线程，必须通过 `CrossThreadSignals` 派发到主线程
3. **配置管理**：所有调参常量集中在 `core/config.py`，禁止硬编码魔法数字
4. **资源路径**：打包时需使用 `sys._MEIPASS` 处理绝对路径

---

## 待实现

- 音效系统
- 装扮/皮肤系统
- 打包为 .exe
- AI 驱动聊天（接入大语言模型）

---

## 许可证

本项目仅供学习和个人使用。
