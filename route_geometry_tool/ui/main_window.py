"""主窗口：组装所有面板。"""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

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
        self.geometry("1100x900")
        self.minsize(950, 720)

        self.query_engine: RouteQuery | None = None
        self.query_panel = None
        self.canvas_view = None
        self._paned: ttk.PanedWindow | None = None
        self._setup_ui()
        # 渲染后显式定位分隔条，让图形区域占窗口大部分
        self.after(50, self._place_sashes)

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

        # 主区域：垂直 PanedWindow，三个面板可拖动分隔条调整高度。
        # weight 越大越占空间——图形区域权重最高，输入/查询固定不弹。
        self._paned = ttk.PanedWindow(self, orient=tk.VERTICAL)
        paned = self._paned
        paned.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=4)

        # 1) 交点数据（weight=0：按内容高度，不弹性增长）
        input_frame = tk.LabelFrame(paned, text="交点数据（双击编辑）")
        paned.add(input_frame, weight=0)

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

        # 2) 查询面板（weight=0：按内容高度）—— Task 7 实现，缺失则占位
        if QueryPanel is not None:
            self.query_panel = QueryPanel(paned)
            paned.add(self.query_panel, weight=0)
        else:
            placeholder = tk.LabelFrame(paned, text="查询")
            paned.add(placeholder, weight=0)
            tk.Label(
                placeholder,
                text="查询面板待实现",
                fg="gray",
            ).pack(side=tk.TOP, pady=20)

        # 3) 图形绘制（weight=4：弹性占大头）—— Task 8 实现，缺失则占位
        if CanvasView is not None:
            self.canvas_view = CanvasView(paned)
            paned.add(self.canvas_view, weight=4)
        else:
            self.canvas_view = None
            placeholder2 = tk.LabelFrame(paned, text="图形")
            paned.add(placeholder2, weight=1)
            tk.Label(placeholder2, text="图形绘制待实现").pack()

        # 设置各窗格的最小高度，防止拖动时压没
        try:
            paned.paneconfigure(input_frame, minsize=180)
            if QueryPanel is not None:
                paned.paneconfigure(self.query_panel, minsize=160)
            if self.canvas_view is not None:
                paned.paneconfigure(self.canvas_view, minsize=300)
        except tk.TclError:
            pass

        # 状态行（蓝色，底部）
        self.status_var = tk.StringVar(value="就绪")
        tk.Label(
            self,
            textvariable=self.status_var,
            fg="blue",
            anchor=tk.W,
        ).pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(4, 8))

    def _place_sashes(self):
        """渲染后显式定位 PanedWindow 的两条分隔条。

        ttk.PanedWindow 的 ``weight`` 只在"有剩余空间"时生效，而输入表格
        与查询面板的固有高度往往已经占满窗口，导致图形区域被压扁。这里
        在窗口布局完成后按比例强制设置 sashpos：输入约 22%、查询约 22%、
        图形约 56%，让线路平面图拿到窗口大部分高度。
        """
        if self._paned is None:
            return
        try:
            self.update_idletasks()
            total = self._paned.winfo_height()
            if total < 100:
                # 尚未完成布局，稍后重试
                self.after(80, self._place_sashes)
                return
            self._paned.sashpos(0, int(total * 0.24))   # 输入 / 查询 分界
            self._paned.sashpos(1, int(total * 0.46))   # 查询 / 图形 分界
        except tk.TclError:
            pass

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
