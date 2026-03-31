"""
将 S_CORNELL_BOX.stl 拆分为三个独立 STL 文件：
  - S_CORNELL_BOX_outer.stl   (外盒：地板+天花板+3面墙)
  - S_CORNELL_BOX_tall.stl    (高 box, 高度 33)
  - S_CORNELL_BOX_short.stl   (矮 box, 高度 16.5)

算法：基于顶点连通性将三角面片分为连通分量，再按 z 跨度识别身份。
"""

import re
import sys
from pathlib import Path
from collections import defaultdict


def parse_ascii_stl(filepath: str):
    """解析 ASCII STL，返回 [(normal, (v0, v1, v2)), ...]"""
    text = Path(filepath).read_text()
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
        normal = tuple(g[0:3])
        v0 = tuple(g[3:6])
        v1 = tuple(g[6:9])
        v2 = tuple(g[9:12])
        facets.append((normal, (v0, v1, v2)))
    return facets


def quantize(v, decimals=4):
    """将顶点坐标四舍五入以合并浮点误差"""
    return tuple(round(c, decimals) for c in v)


def find_connected_components(facets):
    """Union-Find 按共享顶点将三角面片分组为连通分量"""
    parent = list(range(len(facets)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # 建立 vertex → facet indices 映射
    vert_to_facets = defaultdict(list)
    for i, (_, verts) in enumerate(facets):
        for v in verts:
            key = quantize(v)
            vert_to_facets[key].append(i)

    # 共享同一顶点的 facets 合并
    for indices in vert_to_facets.values():
        for j in range(1, len(indices)):
            union(indices[0], indices[j])

    # 收集分量
    components = defaultdict(list)
    for i in range(len(facets)):
        components[find(i)].append(i)

    return list(components.values())


def z_extent(facets, indices):
    """返回一组 facets 的 (z_min, z_max)"""
    zs = []
    for i in indices:
        for v in facets[i][1]:
            zs.append(v[2])
    return min(zs), max(zs)


def write_ascii_stl(filepath: str, facets, indices, solid_name="solid"):
    lines = [f"solid {solid_name}"]
    for i in indices:
        n, (v0, v1, v2) = facets[i]
        lines.append(f" facet normal {n[0]} {n[1]} {n[2]}")
        lines.append("  outer loop")
        for v in (v0, v1, v2):
            lines.append(f"   vertex {v[0]} {v[1]} {v[2]}")
        lines.append("  endloop")
        lines.append(" endfacet")
    lines.append("endsolid")
    Path(filepath).write_text("\n".join(lines) + "\n")


def main():
    default_path = r"D:\Stardis-GPU\Stardis-Starter-Pack\cbox\S_CORNELL_BOX.stl"
    stl_path = sys.argv[1] if len(sys.argv) > 1 else default_path

    if not Path(stl_path).exists():
        print(f"Error: file not found: {stl_path}")
        sys.exit(1)

    facets = parse_ascii_stl(stl_path)
    print(f"Parsed {len(facets)} facets from {stl_path}")

    components = find_connected_components(facets)
    print(f"Found {len(components)} connected components (sizes: {[len(c) for c in components]})")

    if len(components) != 3:
        print(f"WARNING: expected 3 components, got {len(components)}")

    # 按 z 跨度识别：外盒跨度最大，高 box 次之，矮 box 最小
    comp_info = []
    for comp in components:
        zmin, zmax = z_extent(facets, comp)
        comp_info.append((zmax - zmin, comp, zmin, zmax))
    comp_info.sort(key=lambda x: x[0], reverse=True)

    labels = ["outer", "tall", "short"]
    out_dir = Path(stl_path).parent

    for (span, indices, zmin, zmax), label in zip(comp_info, labels):
        out_file = out_dir / f"S_CORNELL_BOX_{label}.stl"
        write_ascii_stl(str(out_file), facets, sorted(indices), solid_name=label)
        print(f"  {label:6s}: {len(indices):3d} facets, z=[{zmin:.2f}, {zmax:.2f}], span={span:.2f}  →  {out_file.name}")

    print("Done.")


if __name__ == "__main__":
    main()
