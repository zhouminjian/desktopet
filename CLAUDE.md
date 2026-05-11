# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在本仓库中工作时提供指引。用于减少 LLM 常见编码错误的行为准则。可根据需要与项目特定指令合并。

**权衡：** 这些准则更偏向谨慎而非速度。对于简单任务，请自行判断。

## 1.编码前先思考
**不要假设。不要掩饰困惑。明确权衡。**

在实现之前：
- 明确说明你的假设。如果不确定，就提问。
- 如果存在多种解释，全部列出来——不要默默选择一种。
- 如果有更简单的方法，直接说明。在必要时提出异议。
- 如果某些内容不清晰，就暂停。指出哪里令人困惑，并提出问题。

## 2.简洁优先

**用最少的代码解决问题。不做任何臆测性的扩展。**

- 不添加任何未被要求的功能。
- 不为一次性代码做抽象。
- 不加入未被要求的“灵活性”或“可配置性”。
- 不为不可能发生的场景添加错误处理。
- 如果你写了 200 行代码，而其实 50 行就够了，那就重写。
- 如果AI模型超过1分钟没有响应，则重新发起请求。

问问自己：“高级工程师会觉得这太复杂了吗？” 如果答案是“会”，那就继续简化。

## 3.外科手术式修改

**只修改必须修改的内容。只清理你自己造成的问题。**

修改现有代码时：

- 不要“顺手优化”相邻代码、注释或格式。
- 不要重构没有问题的部分。
- 保持现有风格一致，即使你个人会写得不同。
- 如果你发现无关的死代码，可以提出来——但不要删除。

当你的修改产生了遗留项时：

- 删除因你的修改而变成未使用的 import / 变量 / 函数。
- 不要删除原本就存在的死代码，除非被明确要求。

判断标准：每一行被修改的代码，都应该能直接对应到用户的需求。

## 4.4. 以目标驱动执行

**定义成功标准。循环直到验证通过。**

将任务转化为可验证的目标：

- “添加校验” → “先为非法输入编写测试，然后让测试通过”
- “修复 Bug” → “先写出能复现问题的测试，然后让测试通过”
- “重构 X” → “确保重构前后测试都通过”

对于多步骤任务，给出简要计划：
1. [步骤] → 验证：[检查项]
2. [步骤] → 验证：[检查项]
3. [步骤] → 验证：[检查项]

强有力的成功标准可以让你独立迭代。弱标准（例如“让它能工作”）则会导致频繁需要澄清。

---

## 项目概述

桌面宠物"Pii"——基于 PySide6 透明置顶窗口，支持 PNG 序列帧动画、属性衰减/恢复、键盘鼠标活动感知、JSON 存档持久化。仅支持 Windows，Python 3.10+。

## 常用命令

```bash
python main.py                                    # 启动应用
python -c "from core.config import PetConfig"      # 快速验证导入
```

暂无测试框架和 linter 配置。`tests/` 目录存在但为空。

## 架构

**入口 `main.py`：** 创建 QApplication → `PetDatabase.load()` 加载存档 → 实例化 `PetMainWindow` → 连接所有 Qt 信号（引擎/UI/感知） → 启动 `UserActivityMonitor` → 进入事件循环。

**模型层 — `core/engine.py`：**
- `PetStats` 数据类（饱食度、心情、精力、整洁度、等级、经验），默认值取自 `PetConfig.DEFAULT_*`。
- `PetEngine` 持有属性 + 状态（`PetState` 枚举：IDLE/WALK/SLEEP/EATING/DRAGGING）。`update()` 每秒调用，处理属性衰减/恢复。`feed()` / `pet()` / `consume_energy()` 修改属性并触发 `on_stats_change` 回调。
- `GrowthStage`（BABY/TEEN/ADULT）按等级阈值解锁。

**视图层 — `ui/main_window.py`：**
- `PetMainWindow`（无边框 + 透明 + 置顶）。鼠标事件委托给 `InteractionController`。拥有 `AnimationPlayer` 和 `BehaviorController`。
- `_on_update()`（1秒定时器）：调用 `engine.update()` + `behavior.check_sleep()`。
- `_on_auto_action()`（可变间隔定时器）：通过 `BehaviorController` 分发 idle_blink / walk_around / snap_to_edge。

**控制层 — `core/behavior.py` + `ui/interaction_controller.py`：**
- `BehaviorController`：睡眠/唤醒逻辑、自动动作分发、空闲追踪。`check_sleep()` 每秒执行——精力≤10 或饱食度≤15 时强制睡眠（任意状态），或无互动≥120秒（仅 IDLE）。`wake_up()` 需同时满足：精力>10、饱食度>15、距上次互动≥5秒。
- `InteractionController`（QObject）：处理鼠标按下/释放/移动/进入/离开。饱食度≤15 或精力≤10 时阻止交互。通过信号通知 pet_requested、snap_to_edge、context_menu、悬停动画。

**动画层 — `ui/animation_player.py`：**
- 从 `assets/animations/<state>/` 子目录加载 PNG 帧，无资源时使用占位图绘制。
- 优先级：`force_animation` > `hover_animation` > 饥饿覆盖 > 引擎状态映射（通过 `core/state_resolver.py`）。
- 循环暂停：普通动画播完1轮后暂停5秒；sleep 循环不暂停；lie 播完一轮后停在第一帧，30-60秒随机间隔后再次播放。

**配置 `core/config.py`：**
- 所有调参常量集中在此，作为 `PetConfig` 类属性。禁止在其他文件中硬编码魔法数字。

**跨线程安全：**
- `pynput` 回调在后台线程运行，绝对不能在其中创建 Qt 对象（QTimer、QWidget 等）。必须通过 `main.py` 中的 `CrossThreadSignals` QObject 以 Qt 信号派发到主线程。

**气泡系统 — `ui/bubble_manager.py` + `ui/components.py`：**
- `BubbleManager` 统一调度气泡消息，处理优先级和冷却。`SpeechBubble` 渲染带方向箭头的气泡，主定时器 + 保底定时器双重自动隐藏。

**持久化 — `core/database.py`：**
- 存档路径 `%APPDATA%/DesktopPet/pii_save.json`。每30秒自动存档。恢复存档时 SLEEP 状态强制转为 IDLE。

## 关键设计模式

- **信号连接在 `main.py` 中完成：** 所有跨组件通信通过 Qt 信号（`PetSignals` 和 `InteractionController` 上定义）。引擎回调（`on_stats_change`、`on_state_change` 等）直接赋值。
- **动画状态解析：** `state_resolver.resolve_animation_state()` 是决定显示哪个动画的唯一依据，由 `AnimationPlayer.get_current_pixmap()` 调用。
- **交互流程：** 鼠标事件 → `InteractionController` → 发射信号 → `main_window` 处理函数 → `engine` 方法 → `on_stats_change` 回调链。
- **lie 动画防重入：** `start_force_animation("lie")` 在 lie 已在播放或保持中时直接跳过，防止每秒触发的 `on_stats_change` 反复重启动画。
- **唤醒流程修正：** `wake_up()` 内部不更新 `_last_interaction_time`，由调用方（`_update_interaction_time`）在调用前先更新，否则 5 秒冷却检查永远失败。

## 注意事项
- 所有对话都是用中文回复，除非有必须使用英文或者字母组合的情况。