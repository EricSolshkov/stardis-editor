"""
修复 S_CORNELL_BOX_outer.stl 外盒的 -x 侧墙面不平问题。

原始 STL 中 -x 侧 4 个角点的 x 坐标不一致：
  - (y=0,   z=0)    x = -55.28   ← 偏差
  - (y=55.92, z=0)  x = -54.96   ← 偏差
  - (y=0,   z=54.88) x = -55.60  ✓
  - (y=55.92, z=54.88) x = -55.60 ✓

修复：将地板上两个 -x 侧顶点的 x 坐标统一归正为 -55.6，
使右壁成为完美平面、法线成为纯 (+1, 0, 0)。
"""

import re
import sys
from pathlib import Path


def main():
    default_path = r"D:\Stardis-GPU\Stardis-Starter-Pack\cbox\S_CORNELL_BOX_outer.stl"
    stl_path = sys.argv[1] if len(sys.argv) > 1 else default_path

    if not Path(stl_path).exists():
        print(f"Error: {stl_path} not found")
        sys.exit(1)

    text = Path(stl_path).read_text()

    # 目标 x 值 = 天花板处的正确值
    TARGET_X = -55.599998474121094

    # 需要修正的两个 x 坐标（地板上 -x 侧）
    BAD_X_VALUES = [
        -55.279998779296875,   # (y=0, z≈0)
        -54.959999084472656,   # (y=55.92, z≈0)
    ]

    fixes = 0
    for bad_x in BAD_X_VALUES:
        bad_str = f"{bad_x}"
        target_str = f"{TARGET_X}"
        count = text.count(bad_str)
        if count > 0:
            text = text.replace(bad_str, target_str)
            print(f"  Replaced x={bad_x} → {TARGET_X}  ({count} occurrences)")
            fixes += count

    if fixes == 0:
        print("No fixes needed — vertices already correct.")
        return

    # 修正受影响面片的法线
    # 简单做法：重新解析所有面片，重算法线
    facets = []
    for m in re.finditer(
        r"facet\s+normal\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)\s+"
        r"outer\s+loop\s+"
        r"vertex\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)\s+"
        r"vertex\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)\s+"
        r"vertex\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)\s+"
        r"endloop\s+endfacet",
        text,
    ):
        g = [float(m.group(i)) for i in range(1, 13)]
        v0 = (g[3], g[4], g[5])
        v1 = (g[6], g[7], g[8])
        v2 = (g[9], g[10], g[11])
        # 重算法线
        e1 = (v1[0]-v0[0], v1[1]-v0[1], v1[2]-v0[2])
        e2 = (v2[0]-v0[0], v2[1]-v0[1], v2[2]-v0[2])
        nx = e1[1]*e2[2] - e1[2]*e2[1]
        ny = e1[2]*e2[0] - e1[0]*e2[2]
        nz = e1[0]*e2[1] - e1[1]*e2[0]
        L = (nx**2 + ny**2 + nz**2)**0.5
        if L > 1e-12:
            nx, ny, nz = nx/L, ny/L, nz/L
        facets.append(((nx, ny, nz), (v0, v1, v2)))

    # 写出
    lines = ["solid outer"]
    for n, (v0, v1, v2) in facets:
        lines.append(f" facet normal {n[0]} {n[1]} {n[2]}")
        lines.append("  outer loop")
        for v in (v0, v1, v2):
            lines.append(f"   vertex {v[0]} {v[1]} {v[2]}")
        lines.append("  endloop")
        lines.append(" endfacet")
    lines.append("endsolid")

    # 备份原文件
    bak_path = Path(stl_path).with_suffix(".stl.bak")
    if not bak_path.exists():
        Path(stl_path).rename(bak_path)
        print(f"  Backup: {bak_path.name}")
    else:
        print(f"  Backup already exists: {bak_path.name}")

    Path(stl_path).write_text("\n".join(lines) + "\n")
    print(f"\n  Fixed {fixes} vertex coordinates in {len(facets)} facets")
    print(f"  Output: {Path(stl_path).name}")

    # 验证 -x 侧法线
    print("\n  -x wall facet normals after fix:")
    for i, (n, (v0, v1, v2)) in enumerate(facets):
        xs = [v0[0], v1[0], v2[0]]
        if all(abs(x - TARGET_X) < 0.01 for x in xs) or (abs(n[0]) > 0.9 and n[0] > 0):
            print(f"    F{i:2d}  n=({n[0]:+.6f}, {n[1]:+.6f}, {n[2]:+.6f})")


if __name__ == "__main__":
    main()
