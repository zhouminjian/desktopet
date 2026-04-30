"""
UI组件模块
包含对话气泡、系统托盘等辅助组件
"""

from PySide6.QtWidgets import QWidget, QApplication, QLabel, QGraphicsDropShadowEffect
from PySide6.QtCore import Qt, QTimer, QPoint, QRect
from PySide6.QtGui import QColor, QPainter, QBrush, QFont, QPen, QPolygon, QFontMetrics


class SpeechBubble(QWidget):
    """
    对话气泡组件
    显示宠物对话或状态提示
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 设置无边框和透明背景
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        
        # 标签显示文字
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setWordWrap(True)
        self._label.setStyleSheet("""
            QLabel {
                color: #333333;
                font-family: "Microsoft YaHei", "SimHei", sans-serif;
                font-size: 12px;
                padding: 8px 12px;
            }
        """)
        
        # 自动隐藏定时器
        self._hide_timer = QTimer(self)
        self._hide_timer.timeout.connect(self.hide)
        
        # 箭头方向: "down"/"up"/"left"/"right"
        self._arrow_direction = "down"
        self._arrow_size = 10
        
        # 默认大小
        self.setFixedSize(150, 60)
        self.hide()
    
    def show_text(self, text: str, duration: int = 3000):
        """
        显示气泡文字
        
        Args:
            text: 显示内容
            duration: 显示时长(毫秒)，默认3秒
        """
        self._label.setText(text)
        self._label.adjustSize()
        
        # 调整气泡大小适应文字（限制最大尺寸防止超出屏幕）
        fm = QFontMetrics(self._label.font())
        max_width = 180  # 最大宽度限制
        max_height = 120  # 最大高度限制
        text_width = min(fm.horizontalAdvance(text) + 24, max_width)
        text_height = fm.boundingRect(QRect(0, 0, text_width - 24, max_height), 
                                       Qt.TextWordWrap, text).height() + 16
        
        # 确保不超出限制
        text_height = min(text_height, max_height)
        
        self.setFixedSize(text_width, text_height + 10)  # +10 给箭头留空间
        self._label.setGeometry(0, 0, text_width, text_height)
        
        self.show()
        self.raise_()
        
        # 重绘气泡形状
        self.update()
        
        # 定时隐藏
        self._hide_timer.stop()
        self._hide_timer.start(duration)
    
    def set_arrow_direction(self, direction: str):
        """设置箭头方向"""
        self._arrow_direction = direction
        self.update()  # 重绘
    
    def paintEvent(self, event):
        """绘制气泡形状 - 支持多方向箭头"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 背景色
        bg_color = QColor(255, 255, 255, 230)  # 半透明白
        border_color = QColor(200, 200, 200, 200)
        
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, 1))
        
        # 根据箭头方向调整主体位置和绘制箭头
        arrow_size = self._arrow_size
        direction = self._arrow_direction
        
        if direction == "down":
            rect = self.rect().adjusted(0, 0, 0, -arrow_size)
            painter.drawRoundedRect(rect, 8, 8)
            # 向下箭头（底部中央）
            arrow_x = self.width() // 2
            arrow_y = self.height() - arrow_size
            arrow = QPolygon([
                QPoint(arrow_x - arrow_size//2, arrow_y),
                QPoint(arrow_x, arrow_y + arrow_size),
                QPoint(arrow_x + arrow_size//2, arrow_y)
            ])
        elif direction == "up":
            rect = self.rect().adjusted(0, arrow_size, 0, 0)
            painter.drawRoundedRect(rect, 8, 8)
            # 向上箭头（顶部中央）
            arrow_x = self.width() // 2
            arrow_y = arrow_size
            arrow = QPolygon([
                QPoint(arrow_x - arrow_size//2, arrow_y),
                QPoint(arrow_x, 0),
                QPoint(arrow_x + arrow_size//2, arrow_y)
            ])
        elif direction == "right":
            rect = self.rect().adjusted(0, 0, -arrow_size, 0)
            painter.drawRoundedRect(rect, 8, 8)
            # 向右箭头（右侧中央）
            arrow_x = self.width() - arrow_size
            arrow_y = self.height() // 2
            arrow = QPolygon([
                QPoint(arrow_x, arrow_y - arrow_size//2),
                QPoint(arrow_x + arrow_size, arrow_y),
                QPoint(arrow_x, arrow_y + arrow_size//2)
            ])
        elif direction == "left":
            rect = self.rect().adjusted(arrow_size, 0, 0, 0)
            painter.drawRoundedRect(rect, 8, 8)
            # 向左箭头（左侧中央）
            arrow_x = arrow_size
            arrow_y = self.height() // 2
            arrow = QPolygon([
                QPoint(arrow_x, arrow_y - arrow_size//2),
                QPoint(0, arrow_y),
                QPoint(arrow_x, arrow_y + arrow_size//2)
            ])
        elif direction == "right-down":
            rect = self.rect().adjusted(0, 0, -arrow_size, -arrow_size)
            painter.drawRoundedRect(rect, 8, 8)
            # 向右下箭头（右下角，指向右下方宠物）
            arrow = QPolygon([
                QPoint(self.width() - arrow_size - arrow_size//2, self.height() - arrow_size),
                QPoint(self.width(), self.height()),
                QPoint(self.width() - arrow_size, self.height() - arrow_size - arrow_size//2)
            ])
        elif direction == "left-down":
            rect = self.rect().adjusted(0, 0, -arrow_size, -arrow_size)
            painter.drawRoundedRect(rect, 8, 8)
            # 向左下箭头（左下角，指向左下方宠物）
            arrow = QPolygon([
                QPoint(arrow_size + arrow_size//2, self.height() - arrow_size),
                QPoint(0, self.height()),
                QPoint(arrow_size, self.height() - arrow_size - arrow_size//2)
            ])
        elif direction == "right-up":
            rect = self.rect().adjusted(0, arrow_size, -arrow_size, 0)
            painter.drawRoundedRect(rect, 8, 8)
            # 向右上箭头（右上角）
            arrow = QPolygon([
                QPoint(self.width() - arrow_size - arrow_size//2, arrow_size),
                QPoint(self.width(), 0),
                QPoint(self.width() - arrow_size, arrow_size + arrow_size//2)
            ])
        elif direction == "left-up":
            rect = self.rect().adjusted(0, arrow_size, -arrow_size, 0)
            painter.drawRoundedRect(rect, 8, 8)
            # 向左上箭头（左上角）
            arrow = QPolygon([
                QPoint(arrow_size + arrow_size//2, arrow_size),
                QPoint(0, 0),
                QPoint(arrow_size, arrow_size + arrow_size//2)
            ])
        else:
            # 默认向下
            rect = self.rect().adjusted(0, 0, 0, -arrow_size)
            painter.drawRoundedRect(rect, 8, 8)
            arrow_x = self.width() // 2
            arrow_y = self.height() - arrow_size
            arrow = QPolygon([
                QPoint(arrow_x - arrow_size//2, arrow_y),
                QPoint(arrow_x, arrow_y + arrow_size),
                QPoint(arrow_x + arrow_size//2, arrow_y)
            ])
        
        painter.drawPolygon(arrow)
        painter.end()
    
    def position_beside(self, target_widget: QWidget, offset: QPoint = QPoint(0, -70)):
        """
        定位到目标窗口旁边
        
        Args:
            target_widget: 参考窗口
            offset: 相对偏移量，默认在上方
        """
        target_pos = target_widget.mapToGlobal(QPoint(0, 0))
        self.move(target_pos + offset)


class StatusIndicator(QWidget):
    """
    状态指示器
    简单显示数值条（饱食度等）
    """
    
    def __init__(self, title: str = "状态", color: QColor = QColor(255, 150, 100), parent=None):
        super().__init__(parent)
        
        self.setFixedSize(100, 24)
        
        self._title = title
        self._color = color
        self._value = 100.0
        self._max_value = 100.0
    
    def set_value(self, value: float, max_value: float = 100.0):
        """设置当前值"""
        self._value = max(0.0, min(max_value, value))
        self._max_value = max_value
        self.update()
    
    def paintEvent(self, event):
        """绘制进度条"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 背景
        painter.setBrush(QBrush(QColor(220, 220, 220)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 4, 4)
        
        # 进度
        if self._max_value > 0:
            ratio = self._value / self._max_value
            width = int(self.width() * ratio)
            
            progress_rect = self.rect().adjusted(0, 0, -(self.width() - width), 0)
            painter.setBrush(QBrush(self._color))
            painter.drawRoundedRect(progress_rect, 4, 4)
        
        # 文字
        painter.setPen(QPen(Qt.white, 1))
        painter.setFont(QFont("Microsoft YaHei", 8))
        text = f"{self._title}: {int(self._value)}"
        painter.drawText(self.rect(), Qt.AlignCenter, text)
        
        painter.end()


class FloatingText(QWidget):
    """
    浮动文字组件
    显示向上浮动并逐渐消失的数值变化提示
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 无边框透明置顶
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        
        # 标签
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet("""
            QLabel {
                font-family: "Microsoft YaHei", sans-serif;
                font-size: 14px;
                font-weight: bold;
                padding: 4px 8px;
            }
        """)
        
        # 动画参数
        self._float_speed = 1  # 浮动速度(像素/帧)
        self._fade_speed = 1.0 / (3 * 60)  # 3秒消失(60fps)
        self._opacity = 1.0
        self._target_widget = None
        
        # 定时器
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_animate)
        
        self.setFixedSize(100, 30)
        self.hide()
    
    def show_value(self, text: str, color: QColor, target_widget: QWidget, offset: QPoint = QPoint(0, -50)):
        """
        显示浮动数值
        
        Args:
            text: 显示文字 (如 "+10 经验")
            color: 文字颜色
            target_widget: 参考窗口(宠物窗口)
            offset: 相对偏移
        """
        self._label.setText(text)
        self._label.setStyleSheet(f"""
            QLabel {{
                font-family: "Microsoft YaHei", sans-serif;
                font-size: 14px;
                font-weight: bold;
                color: {color.name()};
                padding: 4px 8px;
            }}
        """)
        
        # 自适应大小
        fm = QFontMetrics(self._label.font())
        text_width = fm.horizontalAdvance(text) + 16
        self.setFixedSize(text_width, 30)
        self._label.setGeometry(0, 0, text_width, 30)
        
        # 定位
        self._target_widget = target_widget
        target_pos = target_widget.mapToGlobal(QPoint(0, 0))
        self._start_pos = target_pos + QPoint(
            (target_widget.width() - text_width) // 2,
            offset.y()
        )
        self._current_offset = 0
        self._opacity = 1.0
        
        self.move(self._start_pos)
        self.show()
        self.raise_()
        
        # 启动动画 (60fps)
        self._timer.start(1000 // 60)
    
    def _on_animate(self):
        """动画帧更新"""
        self._current_offset -= self._float_speed  # 向上浮动
        self._opacity -= self._fade_speed  # 渐隐
        
        if self._opacity <= 0:
            # 完全透明，结束动画
            self._timer.stop()
            self.hide()
            return
        
        # 更新位置
        new_pos = self._start_pos + QPoint(0, int(self._current_offset))
        self.move(new_pos)
        
        # 更新透明度
        self.setWindowOpacity(self._opacity)
        self.update()


# ============ 模块自测试 ============
if __name__ == "__main__":
    import sys
    
    print("=" * 40)
    print("模块测试: ui/components.py")
    print("=" * 40)
    
    app = QApplication(sys.argv)
    
    # 测试1: 气泡组件
    print("\n[测试1] 对话气泡组件")
    bubble = SpeechBubble()
    bubble.show_text("我饿了喵~\n可以给我喂食吗？", duration=5000)
    
    # 居中显示
    screen = QApplication.primaryScreen().geometry()
    bubble.move(
        (screen.width() - bubble.width()) // 2,
        (screen.height() - bubble.height()) // 2
    )
    
    print(f"  气泡大小: {bubble.width()}x{bubble.height()}")
    print(f"  显示文字: '我饿了喵~'")
    print("  ✓ 气泡组件创建成功")
    
    # 测试2: 状态指示器
    print("\n[测试2] 状态指示器")
    indicator = StatusIndicator("饱食度", QColor(255, 150, 100))
    indicator.set_value(65.0)
    indicator.show()
    indicator.move(
        (screen.width() - indicator.width()) // 2,
        (screen.height() - indicator.height()) // 2 + 100
    )
    
    print(f"  指示器大小: {indicator.width()}x{indicator.height()}")
    print(f"  当前值: 65/100")
    print("  ✓ 指示器组件创建成功")
    
    print("\n" + "=" * 40)
    print("组件测试窗口已启动 (5秒后自动关闭)")
    print("=" * 40)
    
    # 5秒后自动退出
    QTimer.singleShot(5000, app.quit)
    
    sys.exit(app.exec())
