# 桌面宠物项目开发文档

## 1. 项目概述
本项目旨在开发一个基于 Python 的 AI 桌面伙伴“Pii”。它不仅是一个漂浮在桌面上的图标，而是一个具有**真实桌面交互**、**性格成长系统**和**操作感知能力**的“数字灵魂”。

## 2. 开发环境准备
新手在开始前需确保安装以下环境：
* **语言**：Python 3.10 或更高版本。
* **UI 框架**：`PySide6`（用于实现高性能的透明窗体）。
* **监听库**：`pynput`（用于监听用户的键盘/鼠标操作频率）。

## 3. 项目结构 (Directory Structure)
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
│   ├── behavior.py             # 睡眠/唤醒/行为控制 (BehaviorController)
│   ├── state_resolver.py       # 动画状态解析 (resolve_animation_state)
│   ├── perception.py           # 键盘频率监听 (ActivityMonitor)
│   └── database.py             # 存档读写逻辑 (JSON)
├── ui/                         # 界面层
│   ├── main_window.py          # 透明窗体、信号连接、定时器调度
│   ├── animation_player.py     # 动画播放器（帧切换、强制动画生命周期）
│   ├── interaction_controller.py # 鼠标交互控制器（点击/拖拽/悬停）
│   ├── bubble_manager.py       # 气泡统一调度（优先级、冷却、定位）
│   └── components.py           # 对话气泡(SpeechBubble)、托盘图标
├── data/
│   └── dialogues.py            # 对话文案库 (PersonalityDialogues)
├── requirements.txt            # 依赖包列表
└── main.py                     # 程序入口 (信号连接、CrossThreadSignals)
```

## 4. 核心架构设计
* **模型层**：`engine.py`（属性与状态管理）+ `behavior.py`（睡眠/唤醒逻辑）+ `state_resolver.py`（动画状态决策）
* **视图层**：`main_window.py`（窗口与信号调度）+ `animation_player.py`（动画播放）+ `components.py`（气泡与托盘）
* **控制层**：`interaction_controller.py`（鼠标交互）+ `bubble_manager.py`（气泡调度）+ `perception.py`（活动感知）
* **入口**：`main.py` 通过 Qt 信号槽连接所有组件，`CrossThreadSignals` 处理 pynput 后台线程安全

---

## 5. 已实现功能清单

### 5.1 透明置顶窗口 
- 无边框、置顶、不在任务栏显示、不获取焦点
- 透明背景，宠物图片无白边
- 窗口固定尺寸 128×128
- 默认位置：屏幕右下角（任务栏上方）

### 5.2 动画系统 
- **播放器**：`AnimationPlayer`，主定时器 24fps，管理所有帧切换和动画生命周期
- **动画状态**：
  - `idle` - 发呆（默认状态，循环播放）
  - `maimeng` - 卖萌（鼠标悬停触发，离开恢复）
  - `oneeyes` - 独眼（左键点击/拖拽触发）
  - `hungry` - 饥饿（饱食度≤15时自动覆盖）
  - `sleep` - 睡觉（睡眠状态，循环不暂停）
  - `eating` - 进食
  - `walk` - 行走（自动动作触发）
  - `lie` - 躺下（心情≤35触发，特殊生命周期，见5.13节）
  - `tired` - 疲惫（精力≤20触发，见5.12节）
- **动画优先级**（从高到低）：`force_animation`（lie/tired/oneeyes）> `hover_animation`（maimeng）> 饥饿覆盖（hunger≤15）> 引擎状态映射
- **状态解析**：`state_resolver.resolve_animation_state()` 是决定显示哪个动画的唯一依据
- **循环暂停**：普通动画完成1个循环后暂停5秒；sleep 循环不暂停；lie 播完一轮后进入倒序→保持→重复
- **防重入**：`start_force_animation()` 对 lie/tired 有去重守卫，已在播放或保持中时跳过

### 5.3 交互系统 
- **控制器**：`InteractionController`，处理所有鼠标事件，通过信号通知主窗口

| 操作 | 触发动画 | 冷却 | 说明 |
|------|---------|------|------|
| 鼠标悬浮 | maimeng | 无 | 进入触发卖萌，离开恢复（lie/tired 期间例外） |
| 左键点击（无移动） | oneeyes | 1轮+0.5秒 | 点击增加经验值 |
| 左键拖拽（>5px移动） | 吸附+oneeyes | 1轮+0.5秒 | 拖拽后吸附到最近边缘 |
| 右键 | 上下文菜单 | 无 | 显示状态/喂食/退出 |
| 冷却期内点击 | 提示"太快了" | - | 仅点击有冷却 |

- **交互阻止**（任一满足即拒绝，喂食除外）：
  - 饱食度 ≤ 15 → 气泡"快喂我吃的才能互动！"
  - 精力 ≤ 1 → 气泡"太累了...精力不足"
- **lie/tired 保护**：lie/tired 动画期间，鼠标进入不触发卖萌（lie 显示"需要主人抚摸"气泡），鼠标离开不重置动画
- **拖拽距离判断**：用窗口位置变化区分点击和拖拽
- **吸附逻辑**：计算到四边距离，缓动移到最近边缘

### 5.4 睡眠系统 
- **控制器**：`BehaviorController`，每秒由 `_on_update()` 调用 `check_sleep()`

**睡眠触发条件（任一满足即进入睡眠）：**

| 触发条件 | 阈值 | 状态要求 |
|---------|------|---------|
| 精力不足 | ≤ 1 | 任意状态（强制睡眠） |
| 饱食度不足 | ≤ 1 | 任意状态（强制睡眠） |
| 长时间无互动 | ≥ 120 秒 | 仅 IDLE 状态 |

**唤醒条件（需同时满足）：**
1. 精力 > 1
2. 饱食度 > 1
3. 距上次互动 ≥ 5 秒

**睡眠中交互被拒绝时，显示对应气泡：**
- `energy_low` → "太累了...精力不足，让我再睡会儿吧"
- `hunger_low` → "好饿...没力气起来，先喂我点吃的吧"
- `just_woke` → "刚躺下...让我再休息一下"

- **动画**：sleep 序列帧循环播放不暂停
- **防误触发**：启动时初始化互动时间为当前时间；存档恢复时 SLEEP 强制改为 IDLE
- **状态清理**：进入睡眠时清除所有强制动画状态（lie/tired/oneeyes），确保 sleep 动画正确显示

### 5.5 自动动作系统 
- **定时器**：每15秒尝试触发（正态分布间隔，10-20秒之间）
- **动作权重**：
  - 85% - 发呆眨眼
  - 15% - 吸附到边缘
  - （walk/jump/roll/play_cute 已禁用）
- **条件**：仅在 IDLE 状态且不在拖拽时触发

### 5.6 对话气泡系统 
- **SpeechBubble** 组件，支持多方向箭头
- **箭头方向**：根据宠物贴边位置自动调整
  - 贴右边 → 气泡左上角，箭头右下（`right-down`）
  - 贴左边 → 气泡右上角，箭头左下（`left-down`）
  - 支持对角线箭头方向
- **跟随宠物**：宠物移动时气泡跟随更新位置
- **智能定位**：不超出屏幕边界
- **自动隐藏**：显示后按设定时长自动隐藏
- **智能互动气泡**：`PersonalityDialogues.get_contextual_dialogue()` 根据时间/状态/成长多维度选择点击文案，详见 5.15 节

### 5.7 性格选择系统 
- **PersonalitySelector** 对话框
- **宠物命名**：输入框，默认名"Pii"
- **性格标签**：活泼/温柔/幽默/傲娇/好奇/安静，互斥对立
- **性格影响**：对话语气、行为概率权重

### 5.8 养成与数值系统
- **属性**：饱食度(0-100)、心情值(0-100)、精力值(0-100)、整洁度(0-100)、经验值、等级
- **成长阶段**：幼年(BABY, Lv.1-4) → 少年(TEEN, Lv.5-9) → 青年(ADULT, Lv.10+)
- **经验来源**：点击(+5)、喂食(+10)、每分钟在线(+1)
- **等级公式**：每级所需经验 = 100 × 等级

#### 数值衰减/恢复

| 属性 | 清醒衰减 | 睡眠衰减 | 恢复方式 |
|------|---------|---------|---------|
| 饱食度 | 1点/分钟 | 1点/5分钟 | 喂食(+30) |
| 心情值 | 1点/分钟（饥饿时2点/分钟） | 同清醒 | 抚摸(+1)、喂食(+5) |
| 精力值 | 清醒恢复+1/分钟 | 睡眠恢复+10/分钟 | 交互消耗-2/次 |

#### 低数值行为总览

| 属性 | 阈值 | 行为 | 动画 |
|------|------|------|------|
| 饱食度 ≤ 15 | 饥饿 | 覆盖动画、心情加速衰减 | hungry |
| 饱食度 ≤ 1 | 极饿 | 强制睡眠，无法交互 | sleep |
| 心情值 ≤ 35 | 不开心 | 触发 lie 动画、邀玩气泡 | lie |
| 精力 ≤ 20 | 疲劳 | 触发 tired 动画、气泡提醒 | tired |
| 精力 ≤ 1 | 极疲劳 | 强制睡眠，无法交互 | sleep |

详细说明见 5.4（睡眠系统）、5.12（tired 状态）、5.13（lie 生命周期）。

### 5.9 感知系统 
- **ActivityMonitor**：`pynput` 监听键盘敲击频率
- **性能优化**：移除鼠标移动监听（1000Hz 导致系统卡顿），使用 `time.monotonic()` 替代 `datetime.now()`（14x 性能提升）
- **线程安全**：`pynput` 回调在后台线程，通过 `CrossThreadSignals`（QObject）以 Qt 信号派发到主线程，禁止在后台线程创建 Qt 对象
- **窗口检测**：`check_window()` 由主线程 1 秒定时器调用，避免锁竞争
- **打字激励**：1 分钟内键盘敲击超过 100 次视为高强度打字，触发鼓励气泡
- **冷却机制**：高强度打字提醒冷却 300 秒，避免重复打扰
- **空闲检测**：5 秒内操作少于 10 次视为空闲

### 5.10 数据持久化 
- **存档位置**：`%APPDATA%\DesktopPet\pii_save.json`
- **存档内容**：名称、属性、成长阶段、性格、状态、经验更新时间
- **自动存档**：30秒防抖间隔，避免频繁IO
- **退出存档**：程序退出时强制保存
- **状态恢复**：SLEEP状态强制恢复为IDLE

### 5.11 系统托盘 
- **QSystemTrayIcon**：最小化到托盘
- **托盘菜单**：显示/隐藏、退出

### 5.12 Tired 状态（精力疲劳）
- **触发**：精力 ≤ 20 且 > 1（强制睡眠阈值），由 `check_sleep()` 每秒检测并触发 `on_tired` 回调
- **动画**：`tired` 序列帧播放一次，停在末帧，不循环
- **行为保护**：
  - 不触发卖萌（鼠标进入/离开不影响动画）
  - 不触发自动动作（walk/snap_to_edge 等跳过）
  - 不被其他强制动画打断
- **恢复**：精力恢复到 > 20 时，`_on_update()` 自动清除 tired 状态，恢复 idle 动画
- **气泡**：随机显示 5 条疲劳提醒文案（如"有点累了...让我休息一下~"），冷却 60 秒

### 5.13 Lie 动画生命周期
- **触发**：心情 ≤ 35 时，`on_stats_change` 回调中调用 `start_force_animation("lie")`
- **生命周期**：
  1. **正序播放**：播放 lie 序列帧 1 轮
  2. **倒序播放**：从最后一帧逐帧回到第 1 帧（`_lie_reverse` 状态）
  3. **保持**：停在第 1 帧（`_lie_hold` 状态）
  4. **重复**：30-60 秒随机间隔后重新播放（`_lie_repeat_timer` 专用定时器）
- **防重入**：`on_stats_change` 每秒触发，lie 已在播放或保持中时跳过，防止动画重置
- **交互保护**：
  - 鼠标进入：不触发卖萌，显示"需要主人抚摸"气泡（冷却 3 秒）
  - 鼠标离开：不重置动画
  - 不触发自动动作
- **与其他状态的关系**：
  - 睡眠触发时清除 lie 所有状态（`_force_animation`、`_lie_hold`、`_lie_reverse`）
  - lie 期间新的强制动画（如 oneeyes）会清除 lie 状态

### 5.14 配置集中化
- **位置**：`core/config.py` 的 `PetConfig` 类
- **原则**：所有调参常量集中在此，其他文件禁止硬编码魔法数字
- **分类**：应用基础、窗口动画、鼠标交互、吸附、对话气泡、自动动作、动画帧、睡眠唤醒、占位图、引擎属性、经验等级、阈值、感知系统、浮动文字

#### 关键阈值一览

| 参数 | 值 | 说明 |
|------|---|------|
| WAKE_ENERGY_THRESHOLD | 1 | 精力≤1 强制睡眠 |
| WAKE_HUNGER_THRESHOLD | 1 | 饱食度≤1 强制睡眠 |
| ENERGY_TIRED_THRESHOLD | 20 | 精力≤20 触发 tired |
| HUNGER_LOW_THRESHOLD | 15 | 饱食度≤15 饥饿动画/交互阻止 |
| HAPPINESS_LOW_THRESHOLD | 35 | 心情≤35 触发 lie |
| SLEEP_IDLE_TIME | 120 | 无互动 120 秒进入睡眠 |
| TYPING_THRESHOLD | 100 | 1 分钟键盘敲击阈值 |
| TYPING_INTENSIVE_COOLDOWN | 300 | 打字提醒冷却（秒） |
| LIE_REPEAT_MIN_MS | 30000 | lie 重复最小间隔（毫秒） |
| LIE_REPEAT_MAX_MS | 60000 | lie 重复最大间隔（毫秒） |

### 5.15 智能互动气泡系统
- **触发**：点击小猫时 `show_petted(engine)` 调用 `PersonalityDialogues.get_contextual_dialogue()`
- **核心逻辑**：按优先级检查 7 个维度条件，命中后 50% 概率使用条件文案，50% 降级到通用 petted 文案
- **数据结构**：`CONTEXT_DIALOGUES` 字典，4种性格 × 7个条件 × 3-4条文案

**条件优先级：**

| 优先级 | 条件 key | 触发条件 | 配置常量 |
|--------|----------|---------|---------|
| 1 | late_night | 22:00-5:00 | - |
| 2 | hungry | hunger ≤ 30 | PETTED_HUNGER_THRESHOLD |
| 3 | tired | energy ≤ 40 | PETTED_ENERGY_THRESHOLD |
| 4 | happy | happiness ≥ 80 | HAPPINESS_HIGH_THRESHOLD |
| 5 | morning | 6:00-9:00 | - |
| 6 | afternoon | 12:00-14:00 | - |
| 7 | milestone | age_days > 0 且 age_days % 10 == 0 | PETTED_MILESTONE_INTERVAL |

- **概率控制**：`PETTED_CONTEXT_CHANCE = 0.5`，命中条件后有 50% 概率使用，避免特殊文案过于频繁
- **文案格式化**：支持 `{name}`、`{days}`、`{level}` 占位符
- **兜底**：无条件命中或概率未命中时，使用现有 `DIALOGUES[personality]["petted"]` 文案池

---

## 6. 关键技术点实现

### 6.1 透明置顶窗口
```python
# 窗口属性设置
self.setWindowFlags(
    Qt.FramelessWindowHint |      # 无边框
    Qt.WindowStaysOnTopHint |     # 置顶
    Qt.Tool                        # 不在任务栏显示
)
self.setAttribute(Qt.WA_TranslucentBackground)  # 透明背景
self.setAttribute(Qt.WA_ShowWithoutActivating)  # 不抢焦点
```

### 6.2 动画帧切换
- `_animation_timer`：约42ms一帧（~24FPS）
- 多帧动画：sleep每10帧(400ms)切换，其他每6帧(250ms)切换
- 单帧动画：每12帧(500ms)重绘，产生呼吸缩放效果
- `_get_current_pixmap()`：按优先级（强制>悬停>引擎状态）获取当前帧

### 6.3 拖拽与吸附
- `mousePressEvent`：记录窗口初始位置 `_drag_start_window_pos`
- `mouseReleaseEvent`：用窗口位移判断是否真正拖拽（>10px）
- `_action_snap_to_edge`：计算到四边距离，缓动移动到最近边缘
- `_start_move_animation`：60fps位移动画，支持缓动函数

### 6.4 信号系统
```python
class PetSignals(QObject):
    stats_updated = Signal(PetStats)    # 属性更新
    state_changed = Signal(PetState)    # 状态变化
    feed_requested = Signal()           # 喂食请求
    hunger_changed = Signal(float)      # 饱食度变化

class InteractionController(QObject):
    play_animation_requested = Signal(str, int)  # 播放动画
    snap_to_edge_requested = Signal()            # 吸附请求
    pet_requested = Signal()                     # 抚摸请求
    show_cooldown_tip_requested = Signal()       # 冷却提示
    show_hungry_refuse_requested = Signal()      # 饥饿拒绝
    show_energy_low_refuse_requested = Signal()  # 精力不足拒绝
    context_menu_requested = Signal(QPoint)      # 右键菜单
    hover_animation_requested = Signal(str)      # 悬停动画
    hover_animation_ended = Signal()             # 悬停结束
    lie_hover_tip_requested = Signal()           # lie 悬停提示

class CrossThreadSignals(QObject):
    typing_intensive = Signal(int)               # 高强度打字（跨线程）
```

---

## 7. 开发路线图进度

### 第一阶段：生存 (MVP 版本) 
- [x] 透明窗口 + 桌面显示小猫
- [x] 鼠标左键拖拽、右键菜单（喂食/退出）
- [x] 饱食度随时间下降

### 第二阶段：动效 (生动化)
- [x] 序列帧动画系统（idle/maimeng/oneeyes/hungry/sleep/lie/tired/walk）
- [x] 性格选择机制 + 宠物命名
- [x] 交互动画（悬停卖萌、点击独眼、拖拽吸附）
- [x] 对话气泡系统（智能定位、箭头方向、优先级调度）
- [x] lie 动画生命周期（正序→倒序→保持→重复）
- [x] tired 动画（精力疲劳状态，播放一次停在末帧）
- **动效制作流程**：使用 AI 生成角色基础图片和动作视频，再通过 ffmpeg 逐帧拆出 PNG 序列帧
  - AI 生成工具：用于创建角色设计稿和关键帧参考图
  - ffmpeg 视频转帧：将 AI 生成的白色背景动画视频逐帧导出为透明 PNG
    ```bash
    # 白色背景视频按帧数转 png（去白底 + 保留透明通道）
    ffmpeg -i walk1.mov -vf "colorkey=white:0.05:0.02,format=rgba" walk_%03d.png
    ```
    - `colorkey=white:0.05:0.02`：将白色像素（容差 5%，混合阈值 2%）设为透明
    - `format=rgba`：输出带 Alpha 通道的 PNG，确保透明背景可用
    - `-frames:v 1`：测试输出一张，参数放在生成的文件名前面

### 第三阶段：进化 (感知与成长) 
- [x] 键盘频率感知逻辑（性能优化：移除鼠标监听，改用 monotonic 时间）
- [x] 成长系统（经验值、等级、成长阶段）
- [x] 数据持久化（JSON存档）
- [x] 睡眠系统（三种触发条件：精力/饱食度/空闲）
- [x] 精力值系统（清醒恢复、睡眠恢复、交互消耗、三级状态）
- [x] 配置集中化（130+ 常量统一管理）
- [x] 感知系统优化（线程安全、性能优化）
- [x] 交互保护机制（lie/tired 状态下鼠标事件保护）

### 第四阶段：打磨 (待开发)
- [ ] 更多动画资源（walk、eating 等序列帧）
- [ ] 音效系统
- [ ] 装扮/皮肤系统
- [ ] 多显示器适配
- [ ] 打包为 .exe

---

## 8. 注意事项
1. **性能优化**：动画刷新率约24FPS；感知系统已移除鼠标移动监听（1000Hz），改用主线程定时器。
2. **线程安全**：`pynput` 回调在后台线程运行，绝对不能在其中创建 Qt 对象。必须通过 `CrossThreadSignals` 以信号派发到主线程。
3. **坐标异常**：多显示器环境下坐标计算可能出错，当前优先适配单屏幕。
4. **资源路径**：打包时需使用 `sys._MEIPASS` 处理绝对路径。
5. **存档防抖**：自动存档30秒间隔，避免频繁磁盘IO。
6. **配置管理**：所有调参常量集中在 `core/config.py`，禁止在其他文件中硬编码魔法数字。
