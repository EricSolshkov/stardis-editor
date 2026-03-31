# normal_orientation_tests/AGENTS.md

## 测试覆盖

| 测试文件 | 覆盖范围 |
|----------|----------|
| `test_detect_orientation.py` | `detect_normal_orientation()` 和 `detect_normal_orientation_from_polydata()` 函数 |
| `test_semantic_mapping.py` | BodyEditor 的 `_semantic_to_side()` 和 `_side_to_semantic()` 静态方法 |
| `test_roundtrip.py` | `NormalOrientation` 在 `.stardis_project.json` 的序列化/反序列化往返 |

## Fixtures

- `conftest.py` 提供封闭/开放 VTK PolyData 和临时场景目录。
- 封闭网格：三角化立方体（法线指向外侧）
- 开放网格：从立方体中删除部分三角面
