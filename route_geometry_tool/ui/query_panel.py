"""查询面板：单点查询 + 批量查询 + 结果显示。"""
from __future__ import annotations

import math
import tkinter as tk
from tkinter import messagebox, ttk

from route_geometry_tool.core.models import QueryResult
from route_geometry_tool.core.query import RouteQuery

# 结果表格列键与表头
RESULT_COLUMNS = [
    'mileage', 'x', 'y', 'angle', 'tx', 'ty', 'nx', 'ny',
]
RESULT_HEADERS = [
    '里程(m)', 'X', 'Y', '切线角(°)',
    '切向量X', '切向量Y', '法向量X', '法向量Y',
]
RESULT_WIDTHS = [80, 90, 90, 90, 80, 80, 80, 80]


class QueryPanel(tk.LabelFrame):
    """里程查询面板。

    提供单点查询与批量查询两种方式，查询结果同时以单行摘要和
    多列结果表格的形式展示。切线角内部以弧度存储，界面展示时
    转换为度。
    """

    def __init__(self, parent):
        super().__init__(parent, text="里程查询", padx=5, pady=5)
        self.query_engine: RouteQuery | None = None
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _setup_ui(self):
        # === 单点查询行 ===
        single_row = tk.Frame(self)
        single_row.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))

        tk.Label(single_row, text="里程(m):").pack(side=tk.LEFT)
        self.mileage_var = tk.StringVar()
        tk.Entry(single_row, textvariable=self.mileage_var, width=15).pack(
            side=tk.LEFT, padx=4
        )
        tk.Button(single_row, text="查询", command=self._query_single).pack(
            side=tk.LEFT, padx=2
        )

        # 单点结果摘要（等宽字体，左对齐）
        self.single_result_var = tk.StringVar(value="")
        tk.Label(
            self,
            textvariable=self.single_result_var,
            font=('Consolas', 10),
            anchor=tk.W,
            justify=tk.LEFT,
        ).pack(side=tk.TOP, fill=tk.X, pady=(0, 4))

        # === 批量查询行 ===
        batch_row = tk.Frame(self)
        batch_row.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))

        tk.Label(batch_row, text="起始里程:").pack(side=tk.LEFT)
        self.start_var = tk.StringVar()
        tk.Entry(batch_row, textvariable=self.start_var, width=10).pack(
            side=tk.LEFT, padx=(2, 6)
        )

        tk.Label(batch_row, text="终止里程:").pack(side=tk.LEFT)
        self.end_var = tk.StringVar()
        tk.Entry(batch_row, textvariable=self.end_var, width=10).pack(
            side=tk.LEFT, padx=(2, 6)
        )

        tk.Label(batch_row, text="步长:").pack(side=tk.LEFT)
        self.step_var = tk.StringVar(value="10")
        tk.Entry(batch_row, textvariable=self.step_var, width=8).pack(
            side=tk.LEFT, padx=(2, 6)
        )

        tk.Button(
            batch_row, text="批量查询", command=self._query_batch
        ).pack(side=tk.LEFT, padx=2)

        # === 结果表格 ===
        tree_container = tk.Frame(self)
        tree_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.result_tree = ttk.Treeview(
            tree_container,
            columns=RESULT_COLUMNS,
            show='headings',
            height=4,
            selectmode='browse',
        )
        for col, header, width in zip(
            RESULT_COLUMNS, RESULT_HEADERS, RESULT_WIDTHS
        ):
            self.result_tree.heading(col, text=header)
            self.result_tree.column(
                col, width=width, anchor=tk.CENTER, stretch=True
            )

        y_scroll = ttk.Scrollbar(
            tree_container,
            orient=tk.VERTICAL,
            command=self.result_tree.yview,
        )
        self.result_tree.configure(yscrollcommand=y_scroll.set)

        self.result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    # ------------------------------------------------------------------
    # 外部接口
    # ------------------------------------------------------------------
    def set_query_engine(self, engine: RouteQuery):
        """注入查询引擎，并把批量查询的起止里程默认置为线路里程范围。"""
        self.query_engine = engine
        self.start_var.set(f"{engine.min_mileage:.3f}")
        self.end_var.set(f"{engine.max_mileage:.3f}")

    # ------------------------------------------------------------------
    # 查询动作
    # ------------------------------------------------------------------
    def _query_single(self):
        """单点查询：解析里程、调用引擎、刷新摘要与结果表格。"""
        if self.query_engine is None:
            messagebox.showwarning("提示", "请先构建线路")
            return

        raw = self.mileage_var.get().strip()
        try:
            mileage = float(raw)
        except ValueError:
            messagebox.showerror(
                "查询错误", f"请输入有效的里程数值，得到：{raw!r}"
            )
            return

        try:
            result = self.query_engine.query(mileage)
        except ValueError as exc:
            messagebox.showerror("查询错误", str(exc))
            return

        tx, ty = result.tangent_vector
        nx, ny = result.normal_vector
        self.single_result_var.set(
            f"坐标=({result.x:.4f}, {result.y:.4f})  "
            f"切线角={math.degrees(result.tangent_angle):.4f}°  "
            f"切向量=({tx:.6f}, {ty:.6f})  "
            f"法向量=({nx:.6f}, {ny:.6f})"
        )
        self._show_results([result])

    def _query_batch(self):
        """批量查询：解析起止与步长、调用引擎、刷新结果表格。"""
        if self.query_engine is None:
            messagebox.showwarning("提示", "请先构建线路")
            return

        try:
            start = float(self.start_var.get().strip())
            end = float(self.end_var.get().strip())
            step = float(self.step_var.get().strip())
        except ValueError as exc:
            messagebox.showerror(
                "查询错误", f"批量查询参数无效：{exc}"
            )
            return

        try:
            results = self.query_engine.batch_query(start, end, step)
        except ValueError as exc:
            messagebox.showerror("查询错误", str(exc))
            return

        self._show_results(results)

    # ------------------------------------------------------------------
    # 结果展示
    # ------------------------------------------------------------------
    def _show_results(self, results: list[QueryResult]):
        """清空表格并按既定精度插入 *results* 中的每一条结果。"""
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)

        for r in results:
            tx, ty = r.tangent_vector
            nx, ny = r.normal_vector
            self.result_tree.insert(
                '',
                tk.END,
                values=[
                    f"{r.mileage:.3f}",
                    f"{r.x:.4f}",
                    f"{r.y:.4f}",
                    f"{math.degrees(r.tangent_angle):.4f}",
                    f"{tx:.6f}",
                    f"{ty:.6f}",
                    f"{nx:.6f}",
                    f"{ny:.6f}",
                ],
            )
