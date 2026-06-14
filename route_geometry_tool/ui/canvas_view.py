"""Canvas图形绘制：线路平面示意图。

将 :class:`~route_geometry_tool.core.models.Segment` 序列渲染为线路
平面图：直线/缓和曲线/圆曲线分别用不同颜色绘制，支持鼠标滚轮缩放、
"适应窗口" 重置视图，以及鼠标悬停时显示最近点的里程与坐标提示。

世界坐标系 → 画布坐标系的变换规则：

    cx = _offset_x + x * _scale
    cy = _offset_y - y * _scale      # 世界 Y 向上，画布 Y 向下，需翻转
"""
from __future__ import annotations

import tkinter as tk

from route_geometry_tool.core.models import Segment, SegmentType
from route_geometry_tool.core.query import RouteQuery

# 段类型颜色
SEGMENT_COLORS = {
    SegmentType.STRAIGHT: '#333333',     # 深灰（直线）
    SegmentType.TRANSITION: '#2196F3',   # 蓝色（缓和曲线）
    SegmentType.CIRCULAR: '#F44336',     # 红色（圆曲线）
}
SEGMENT_NAMES = {
    SegmentType.STRAIGHT: '直线',
    SegmentType.TRANSITION: '缓和曲线',
    SegmentType.CIRCULAR: '圆曲线',
}

# 画布尺寸与边距
_CANVAS_HEIGHT = 500
_FIT_MARGIN = 40           # 适应窗口时的四周边距（像素）
_DEFAULT_CANVAS_W = 900    # 画布尚未渲染时的默认宽度
_DEFAULT_CANVAS_H = 500    # 画布尚未渲染时的默认高度

# 悬停命中阈值：鼠标距线路 20 像素内即视为命中
_HIT_PIXELS = 20


class CanvasView(tk.LabelFrame):
    """线路平面图形绘制区域。

    通过 :meth:`set_data` 注入线元序列与查询引擎后即可绘制。
    支持：

    * 适应窗口：将整条线路缩放至画布可见区；
    * 滚轮缩放：以画布中心为锚点放大/缩小；
    * 悬停提示：鼠标移动到线路附近显示里程与坐标。
    """

    def __init__(self, parent):
        super().__init__(parent, text="线路平面图", padx=5, pady=5)
        self.segments: list[Segment] = []
        self.query_engine: RouteQuery | None = None
        self.tooltip: tk.Toplevel | None = None
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._scale = 1.0
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _setup_ui(self):
        # 工具栏：左侧按钮 + 右侧图例
        toolbar = tk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))

        tk.Button(
            toolbar, text="适应窗口", command=self._on_fit
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            toolbar, text="放大", command=lambda: self._zoom(1.2)
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            toolbar, text="缩小", command=lambda: self._zoom(1 / 1.2)
        ).pack(side=tk.LEFT, padx=2)

        # 图例：向右排列，■ 用对应颜色
        legend_frame = tk.Frame(toolbar)
        legend_frame.pack(side=tk.RIGHT)
        for seg_type in (
            SegmentType.STRAIGHT,
            SegmentType.TRANSITION,
            SegmentType.CIRCULAR,
        ):
            tk.Label(
                legend_frame,
                text=f"■ {SEGMENT_NAMES[seg_type]}",
                fg=SEGMENT_COLORS[seg_type],
            ).pack(side=tk.LEFT, padx=4)

        # 画布
        self.canvas = tk.Canvas(
            self, bg='white', height=_CANVAS_HEIGHT, highlightthickness=1,
            highlightbackground='#cccccc',
        )
        self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # 绑定事件
        self.canvas.bind('<MouseWheel>', self._on_mousewheel)
        self.canvas.bind('<Motion>', self._on_mouse_move)
        self.canvas.bind('<Leave>', self._hide_tooltip)

    # ------------------------------------------------------------------
    # 外部接口
    # ------------------------------------------------------------------
    def set_data(self, segments: list[Segment], query_engine: RouteQuery):
        """注入线元与查询引擎，自动适应窗口并重绘。"""
        self.segments = list(segments)
        self.query_engine = query_engine
        if self.segments:
            self._fit_view()
        self._draw()

    # ------------------------------------------------------------------
    # 视图变换
    # ------------------------------------------------------------------
    def _canvas_size(self) -> tuple[int, int]:
        """返回当前画布的 (宽, 高)；未渲染时返回默认值。"""
        self.update_idletasks()
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10:
            w = _DEFAULT_CANVAS_W
        if h < 10:
            h = _DEFAULT_CANVAS_H
        return w, h

    def _fit_view(self):
        """根据所有线元端点的外接矩形，计算 _scale 与 _offset 使线路居中。

        世界 Y 向上、画布 Y 向下，因此 Y 方向需要翻转。
        """
        if not self.segments:
            self._scale = 1.0
            self._offset_x = 0.0
            self._offset_y = 0.0
            return

        xs: list[float] = []
        ys: list[float] = []
        for seg in self.segments:
            xs.append(seg.start_point.x)
            ys.append(seg.start_point.y)
            xs.append(seg.end_point.x)
            ys.append(seg.end_point.y)

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        data_w = max_x - min_x
        data_h = max_y - min_y

        canvas_w, canvas_h = self._canvas_size()
        avail_w = max(canvas_w - 2 * _FIT_MARGIN, 1)
        avail_h = max(canvas_h - 2 * _FIT_MARGIN, 1)

        # 防御零宽/零高数据
        scale_x = avail_w / data_w if data_w > 1e-9 else 1.0
        scale_y = avail_h / data_h if data_h > 1e-9 else 1.0
        scale = min(scale_x, scale_y)
        if not (scale > 0) or scale != scale:  # NaN 检查
            scale = 1.0
        self._scale = scale

        # 居中：让数据包围盒中心对齐画布中心
        data_cx = (min_x + max_x) / 2.0
        data_cy = (min_y + max_y) / 2.0
        canvas_cx = canvas_w / 2.0
        canvas_cy = canvas_h / 2.0

        # cx = _offset_x + x * _scale  ->  _offset_x = canvas_cx - data_cx * _scale
        self._offset_x = canvas_cx - data_cx * self._scale
        # cy = _offset_y - y * _scale  ->  _offset_y = canvas_cy + data_cy * _scale
        self._offset_y = canvas_cy + data_cy * self._scale

    def _world_to_canvas(self, x: float, y: float) -> tuple[float, float]:
        cx = self._offset_x + x * self._scale
        cy = self._offset_y - y * self._scale   # Y 翻转
        return cx, cy

    def _canvas_to_world(self, cx: float, cy: float) -> tuple[float, float]:
        x = (cx - self._offset_x) / self._scale
        y = (self._offset_y - cy) / self._scale  # Y 翻转
        return x, y

    def _zoom(self, factor: float):
        """以画布中心为锚点缩放。"""
        canvas_w, canvas_h = self._canvas_size()
        cx_center = canvas_w / 2.0
        cy_center = canvas_h / 2.0

        # 锚点在世界坐标系下的位置（缩放前后保持不变）
        anchor_x, anchor_y = self._canvas_to_world(cx_center, cy_center)

        new_scale = self._scale * factor
        if new_scale <= 1e-9:
            return
        self._scale = new_scale

        # 重新计算 offset 使锚点仍落在画布中心
        self._offset_x = cx_center - anchor_x * self._scale
        self._offset_y = cy_center + anchor_y * self._scale

        self._draw()

    def _on_fit(self):
        self._fit_view()
        self._draw()

    def _on_mousewheel(self, event):
        if event.delta > 0:
            self._zoom(1.2)
        else:
            self._zoom(1 / 1.2)

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def _draw(self):
        self.canvas.delete('all')
        if not self.segments or self.query_engine is None:
            return

        for seg in self.segments:
            self._draw_segment(seg)

        # 起点/终点标签
        first_seg = self.segments[0]
        last_seg = self.segments[-1]
        start_cx, start_cy = self._world_to_canvas(
            first_seg.start_point.x, first_seg.start_point.y
        )
        end_cx, end_cy = self._world_to_canvas(
            last_seg.end_point.x, last_seg.end_point.y
        )
        self.canvas.create_oval(
            start_cx - 4, start_cy - 4, start_cx + 4, start_cy + 4,
            fill='#4CAF50', outline='#2E7D32',
        )
        self.canvas.create_text(
            start_cx, start_cy - 12, text='起点', fill='#2E7D32',
            font=('Microsoft YaHei', 9, 'bold'),
        )
        self.canvas.create_oval(
            end_cx - 4, end_cy - 4, end_cx + 4, end_cy + 4,
            fill='#F44336', outline='#B71C1C',
        )
        self.canvas.create_text(
            end_cx, end_cy - 12, text='终点', fill='#B71C1C',
            font=('Microsoft YaHei', 9, 'bold'),
        )

    def _draw_segment(self, seg: Segment):
        """沿线元采样若干点并连成平滑折线。"""
        seg_len = seg.length
        if seg_len <= 0:
            # 退化为单点
            cx, cy = self._world_to_canvas(
                seg.start_point.x, seg.start_point.y
            )
            color = SEGMENT_COLORS.get(seg.seg_type, '#333333')
            self.canvas.create_oval(
                cx - 2, cy - 2, cx + 2, cy + 2, fill=color, outline=color
            )
            return

        n = int(max(20, seg_len / 2))
        if n > 500:
            n = 500
        if n < 2:
            n = 2

        step = seg_len / (n - 1)
        points: list[float] = []
        for i in range(n):
            mileage = seg.start_mileage + i * step
            try:
                result = self.query_engine.query(mileage)
            except ValueError:
                continue
            cx, cy = self._world_to_canvas(result.x, result.y)
            points.extend((cx, cy))

        color = SEGMENT_COLORS.get(seg.seg_type, '#333333')
        if len(points) >= 4:
            self.canvas.create_line(
                *points, fill=color, width=2, smooth=True
            )

    # ------------------------------------------------------------------
    # 悬停提示
    # ------------------------------------------------------------------
    def _on_mouse_move(self, event):
        if not self.segments or self.query_engine is None:
            self._hide_tooltip()
            return

        wx, wy = self._canvas_to_world(event.x, event.y)

        # 在每段上采样 20 个点，找最近点
        best_dist2 = float('inf')
        best_x = best_y = 0.0
        best_mileage = 0.0

        for seg in self.segments:
            seg_len = seg.length
            if seg_len <= 0:
                samples = [(seg.start_mileage, seg.start_point.x, seg.start_point.y)]
            else:
                n = 20
                step = seg_len / (n - 1)
                samples = []
                for i in range(n):
                    mileage = seg.start_mileage + i * step
                    try:
                        result = self.query_engine.query(mileage)
                    except ValueError:
                        continue
                    samples.append((mileage, result.x, result.y))

            for mileage, px, py in samples:
                d2 = (px - wx) ** 2 + (py - wy) ** 2
                if d2 < best_dist2:
                    best_dist2 = d2
                    best_x, best_y = px, py
                    best_mileage = mileage

        # 阈值：20 像素对应的世界距离
        threshold = _HIT_PIXELS / self._scale if self._scale > 0 else 0.0
        if best_dist2 <= threshold * threshold:
            cx, cy = self._world_to_canvas(best_x, best_y)
            text = f"里程: {best_mileage:.2f}m\n坐标: ({best_x:.2f}, {best_y:.2f})"
            self._show_tooltip(event.x_root, event.y_root, text)
        else:
            self._hide_tooltip()

    def _show_tooltip(self, screen_x: int, screen_y: int, text: str):
        if self.tooltip is not None:
            self._hide_tooltip()

        self.tooltip = tk.Toplevel(self.canvas)
        self.tooltip.wm_overrideredirect(True)
        label = tk.Label(
            self.tooltip,
            text=text,
            justify=tk.LEFT,
            background='#FFFFE0',
            relief=tk.SOLID,
            borderwidth=1,
            font=('Microsoft YaHei', 9),
        )
        label.pack(ipadx=4, ipady=2)
        self.tooltip.wm_geometry(f"+{screen_x + 12}+{screen_y + 12}")

    def _hide_tooltip(self, _event=None):
        if self.tooltip is not None:
            try:
                self.tooltip.destroy()
            except tk.TclError:
                pass
            self.tooltip = None
