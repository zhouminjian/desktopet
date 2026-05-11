"""
宠物配置模块
集中管理宠物相关的各类常量、阈值和参数
"""

class PetConfig:
    # ============================================================
    # 应用基础
    # ============================================================
    APP_NAME = "DesktopPet"
    SAVE_FILENAME = "pii_save.json"
    DEFAULT_PET_NAME = "Pii"  # 默认宠物名称
    AUTO_SAVE_INTERVAL = 30   # 自动存档间隔 (秒)

    # ============================================================
    # 窗口 & 动画基础
    # ============================================================
    WINDOW_WIDTH = 128            # 窗口宽度 (像素)
    WINDOW_HEIGHT = 128           # 窗口高度 (像素)
    MAX_WINDOW_SIZE = 128         # 最大窗口尺寸限制
    FPS = 24                      # 动画帧率
    FRAME_INTERVAL = 1000 // FPS  # 动画帧间隔 (毫秒，约42ms)
    DEFAULT_SCREEN_MARGIN_X = 20  # 初始位置距屏幕右边缘距离 (像素)
    DEFAULT_SCREEN_MARGIN_BOTTOM = 80  # 初始位置距屏幕底部距离 (像素，任务栏上方)

    # ============================================================
    # 鼠标交互
    # ============================================================
    DRAG_DISTANCE_THRESHOLD = 5       # 区分点击和拖拽的最小距离 (像素)
    HUNGER_INTERACT_REFUSE_THRESHOLD = 15  # 饱食度低于此值时拒绝互动 (喂食除外)
    INTERACTION_COOLDOWN_TIME = 0.5   # 点击强制动画后的等待时间 (秒)

    # ============================================================
    # 吸附
    # ============================================================
    SNAP_EDGE_MARGIN = 5          # 吸附到边缘时与屏幕边的间距 (像素)
    SNAP_ALREADY_CLOSE = 10       # 已接近边缘时不移动的距离阈值 (像素)
    TASKBAR_CLEARANCE = 60        # 吸附底部时与任务栏的间距 (像素)
    MOVE_MIN_DISTANCE = 10        # 移动动画最小位移，低于此值直接定位 (像素)
    MOVE_ANIM_DURATION_MS = 500   # 吸附/移动动画持续时间 (毫秒)
    MOVE_ANIM_FPS = 60            # 移动动画帧率

    # ============================================================
    # 对话气泡
    # ============================================================
    BUBBLE_OFFSET_Y = -70           # 对话气泡默认 Y 轴偏移
    BUBBLE_GAP = 5                  # 气泡与宠物的间距 (像素)
    BUBBLE_SCREEN_MARGIN = 5        # 气泡与屏幕边缘的最小距离 (像素)
    BUBBLE_MAX_WIDTH = 180          # 气泡最大宽度 (像素)
    BUBBLE_MAX_HEIGHT = 120         # 气泡最大高度 (像素)
    BUBBLE_ARROW_SIZE = 10          # 气泡箭头大小 (像素)
    BUBBLE_BORDER_RADIUS = 8        # 气泡圆角半径 (像素)
    BUBBLE_FONT_SIZE = 12           # 气泡文字字号 (px)
    BUBBLE_DEFAULT_WIDTH = 150      # 气泡默认宽度 (像素)
    BUBBLE_DEFAULT_HEIGHT = 60      # 气泡默认高度 (像素)
    BUBBLE_TEXT_PADDING_X = 24      # 气泡文字水平内边距 (像素)
    BUBBLE_TEXT_PADDING_Y = 16      # 气泡文字垂直内边距 (像素)
    BUBBLE_ARROW_SPACE = 10        # 气泡为箭头预留的空间 (像素)
    BUBBLE_FAIL_SAFE_EXTRA = 500    # 气泡保底隐藏定时器额外延迟 (毫秒)
    BUBBLE_EDGE_THRESHOLD_BOTTOM = 100  # 底部边缘检测阈值 (像素)
    BUBBLE_EDGE_THRESHOLD_TOP = 30  # 顶部边缘检测阈值 (像素)

    # 气泡显示时长 (毫秒)
    BUBBLE_HUNGRY_REFUSE_DURATION = 3000   # 饥饿拒绝提示
    BUBBLE_COOLDOWN_TIP_DURATION = 2000    # 冷却提示
    BUBBLE_HUNGRY_NOTIFY_DURATION = 5000   # 饥饿提醒
    BUBBLE_LEVEL_UP_DURATION = 3000        # 升级提示
    BUBBLE_STAGE_CHANGE_DURATION = 4000    # 成长阶段变化
    BUBBLE_TYPING_INTENSIVE_DURATION = 5000  # 高强度打字鼓励
    BUBBLE_PETTED_DURATION = 2500          # 抚摸反馈
    BUBBLE_GREETING_DURATION = 4000        # 欢迎语
    BUBBLE_SLEEP_DURATION = 3000           # 进入睡眠提示
    BUBBLE_WAKE_DURATION = 2000            # 唤醒提示
    BUBBLE_WAKE_REFUSAL_DURATION = 3000    # 唤醒拒绝提示
    BUBBLE_WALK_ENCOURAGE_DURATION = 3000  # 行走鼓励

    # 气泡冷却间隔 (秒)
    BUBBLE_HUNGRY_NOTIFY_INTERVAL = 60     # 饥饿提醒最小间隔
    BUBBLE_TYPING_ENCOURAGE_COOLDOWN = 30  # 打字鼓励冷却
    BUBBLE_WAKE_REFUSAL_COOLDOWN = 3       # 唤醒拒绝冷却

    # ============================================================
    # 自动动作
    # ============================================================
    AUTO_ACTION_INTERVAL_MEAN = 8000   # 自动动作平均间隔 (毫秒)
    AUTO_ACTION_INTERVAL_STD = 3000    # 自动动作间隔标准差 (毫秒)
    AUTO_ACTION_INTERVAL_MIN = 3000    # 自动动作最小间隔 (毫秒)
    AUTO_ACTION_INTERVAL_MAX = 20000   # 自动动作最大间隔 (毫秒)
    ACTION_FALLBACK_INTERVAL = 1000    # 自动动作未触发时的下次检查间隔 (毫秒)
    UPDATE_TIMER_INTERVAL = 1000       # 属性更新定时器间隔 (毫秒)
    ACTION_FPS_INTERVAL = 1000 // 60   # 动作动画帧间隔 (毫秒，60fps)

    # 动作权重
    ACTION_WEIGHTS = {
        "idle_blink": 70,   # 发呆眨眼
        "walk_around": 20,  # 原地播放 walk 动画
        "snap_to_edge": 10, # 吸附到边缘
    }

    # 动作动画参数
    JUMP_DURATION = 600        # 跳跃动画总时长 (毫秒)
    JUMP_HEIGHT = 80           # 跳跃高度 (像素)
    JUMP_SCALE_FACTOR = 0.15   # 跳跃缩放幅度 (15%)
    JUMP_WOBBLE = 5            # 跳跃落地左右摇摆幅度 (像素)
    ROLL_DURATION = 800        # 翻滚动画总时长 (毫秒)
    CUTE_DURATION = 1500       # 卖萌动画总时长 (毫秒)
    CUTE_FPS_INTERVAL = 50     # 卖萌动画帧间隔 (毫秒，20fps)
    CUTE_TILT_ANGLE = 15       # 卖萌头部倾斜角度 (度)
    CUTE_WOBBLE = 8            # 卖萌摇摆幅度 (像素)

    # Walk 自动漫步
    WALK_MIN_IDLE_TIME = 10        # 进入 IDLE 后最少等多少秒才允许触发 walk
    WALK_DURATION_BASE = 4000      # 单次 walk 基础持续时间 (毫秒)
    WALK_DURATION_PER_CYCLE = 4000 # 每多一轮循环增加的持续时间 (毫秒)
    WALK_CYCLE_MIN = 1             # walk 动画最少循环次数
    WALK_CYCLE_MAX = 3             # walk 动画最多循环次数
    WALK_ENCOURAGE_MESSAGES = [
        "出去溜溜~",
        "活动活动筋骨~",
        "走走路心情好~",
        "散步中~",
        "跑跑跳跳~",
        "嘿嘿，溜达一圈~",
    ]

    # ============================================================
    # 动画帧
    # ============================================================
    ANIM_FRAME_INTERVAL_SLEEP = 10     # sleep 动画每N帧切换一次 (约400ms)
    ANIM_FRAME_INTERVAL_DEFAULT = 6    # 默认动画每N帧切换一次 (约250ms)
    ANIM_FRAME_INTERVAL_VIDEO = 1      # 高帧数动画每N帧切换一次 (约41ms，~24fps)
    ANIM_VIDEO_FRAME_THRESHOLD = 10    # 帧数超过此值时使用 VIDEO 帧率
    ANIM_SINGLE_FRAME_REDRAW = 12      # 单帧动画每N帧重绘一次 (约500ms)
    ANIM_CYCLE_PAUSE_DEFAULT = 5000    # 正常动画循环结束后暂停时间 (毫秒)
    BLINK_ANIM_DURATION = 200          # 眨眼动画持续时间 (毫秒)
    LIE_REPEAT_MIN_MS = 30000          # lie 动画重复播放最小间隔 (毫秒)
    LIE_REPEAT_MAX_MS = 60000          # lie 动画重复播放最大间隔 (毫秒)

    # ============================================================
    # 睡眠 & 唤醒
    # ============================================================
    SLEEP_IDLE_TIME = 120         # 无互动后自动进入睡眠的时间 (秒)
    WAKE_MIN_IDLE_TIME = 5        # 唤醒后至少等待多少秒才能再次被唤醒
    WAKE_ENERGY_THRESHOLD = 1    # 精力值低于此值时强制睡眠/拒绝唤醒/阻止交互
    ENERGY_TIRED_THRESHOLD = 20   # 精力值低于此值时触发 tired 动画提醒
    WAKE_HUNGER_THRESHOLD = 1    # 饱食度低于此值时强制睡眠/拒绝唤醒

    # ============================================================
    # 占位图绘制
    # ============================================================
    PLACEHOLDER_PET_SIZE = 108                               # 宠物基础大小
    PLACEHOLDER_PET_EYE_SIZE = 15                            # 眼睛大小
    PLACEHOLDER_PET_BODY_SIZE = 100                          # 身体基础大小
    PLACEHOLDER_PET_MOUTH_ARC = (45, 65, 38, 25, 0, 180 * 16)       # 微笑嘴巴弧度
    PLACEHOLDER_PET_HUNGRY_MOUTH_ARC = (45, 75, 38, 20, 0, -180 * 16)  # 饥饿嘴巴弧度
    PLACEHOLDER_CENTER_X = 64     # 占位图绘制中心 X
    PLACEHOLDER_CENTER_Y = 64     # 占位图绘制中心 Y
    PLACEHOLDER_WALK_OFFSET = 3   # walk 占位动画左右摇摆偏移 (像素)

    # ============================================================
    # 引擎：属性默认值
    # ============================================================
    DEFAULT_HUNGER = 80.0       # 初始饱食度
    DEFAULT_HAPPINESS = 70.0    # 初始心情值
    DEFAULT_ENERGY = 100.0      # 初始精力值
    DEFAULT_HYGIENE = 100.0     # 初始整洁度
    UPDATE_MIN_DELTA = 0.1      # 引擎 update() 最小时间间隔 (秒)

    # ============================================================
    # 引擎：属性衰减/恢复
    # ============================================================
    HUNGER_DECAY_RATE = 1.0 / 60        # 饱食度每秒衰减 (清醒，1点/分钟)
    HUNGER_DECAY_SLEEP_RATE = 1.0 / 300  # 饱食度每秒衰减 (睡眠，1点/5分钟)
    HAPPINESS_DECAY_RATE = 1.0 / 60      # 心情每秒衰减 (1点/分钟)
    HAPPINESS_LOW_HUNGER_DECAY_RATE = 2.0 / 60  # 饥饿时心情每秒衰减 (2点/分钟)
    ENERGY_SLEEP_RECOVER_RATE = 10.0 / 60  # 睡眠中精力每秒恢复 (10点/分钟)
    ENERGY_AWAKE_RECOVER_RATE = 1.0 / 60   # 清醒时精力每秒恢复 (1点/分钟)
    ENERGY_INTERACT_COST = 2.0           # 每次交互消耗精力

    # ============================================================
    # 引擎：互动收益
    # ============================================================
    HAPPINESS_PET_GAIN = 1.0        # 抚摸获得心情
    HAPPINESS_FEED_GAIN = 5.0       # 喂食获得心情
    FEED_VALUE = 30.0               # 每次喂食增加饱食度
    MAX_STATS = 100.0               # 属性最大值

    # ============================================================
    # 引擎：经验 & 等级
    # ============================================================
    EXP_PER_FEED = 10           # 喂食获得经验
    EXP_PER_PET = 5             # 抚摸获得经验
    EXP_PER_MINUTE_ONLINE = 1   # 每分钟在线获得经验
    EXP_ONLINE_INTERVAL = 60    # 在线经验检查间隔 (秒)
    LEVEL_UP_BASE_EXP = 100     # 每级所需基础经验 (逐级增加)

    # ============================================================
    # 引擎：阈值
    # ============================================================
    HUNGER_LOW_THRESHOLD = 15       # 饱食度低于此值被认为是"饿了"
    HUNGER_CRITICAL_THRESHOLD = 10  # 饱食度低于此值被认为是"很饿"
    HUNGER_FULL_THRESHOLD = 90      # 饱食度高于此值被认为是"饱饱的"
    HAPPINESS_LOW_THRESHOLD = 35    # 心情低于此值触发邀玩提示
    HAPPINESS_HIGH_THRESHOLD = 80   # 心情高于此值显示"开心"
    ENERGY_LOW_THRESHOLD = 20       # 精力低于此值显示"困倦"
    HAPPINESS_NOTIFY_INTERVAL = 60  # 心情提示最小间隔 (秒)

    # 智能互动气泡
    PETTED_HUNGER_THRESHOLD = 30       # 点击时饥饿感知阈值
    PETTED_ENERGY_THRESHOLD = 40       # 点击时精力感知阈值
    PETTED_CONTEXT_CHANCE = 0.5        # 条件文案触发概率 (50%)
    PETTED_MILESTONE_INTERVAL = 10     # 里程碑间隔天数

    # 成长阶段解锁等级
    STAGE_LEVELS = {
        "BABY": 1,   # 幼年: 1-4级
        "TEEN": 5,   # 少年: 5-9级
        "ADULT": 10  # 青年: 10级以上
    }

    # ============================================================
    # 感知系统
    # ============================================================
    TYPING_THRESHOLD = 100               # 1分钟内敲击超过此值认为是"高强度打字"
    IDLE_THRESHOLD = 10                  # 5秒内操作少于此值认为是"空闲"
    IDLE_CHECK_INTERVAL = 5             # 空闲检测频率 (秒)
    TYPING_FREQUENCY_WINDOW_SECONDS = 60 # 键盘频率统计窗口大小 (秒)
    TYPING_INTENSIVE_COOLDOWN = 300      # 高强度打字提醒冷却时间 (秒)
    MOUSE_MOVE_SAMPLE_RATE = 10         # 鼠标移动采样率 (每N次计数一次)

    # ============================================================
    # 浮动文字
    # ============================================================
    FLOATING_TEXT_FONT_SIZE = 14       # 浮动文字字号 (px)
    FLOATING_TEXT_SPEED = 1            # 浮动速度 (像素/帧)
    FLOATING_TEXT_FADE_DURATION = 3000 # 渐隐时长 (毫秒)
    FLOATING_TEXT_WIDTH = 100          # 浮动文字默认宽度 (像素)
    FLOATING_TEXT_HEIGHT = 30          # 浮动文字默认高度 (像素)