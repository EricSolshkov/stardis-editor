"""
将外盒 S_CORNELL_BOX_outer.stl 延拓为封闭结构。

新增 18 个三角面片：
  - 上/下/左/右/后 各 2 个三角形 = 10
  - 前面 (朝摄像机方向) 环形 (外矩形减内矩形孔) = 8

外盒高 H ≈ 54.88，延拓后各方向总边长约 3H：上下各延 H，左右前后各延 H。
法线朝内（朝场景中心），与原有外盒法线方向一致。
"""

import re
import sys
from pathlib import Path


# ── STL 解析 / 写出 ───────────────────────────────────────────────

def parse_ascii_stl(filepath):
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
        v0, v1, v2 = tuple(g[3:6]), tuple(g[6:9]), tuple(g[9:12])
        facets.append((normal, (v0, v1, v2)))
    return facets


def write_ascii_stl(filepath, facets, solid_name="outer_closed"):
    lines = [f"solid {solid_name}"]
    for n, (v0, v1, v2) in facets:
        lines.append(f" facet normal {n[0]} {n[1]} {n[2]}")
        lines.append("  outer loop")
        for v in (v0, v1, v2):
            lines.append(f"   vertex {v[0]} {v[1]} {v[2]}")
        lines.append("  endloop")
        lines.append(" endfacet")
    lines.append("endsolid")
    Path(filepath).write_text("\n".join(lines) + "\n")


# ── 向量工具 ──────────────────────────────────────────────────────

def vsub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])

def vcross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )

def vdot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

def vnorm(v):
    L = (v[0] ** 2 + v[1] ** 2 + v[2] ** 2) ** 0.5
    return (v[0] / L, v[1] / L, v[2] / L) if L > 1e-12 else (0, 0, 0)


def _make_tri(a, b, c, desired_normal):
    """返回单个三角形，自动调整绕序使法线与 desired_normal 同向。"""
    n = vnorm(vcross(vsub(b, a), vsub(c, a)))
    if vdot(n, desired_normal) > 0:
        return (desired_normal, (a, b, c))
    else:
        return (desired_normal, (a, c, b))


def make_quad(v0, v1, v2, v3, desired_normal):
    """
    将四边形 (v0, v1, v2, v3) 拆分为 2 个三角形。
    逐个检查并调整顶点绕序使法线与 desired_normal 同向。
    """
    return [
        _make_tri(v0, v1, v2, desired_normal),
        _make_tri(v0, v2, v3, desired_normal),
    ]


# ── 几何工具 ──────────────────────────────────────────────────────

def bounding_box(facets):
    xs, ys, zs = [], [], []
    for _, verts in facets:
        for v in verts:
            xs.append(v[0])
            ys.append(v[1])
            zs.append(v[2])
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def snap(val, threshold=1e-6):
    """将接近 0 的值精确归零"""
    return 0.0 if abs(val) < threshold else val


# ── 主流程 ────────────────────────────────────────────────────────

def main():
    default_path = r"D:\Stardis-GPU\Stardis-Starter-Pack\cbox\S_CORNELL_BOX_outer.stl"
    stl_path = sys.argv[1] if len(sys.argv) > 1 else default_path

    if not Path(stl_path).exists():
        print(f"Error: {stl_path} not found")
        sys.exit(1)

    # ① 读取已有外盒
    existing = parse_ascii_stl(stl_path)
    print(f"Read {len(existing)} existing facets")

    # ② 计算房间包围盒
    (rx0, rx1), (ry0, ry1), (rz0, rz1) = bounding_box(existing)
    rx0, rx1 = snap(rx0), snap(rx1)
    ry0, ry1 = snap(ry0), snap(ry1)
    rz0, rz1 = snap(rz0), snap(rz1)
    print(f"Room bbox: x=[{rx0:.4f}, {rx1:.4f}], "
          f"y=[{ry0:.4f}, {ry1:.4f}], z=[{rz0:.4f}, {rz1:.4f}]")

    # ③ 延拓距离 = 外盒高度
    H = rz1 - rz0
    print(f"H (height / extension) = {H:.4f}")

    # ④ 外壳包围盒 = 左右上下后延 H，前面不延拓（保持 y0=ry0 以与外盒开口齐平）
    x0 = rx0 - H
    x1 = rx1 + H
    y0 = ry0            # 前面不延拓！与外盒开口 y=0 齐平
    y1 = ry1 + H
    z0 = rz0 - H
    z1 = rz1 + H
    print(f"Enclosure: x=[{x0:.4f}, {x1:.4f}], "
          f"y=[{y0:.4f}, {y1:.4f}], z=[{z0:.4f}, {z1:.4f}]")
    print(f"Enclosure size: {x1-x0:.2f} x {y1-y0:.2f} x {z1-z0:.2f}")

    # ⑤ 外壳 8 个角点
    #   A──B
    #   │  │  z=z0 (底面)
    #   D──C
    #
    #   E──F
    #   │  │  z=z1 (顶面)
    #   H──G
    #
    # x: A,D,E,H = x0;  B,C,F,G = x1
    # y: A,B,E,F = y0;  C,D,G,H = y1

    A = (x0, y0, z0)
    B = (x1, y0, z0)
    C = (x1, y1, z0)
    D = (x0, y1, z0)
    E = (x0, y0, z1)
    F = (x1, y0, z1)
    G = (x1, y1, z1)
    Hv = (x0, y1, z1)   # 避免与变量 H 冲突

    new_facets = []

    # ── 5 个实面（法线朝外）──────────────────────────────────

    # 底面 z=z0  →  法线 (0, 0, -1)
    new_facets.extend(make_quad(A, B, C, D, (0, 0, -1)))

    # 顶面 z=z1  →  法线 (0, 0, +1)
    new_facets.extend(make_quad(E, Hv, G, F, (0, 0, 1)))

    # 右壁 x=x0  →  法线 (-1, 0, 0)
    new_facets.extend(make_quad(A, D, Hv, E, (-1, 0, 0)))

    # 左壁 x=x1  →  法线 (+1, 0, 0)
    new_facets.extend(make_quad(B, F, G, C, (1, 0, 0)))

    # 后壁 y=y1  →  法线 (0, +1, 0)
    new_facets.extend(make_quad(D, C, G, Hv, (0, 1, 0)))

    assert len(new_facets) == 10, f"Expected 10, got {len(new_facets)}"

    # ── 提取前面开口的精确 4 顶点 ────────────────────────────
    # 外盒前面开口是梯形（底边略窄），不能用 bounding box 近似！
    front_verts = []
    for _, verts in existing:
        for v in verts:
            if abs(v[1] - ry0) < 1e-6:
                front_verts.append(v)
    # 去重：按 snap 后坐标
    seen = set()
    unique_front = []
    for v in front_verts:
        key = (round(v[0], 4), round(v[1], 4), round(v[2], 4))
        if key not in seen:
            seen.add(key)
            unique_front.append(v)
    # Snap 所有坐标消除浮点噪声（如 z=6.77e-15 → 0）
    unique_front = [(snap(v[0]), snap(v[1]), snap(v[2])) for v in unique_front]
    # 按 (z, x) 排序找到 4 个角：BL, BR, TL, TR
    unique_front.sort(key=lambda v: (v[2], v[0]))
    print(f"\nFront opening vertices (exact):")
    for v in unique_front:
        print(f"  ({v[0]:.4f}, {v[1]:.4f}, {v[2]:.4f})")

    # BL=底左, BR=底右, TL=顶左, TR=顶右
    fBL = unique_front[0]   # min z, min x  (-55.28, 0, ~0)
    fBR = unique_front[1]   # min z, max x  (0, 0, 0)
    fTL = unique_front[2]   # max z, min x  (-55.6, 0, 54.88)
    fTR = unique_front[3]   # max z, max x  (~0, 0, 54.88)

    # ── 前面环形：逐边缝合外框与内框 ────────────────────────
    #
    # 外框顶点（y=y0 平面，逆时针从底左起）：
    #   Ao=(x0,y0,z0)  Bo=(x1,y0,z0)  Co=(x1,y0,z1)  Do=(x0,y0,z1)
    # 内框顶点（外盒前缘开口，同序）：
    #   Ai=fBL         Bi=fBR         Ci=fTR          Di=fTL
    #
    # 每条边对应 2 个三角形（共 8 个），缝合方式：
    #   底边 Ao-Bo / Ai-Bi : (Ao,Bo,Ai) + (Bi,Ai,Bo)
    #   右边 Bo-Co / Bi-Ci : (Bo,Co,Bi) + (Ci,Bi,Co)
    #   顶边 Co-Do / Ci-Di : (Co,Do,Ci) + (Di,Ci,Do)
    #   左边 Do-Ao / Di-Ai : (Do,Ao,Di) + (Ai,Di,Ao)

    Ao = (x0, y0, z0)
    Bo = (x1, y0, z0)
    Co = (x1, y0, z1)
    Do = (x0, y0, z1)
    Ai = (fBL[0], y0, fBL[2])
    Bi = (fBR[0], y0, fBR[2])
    Ci = (fTR[0], y0, fTR[2])
    Di = (fTL[0], y0, fTL[2])

    n_front = (0, -1, 0)

    # 底边
    new_facets.append(_make_tri(Ao, Bo, Ai, n_front))
    new_facets.append(_make_tri(Bi, Ai, Bo, n_front))
    # 右边
    new_facets.append(_make_tri(Bo, Co, Bi, n_front))
    new_facets.append(_make_tri(Ci, Bi, Co, n_front))
    # 顶边
    new_facets.append(_make_tri(Co, Do, Ci, n_front))
    new_facets.append(_make_tri(Di, Ci, Do, n_front))
    # 左边
    new_facets.append(_make_tri(Do, Ao, Di, n_front))
    new_facets.append(_make_tri(Ai, Di, Ao, n_front))

    assert len(new_facets) == 18, f"Expected 18, got {len(new_facets)}"

    # ⑥ 验证所有新面片法线
    print("\nNew facet normals:")
    labels = [
        "Bottom-1", "Bottom-2",
        "Top-1", "Top-2",
        "Right(x0)-1", "Right(x0)-2",
        "Left(x1)-1", "Left(x1)-2",
        "Back-1", "Back-2",
        "Front-bottom-1", "Front-bottom-2",
        "Front-right-1", "Front-right-2",
        "Front-top-1", "Front-top-2",
        "Front-left-1", "Front-left-2",
    ]
    all_ok = True
    for i, (n, verts) in enumerate(new_facets):
        computed = vnorm(vcross(vsub(verts[1], verts[0]), vsub(verts[2], verts[0])))
        ok = vdot(computed, n) > 0.99
        mark = "OK" if ok else "FAIL"
        if not ok:
            all_ok = False
        print(f"  {labels[i]:20s}  desired=({n[0]:+.0f},{n[1]:+.0f},{n[2]:+.0f})  "
              f"computed=({computed[0]:+.4f},{computed[1]:+.4f},{computed[2]:+.4f})  [{mark}]")

    if not all_ok:
        print("\nERROR: some normals are incorrect!")
        sys.exit(1)

    # ⑦ 合并输出
    all_facets = existing + new_facets
    out_path = Path(stl_path).parent / "S_CORNELL_BOX_outer_closed.stl"
    write_ascii_stl(str(out_path), all_facets)
    print(f"\nWrote {len(all_facets)} facets "
          f"({len(existing)} existing + {len(new_facets)} new)")
    print(f"Output: {out_path}")


if __name__ == "__main__":
    main()
