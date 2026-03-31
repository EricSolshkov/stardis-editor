"""
将 cbox 场景中所有被引用的 STL 文件的坐标除以 SCALE_FACTOR，
原文件备份为 *.stl.bak，缩放后覆盖原文件。
"""

import struct
import shutil
import os

SCALE_FACTOR = 55.6

SCENE_DIR = r"D:\Stardis-GPU\Stardis-Starter-Pack\cbox"

# 场景引用的所有 STL 文件
STL_FILES = [
    "S_CORNELL_BOX_SHORT.stl",
    "S_CORNELL_BOX_TALL.stl",
    "S_CORNELL_BOX_OUTER_BOX.stl",
    "B_ShortBoxFace.stl",
    "B_TallBoxFace.stl",
    "B_CeilLight.stl",
    "B_LeftWall.stl",
    "B_RightWall.stl",
    "B_Other.stl",
]


def read_binary_stl(path):
    """读取二进制 STL，返回 (header_80bytes, triangles)。
    每个 triangle = (normal_xyz, v1_xyz, v2_xyz, v3_xyz, attr)。"""
    with open(path, "rb") as f:
        header = f.read(80)
        num_triangles = struct.unpack("<I", f.read(4))[0]
        triangles = []
        for _ in range(num_triangles):
            data = struct.unpack("<12fH", f.read(50))
            normal = data[0:3]
            v1 = data[3:6]
            v2 = data[6:9]
            v3 = data[9:12]
            attr = data[12]
            triangles.append((normal, v1, v2, v3, attr))
    return header, triangles


def write_binary_stl(path, header, triangles):
    """写出二进制 STL。"""
    with open(path, "wb") as f:
        f.write(header)
        f.write(struct.pack("<I", len(triangles)))
        for normal, v1, v2, v3, attr in triangles:
            f.write(struct.pack("<12fH", *normal, *v1, *v2, *v3, attr))


def scale_stl(input_path, factor):
    """缩放 STL 文件中的顶点坐标（法线不变）。"""
    header, triangles = read_binary_stl(input_path)
    scaled = []
    for normal, v1, v2, v3, attr in triangles:
        sv1 = tuple(c / factor for c in v1)
        sv2 = tuple(c / factor for c in v2)
        sv3 = tuple(c / factor for c in v3)
        scaled.append((normal, sv1, sv2, sv3, attr))
    return header, scaled


def is_ascii_stl(path):
    """简单检测是否为 ASCII STL。"""
    with open(path, "rb") as f:
        start = f.read(5)
    return start == b"solid"


def read_ascii_stl(path):
    """读取 ASCII STL，返回原始文本行列表。"""
    with open(path, "r") as f:
        return f.readlines()


def scale_ascii_stl(path, factor):
    """缩放 ASCII STL 中的 vertex 行坐标。"""
    lines = read_ascii_stl(path)
    out = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("vertex"):
            parts = stripped.split()
            x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
            indent = line[: len(line) - len(line.lstrip())]
            out.append(f"{indent}vertex {x/factor} {y/factor} {z/factor}\n")
        else:
            out.append(line)
    return out


def main():
    for name in STL_FILES:
        path = os.path.join(SCENE_DIR, name)
        if not os.path.exists(path):
            print(f"[SKIP] {name} — 文件不存在")
            continue

        bak_path = path + ".bak"
        if os.path.exists(bak_path):
            print(f"[SKIP] {name} — 备份文件已存在，可能已缩放过")
            continue

        # 备份
        shutil.copy2(path, bak_path)

        if is_ascii_stl(path):
            scaled_lines = scale_ascii_stl(path, SCALE_FACTOR)
            with open(path, "w") as f:
                f.writelines(scaled_lines)
            print(f"[OK]   {name} (ASCII) — 坐标 ÷ {SCALE_FACTOR}")
        else:
            header, scaled = scale_stl(path, SCALE_FACTOR)
            write_binary_stl(path, header, scaled)
            print(f"[OK]   {name} (Binary) — 坐标 ÷ {SCALE_FACTOR}")

    print("\n完成！原文件已备份为 *.stl.bak")


if __name__ == "__main__":
    main()
