"""主窗口：组装所有面板。"""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox

from route_geometry_tool.core.models import SegmentType
from route_geometry_tool.core.query import RouteQuery
from route_geometry_tool.core.route_builder import RouteBuilder
from route_geometry_tool.ui.input_table import InputTable
from route_geometry_tool.utils.csv_handler import load_csv_file, save_csv_file

# QueryPanel 由 Task 7 提供；尚未实现时优雅降级为占位标签。
try:
    from route_geometry_tool.ui.query_panel import QueryPanel  # type: ignore
except ImportError:  # pragma: no cover - Task 7 之前 QueryPanel 不存在
    QueryPanel = None  # type: ignore[assignment]

# CanvasView 由 Task 8 提供；尚未实现时优雅降级为占位标签。
try:
    from route_geometry_tool.ui.canvas_view import CanvasView  # type: ignore
except ImportError:  # pragma: no cover - Task 8 之前 CanvasView 不存在
    CanvasView = None  # type: ignore[assignment]


class MainWindow(tk.Tk):
    """应用主窗口。

    顶部为标题与 CSV 导入/导出按钮，中部为交点数据输入表格及
    "构建线路" 按钮，下方为状态行与查询面板（Task 7 实现）。
    """

    def __init__(self):
        super().__init__()
        self.title("线路平面几何计算工具")
        self.geometry("900x750")
        self.minsize(800, 600)

        self.query_engine: RouteQuery | None = None
        self.query_panel = None
        self.canvas_view = None
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _setup_ui(self):
        # 顶部：标题（左）+ 导入/导出按钮（右）
        top_frame = tk.Frame(self)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(8, 4))

        tk.Label(
            top_frame,
            text="线路平面几何计算工具",
            font=('Microsoft YaHei', 14, 'bold'),
        ).pack(side=tk.LEFT)

        btn_frame = tk.Frame(top_frame)
        btn_frame.pack(side=tk.RIGHT)
        tk.Button(
            btn_frame, text="导入CSV", command=self._import_csv
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            btn_frame, text="导出CSV", command=self._export_csv
        ).pack(side=tk.LEFT, padx=2)

        # 交点数据 LabelFrame
        input_frame = tk.LabelFrame(self, text="交点数据（双击编辑）")
        input_frame.pack(side=tk.TOP, fill=tk.BOTH, padx=8, pady=4)

        self.input_table = InputTable(input_frame)
        self.input_table.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=4, pady=4)

        tk.Button(
            input_frame,
            text="🔧 构建线路",
            bg="#4CAF50",
            fg="white",
            font=('Microsoft YaHei', 10, 'bold'),
            command=self._build_route,
        ).pack(side=tk.TOP, pady=4)

        # 状态行（蓝色）
        self.status_var = tk.StringVar(value="就绪")
        tk.Label(
            self,
            textvariable=self.status_var,
            fg="blue",
            anchor=tk.W,
        ).pack(side=tk.TOP, fill=tk.X, padx=8, pady=(4, 8))

        # 查询面板：Task 7 实现，缺失则占位
        if QueryPanel is not None:
            self.query_panel = QueryPanel(self)
            self.query_panel.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=4)
        else:
            placeholder = tk.LabelFrame(self, text="查询")
            placeholder.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=4)
            tk.Label(
                placeholder,
                text="查询面板待实现",
                fg="gray",
            ).pack(side=tk.TOP, pady=20)

        # 图形绘制面板：Task 8 实现，缺失则占位
        if CanvasView is not None:
            self.canvas_view = CanvasView(self)
            self.canvas_view.pack(side=tk.TOP, fill=tk.BOTH, padx=10, pady=5, expand=True)
        else:
            self.canvas_view = None
            tk.Label(self, text="图形绘制待实现").pack()

    # ------------------------------------------------------------------
    # 构建线路
    # ------------------------------------------------------------------
    def _build_route(self):
        junctions = self.input_table.get_junctions()
        if not junctions:
            messagebox.showwarning("提示", "请先输入有效的交点数据。")
            return

        try:
            segments = RouteBuilder(junctions).build()
            self.query_engine = RouteQuery(segments)

            summary = self._summarize_segments(segments)
            self.status_var.set(
                f"构建成功：{len(junctions)} 个交点，{len(segments)} 个线元"
                f"（{summary}），里程范围 "
                f"[{self.query_engine.min_mileage:.2f}, "
                f"{self.query_engine.max_mileage:.2f}] m"
            )

            if self.query_panel is not None and hasattr(
                self.query_panel, 'set_query_engine'
            ):
                self.query_panel.set_query_engine(self.query_engine)

            if self.canvas_view is not None:
                self.canvas_view.set_data(segments, self.query_engine)
        except Exception as exc:  # noqa: BLE001 - 面向用户的兜底
            self.query_engine = None
            self.status_var.set(f"构建失败：{exc}")
            messagebox.showerror("构建失败", str(exc))

    @staticmethod
    def _summarize_segments(segments) -> str:
        """统计各类线元数量，用于状态行展示。"""
        counts = {SegmentType.STRAIGHT: 0, SegmentType.TRANSITION: 0, SegmentType.CIRCULAR: 0}
        for seg in segments:
            counts[seg.seg_type] = counts.get(seg.seg_type, 0) + 1
        return (
            f"直线 {counts[SegmentType.STRAIGHT]}"
            f" / 缓和 {counts[SegmentType.TRANSITION]}"
            f" / 圆曲线 {counts[SegmentType.CIRCULAR]}"
        )

    # ------------------------------------------------------------------
    # CSV 导入 / 导出
    # ------------------------------------------------------------------
    def _import_csv(self):
        path = filedialog.askopenfilename(
            title="选择 CSV 文件",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            junctions = load_csv_file(path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("导入失败", str(exc))
            return
        self.input_table.set_junctions(junctions)
        self.status_var.set(f"已导入 {len(junctions)} 个交点：{path}")

    def _export_csv(self):
        junctions = self.input_table.get_junctions()
        if not junctions:
            messagebox.showwarning("提示", "没有可导出的交点数据。")
            return

        path = filedialog.asksaveasfilename(
            title="保存 CSV 文件",
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            save_csv_file(path, junctions)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("导出失败", str(exc))
            return
        self.status_var.set(f"已导出 {len(junctions)} 个交点：{path}")
