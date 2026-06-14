"""线路平面几何计算工具 — 入口。"""
import os
import sys

# 把 route_geometry_tool/ 的父目录加入 sys.path，
# 使得 ``route_geometry_tool`` 可作为顶层包被导入。
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from route_geometry_tool.ui.main_window import MainWindow


def main():
    app = MainWindow()
    app.mainloop()


if __name__ == '__main__':
    main()
