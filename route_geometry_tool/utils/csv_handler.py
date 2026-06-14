"""CSV导入导出。"""
from __future__ import annotations

import csv
import io

from route_geometry_tool.core.models import JunctionPoint


CSV_HEADERS = ['里程', 'X坐标', 'Y坐标', '前缓长', '半径', '后缓长']


def export_csv(junctions: list[JunctionPoint]) -> str:
    """导出为CSV字符串。

    写入表头行，然后每行依次写出 6 个字段，每个值保留 6 位小数。

    Args:
        junctions: 待导出的 :class:`JunctionPoint` 列表。

    Returns:
        CSV 文本（含表头），使用 CRLF 换行。
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_HEADERS)
    for jd in junctions:
        writer.writerow([
            round(jd.mileage, 6),
            round(jd.x, 6),
            round(jd.y, 6),
            round(jd.l1, 6),
            round(jd.radius, 6),
            round(jd.l2, 6),
        ])
    return output.getvalue()


def import_csv(csv_text: str) -> list[JunctionPoint]:
    """从CSV字符串导入。

    - 检测是否有表头：尝试 float(first_row[0])，失败则视为有表头。
    - 跳过无法解析的行（非 6 列或解析失败）。
    - 字段顺序：mileage, x, y, l1, radius, l2。

    Args:
        csv_text: CSV 文本（可能含表头）。

    Returns:
        解析得到的 :class:`JunctionPoint` 列表。
    """
    reader = csv.reader(io.StringIO(csv_text.strip()))
    rows = list(reader)

    result: list[JunctionPoint] = []
    for i, row in enumerate(rows):
        if not row:
            continue
        # 第一行做表头检测：解析失败则当作表头跳过。
        if i == 0:
            try:
                float(row[0])
            except (ValueError, IndexError):
                continue
        # 需要恰好 6 列。
        if len(row) < 6:
            continue
        try:
            mileage = float(row[0])
            x = float(row[1])
            y = float(row[2])
            l1 = float(row[3])
            radius = float(row[4])
            l2 = float(row[5])
        except (ValueError, IndexError):
            continue
        result.append(JunctionPoint(mileage, x, y, l1, radius, l2))

    return result


def save_csv_file(filepath: str, junctions: list[JunctionPoint]) -> None:
    """保存到文件。

    使用 ``utf-8-sig`` 编码（带 BOM，Excel 兼容），并设置 ``newline=''``
    以避免在 Windows 上出现多余空行。

    Args:
        filepath: 目标文件路径。
        junctions: 待导出的 :class:`JunctionPoint` 列表。
    """
    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        f.write(export_csv(junctions))


def load_csv_file(filepath: str) -> list[JunctionPoint]:
    """从文件加载。

    使用 ``utf-8-sig`` 编码读取（兼容带 BOM 的文件）。

    Args:
        filepath: 源文件路径。

    Returns:
        解析得到的 :class:`JunctionPoint` 列表。
    """
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        return import_csv(f.read())
