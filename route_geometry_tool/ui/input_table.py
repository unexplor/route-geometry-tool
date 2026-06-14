"""可编辑的交点输入表格（Treeview）。"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from route_geometry_tool.core.models import JunctionPoint

# 列键（与 JunctionPoint 字段顺序一致）
COLUMNS = ['mileage', 'x', 'y', 'l1', 'radius', 'l2']
# 表头显示文本
HEADERS = ['里程(m)', 'X坐标', 'Y坐标', '前缓长(m)', '半径(m)', '后缓长(m)']
# 每列宽度（像素）
COL_WIDTHS = [100, 100, 100, 90, 90, 90]


class InputTable(tk.Frame):
    """交点输入表格面板。

    以可编辑 Treeview 的形式管理一行行交点数据。每行 6 个数值列，
    双击单元格进入编辑状态。``get_junctions`` 返回已校验的
    :class:`JunctionPoint` 列表；任意一行无效时弹出错误并返回空列表。
    """

    def __init__(self, parent, on_change=None):
        super().__init__(parent)
        self.on_change = on_change
        self._entry: tk.Entry | None = None
        self._setup_widgets()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _setup_widgets(self):
        # 表格容器（Treeview + 纵向滚动条）
        tree_container = tk.Frame(self)
        tree_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(
            tree_container,
            columns=COLUMNS,
            show='headings',
            height=6,
            selectmode='browse',
        )
        for col, header, width in zip(COLUMNS, HEADERS, COL_WIDTHS):
            self.tree.heading(col, text=header)
            self.tree.column(
                col,
                width=width,
                anchor=tk.CENTER,
                stretch=True,
            )

        y_scroll = ttk.Scrollbar(
            tree_container,
            orient=tk.VERTICAL,
            command=self.tree.yview,
        )
        self.tree.configure(yscrollcommand=y_scroll.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 双击进入编辑
        self.tree.bind('<Double-1>', self._on_double_click)

        # 操作按钮栏
        btn_bar = tk.Frame(self)
        btn_bar.pack(side=tk.TOP, fill=tk.X, pady=4)

        tk.Button(btn_bar, text='添加行', command=self._add_row).pack(
            side=tk.LEFT, padx=2
        )
        tk.Button(btn_bar, text='删除行', command=self._delete_row).pack(
            side=tk.LEFT, padx=2
        )
        tk.Button(btn_bar, text='清空', command=self._clear).pack(
            side=tk.LEFT, padx=2
        )
        tk.Button(btn_bar, text='加载示例', command=self._load_example).pack(
            side=tk.RIGHT, padx=2
        )

    # ------------------------------------------------------------------
    # 行操作
    # ------------------------------------------------------------------
    def _add_row(self):
        """追加一行；里程默认为上一行里程 + 500，列表为空时取 0。"""
        items = self.tree.get_children()
        if items:
            try:
                last_mileage = float(self.tree.set(items[-1], 'mileage'))
            except (ValueError, tk.TclError):
                last_mileage = 0.0
            default_mileage = last_mileage + 500
        else:
            default_mileage = 0.0

        self.tree.insert(
            '',
            tk.END,
            values=[default_mileage, 0, 0, 0, 0, 0],
        )
        self._notify_change()

    def _delete_row(self):
        """删除当前选中行（无选中则忽略）。"""
        selected = self.tree.selection()
        if not selected:
            return
        for item in selected:
            self.tree.delete(item)
        self._notify_change()

    def _clear(self):
        """清空全部行。"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._notify_change()

    def _load_example(self):
        """载入示例数据。

        注意：示例曲线半径取 R=300（**不要**使用 R=800）。
        R=800 时切线长约为 825，已超过约 500 的边长间距，会使 ZH
        里程变为负值，几何上不可行。R=300 可正常构建。
        """
        for item in self.tree.get_children():
            self.tree.delete(item)

        example = [
            [0, 0, 0, 0, 0, 0],           # 起点
            [500, 500, 0, 50, 300, 50],   # 左转曲线 R=300
            [900, 500, 400, 0, 0, 0],     # 终点
        ]
        for row in example:
            self.tree.insert('', tk.END, values=row)

        self._notify_change()

    # ------------------------------------------------------------------
    # 单元格编辑
    # ------------------------------------------------------------------
    def _on_double_click(self, event):
        """双击单元格，覆盖一个 Entry 进行就地编辑。"""
        region = self.tree.identify('region', event.x, event.y)
        if region != 'cell':
            return

        column = self.tree.identify_column(event.x)
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return

        # 列索引 'mx' -> 索引 m-1
        try:
            col_index = int(column.replace('#', '')) - 1
        except ValueError:
            return
        if col_index < 0 or col_index >= len(COLUMNS):
            return
        col_key = COLUMNS[col_index]

        bbox = self.tree.bbox(row_id, column)
        if not bbox:
            return
        x, y, w, h = bbox

        current_value = self.tree.set(row_id, col_key)

        # 销毁可能残留的编辑 Entry
        if self._entry is not None:
            try:
                self._entry.destroy()
            except tk.TclError:
                pass
            self._entry = None

        self._entry = tk.Entry(self.tree, borderwidth=0, highlightthickness=1)
        self._entry.place(x=x, y=y, width=w, height=h)
        self._entry.insert(0, current_value)
        self._entry.select_range(0, tk.END)
        self._entry.focus_force()

        def commit(_event=None):
            self._commit_edit(self._entry, row_id, col_key)

        def cancel(_event=None):
            self._destroy_entry()

        self._entry.bind('<Return>', commit)
        self._entry.bind('<FocusOut>', commit)
        self._entry.bind('<Escape>', cancel)

    def _commit_edit(self, entry, row_id, col_key):
        """提交编辑：校验为浮点数后写回单元格。"""
        if entry is None:
            return
        raw = entry.get().strip()
        try:
            value = float(raw)
        except ValueError:
            messagebox.showwarning(
                '输入错误',
                f'请输入有效的数字，得到：{raw!r}',
            )
            self._destroy_entry()
            return

        # 整数显示更整洁
        display = value if value != int(value) else int(value)
        self.tree.set(row_id, col_key, display)
        self._destroy_entry()
        self._notify_change()

    def _destroy_entry(self):
        if self._entry is not None:
            try:
                self._entry.destroy()
            except tk.TclError:
                pass
            self._entry = None

    # ------------------------------------------------------------------
    # 外部数据接口
    # ------------------------------------------------------------------
    def get_junctions(self) -> list[JunctionPoint]:
        """返回所有行对应的已校验 :class:`JunctionPoint` 列表。

        - 任意一行解析失败：弹出错误并返回 ``[]``。
        - 任意一行 :meth:`JunctionPoint.validate` 抛出 ``ValueError``：
          弹出错误并返回 ``[]``（validate 是抛异常而非返回列表）。
        """
        junctions: list[JunctionPoint] = []
        for index, item in enumerate(self.tree.get_children()):
            values = self.tree.set(item)
            try:
                parsed = [float(values[col]) for col in COLUMNS]
            except (ValueError, tk.TclError) as exc:
                messagebox.showerror(
                    '数据错误',
                    f'第 {index + 1} 行数据无法解析为数字：{exc}',
                )
                return []

            jd = JunctionPoint(*parsed)
            try:
                jd.validate()
            except ValueError as exc:
                messagebox.showerror(
                    '数据错误',
                    f'第 {index + 1} 行数据无效：{exc}',
                )
                return []
            junctions.append(jd)
        return junctions

    def set_junctions(self, junctions):
        """清空并以 *junctions* 重填表格。"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        for jd in junctions:
            self.tree.insert(
                '',
                tk.END,
                values=[
                    jd.mileage, jd.x, jd.y, jd.l1, jd.radius, jd.l2,
                ],
            )
        self._notify_change()

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _notify_change(self):
        if self.on_change is not None:
            try:
                self.on_change()
            except Exception:
                # 回调失败不应影响表格自身逻辑
                pass
