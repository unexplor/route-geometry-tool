# 线路平面几何计算工具 - 设计文档

## 概述

铁路线路平面几何计算工具，输入交点（JD）数据后自动构建线路模型，支持里程查询和图形展示。Python + Tkinter 实现，3天内完成。

## 技术栈

- **语言**: Python 3.10+
- **GUI**: Tkinter（标准库）
- **绘图**: Tkinter Canvas（图形绘制加分项）
- **依赖**: 仅标准库，无需第三方包

## 架构：模块化分层

```
route_geometry_tool/
├── core/                  # 纯数学计算层（零UI依赖）
│   ├── models.py          # 数据模型：JunctionPoint、Segment等
│   ├── geometry.py        # 几何计算：缓和曲线、圆曲线、直线
│   ├── route_builder.py   # 线路构建：由交点生成完整线路
│   └── query.py           # 里程查询：坐标、切线角、法线
├── ui/                    # Tkinter界面层
│   ├── main_window.py     # 主窗口
│   ├── input_table.py     # 交点输入表格
│   ├── query_panel.py     # 查询面板
│   └── canvas_view.py     # 图形绘制（加分项）
├── utils/
│   └── csv_handler.py     # CSV导入导出
├── tests/                 # 单元测试
│   └── test_geometry.py
└── main.py                # 入口
```

## 核心数据模型

### JunctionPoint（交点）

```python
@dataclass
class JunctionPoint:
    mileage: float    # 里程（m）
    x: float          # X坐标
    y: float          # Y坐标
    l1: float         # 前缓和曲线长度（m）
    radius: float     # 圆曲线半径（m），0=直线
    l2: float         # 后缓和曲线长度（m）
```

### Segment（线路段）

线路由以下段类型按顺序拼接：

| 段类型 | 起止点 | 说明 |
|--------|--------|------|
| StraightSegment | 前HZ → 后ZH | 直线段 |
| TransitionSegment | ZH → HY | 前缓和曲线（曲率0→1/R） |
| CircularSegment | HY → YH | 圆曲线（曲率恒定=1/R） |
| TransitionSegment | YH → HZ | 后缓和曲线（曲率1/R→0） |

每段存储：起始里程、终止里程、起始坐标、终止坐标、段类型、几何参数。

### 关键推导参数

对每个有曲线的交点（radius > 0）：

```
偏角 α = π - angle(前直线方向, 后直线方向)
内移距 p = Ls²/(24R)
切垂距 m = Ls/2 - Ls³/(240R²)
切线长 T = (R + p) * tan(α/2) + m
缓和曲线角 β = Ls/(2R)
曲线长 Ly = R*(α - β1 - β2)
```

## 几何计算（核心）

### 缓和曲线 - 回旋线（Clothoid）

曲率随弧长线性变化。以ZH点为原点，切线方向为x轴：

```
参数: l = 从ZH起的弧长, Ls = 缓和曲线全长, R = 圆曲线半径

局部坐标（级数展开，取前2-3项）：
x(l) = l - l⁵/(40·R²·Ls²) + l⁹/(3456·R⁴·Ls⁴)
y(l) = l³/(6·R·Ls) - l⁷/(336·R³·Ls³) + l¹¹/(42240·R⁵·Ls⁵)

切线方位角:
θ(l) = l²/(2·R·Ls)

坐标转换（局部→全局）：
X = x·cos(α₀) - y·sin(α₀) + X_ZH
Y = x·sin(α₀) + y·cos(α₀) + Y_ZH
```

后缓和曲线（从HZ方向）需反向处理。

### 圆曲线

用圆心+起始角+扫描角方式：

```
圆心 = HY点 + R·(法线方向)
起始角 = HY处切线方向角
扫描角 = Ly / R
θ(s) = 起始角 + s/R * sign(偏转方向)
X(s) = Xc + R·cos(θ(s))
Y(s) = Yc + R·sin(θ(s))
```

### 直线段

简单线性插值：

```
方向角 = atan2(Y₂-Y₁, X₂-X₁)
X(s) = X₁ + s·cos(方向角)
Y(s) = Y₁ + s·sin(方向角)
```

### 查询接口

```python
@dataclass
class QueryResult:
    x: float           # X坐标
    y: float           # Y坐标
    tangent_angle: float  # 切线方向角（弧度）
    tangent_vector: tuple # (cos α, sin α)
    normal_vector: tuple  # (-sin α, cos α) 切线逆时针旋转90°

def query_by_mileage(mileage: float) -> QueryResult
def batch_query(start: float, end: float, step: float) -> list[QueryResult]
```

## UI界面

### 布局

- **顶部**: 标题栏 + [导入CSV] [导出CSV] 按钮
- **交点表格**: Treeview可编辑表格，列=里程/X/Y/前缓长/半径/后缓长
- **操作栏**: [添加行] [删除行] [构建线路]
- **查询区**: 单点查询 + 批量查询（起止里程+步长）
- **结果区**: 查询结果表格
- **底部Canvas**: 图形绘制（加分项），不同颜色区分线型

### 功能流程

1. **输入**: 表格填写或CSV导入交点数据
2. **构建**: 点击构建→RouteBuilder生成所有段→验证连续性
3. **查询**: 输入里程→定位段→计算→返回结果
4. **绘制**: 遍历段在Canvas上绘制（直线黑/缓和蓝/圆曲线红）

## 边界处理

- radius=0 → 纯直线交点，不生成曲线段
- l1=0 或 l2=0 → 无对应缓和曲线，只有圆曲线
- 里程超出线路范围 → 错误提示
- 输入验证: 半径≥0, 缓长≥0
- 首尾交点通常radius=0（起点和终点）

## 开发策略

分阶段实现，确保核心功能优先：

### Phase 1: 核心计算（Day 1）
- models.py 数据模型
- geometry.py 几何计算（三种曲线）
- 单元测试验证正确性

### Phase 2: 线路构建+查询（Day 1-2）
- route_builder.py 由交点生成线路
- query.py 里程查询
- CSV导入导出

### Phase 3: UI界面（Day 2）
- Tkinter主窗口、输入表格
- 查询面板、结果展示
- CSV操作集成

### Phase 4: 图形绘制（Day 3，加分项）
- Canvas绘图
- 颜色区分、标注交点
- 悬停显示信息
