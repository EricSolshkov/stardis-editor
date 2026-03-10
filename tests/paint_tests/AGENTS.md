# paint_tests — 画笔系统 & 场景序列化测试

## 测试文件

| 文件 | 功能 |
|------|------|
| `conftest.py` | 共享 fixtures（VTK PolyData 构建、临时场景目录） |
| `test_roundtrip.py` | 保存/加载往返测试（有/无 JSON、cell_ids 恢复） |
| `test_save_project.py` | save_project / zone_parent_map 序列化验证 |
| `test_scene_writer.py` | SceneWriter 统一 B_*.stl 导出测试 |
| `test_triangle_hash_matcher.py` | 三角形哈希匹配器单元测试 |

## 测试覆盖

| 测试模块 | 测试类 | 用例数 | 覆盖范围 |
|----------|--------|--------|---------|
| `test_triangle_hash_matcher.py` | `TestTriangleHash` | 3 | 哈希确定性、不同 cell 不同哈希、SHA-256 格式 |
| | `TestBuildParentHashMap` | 2 | map 大小 = cell 数量、所有 cell_id 存在 |
| | `TestMatchChildToParent` | 6 | 完全匹配 / 单 cell / 全 cell / 空子网格 / 复用 hash_map / 外来网格零匹配 |
| | `TestLoadStlPolydata` | 1 | STL 文件读写往返 |
| `test_save_project.py` | `TestSaveProject` | 5 | zone_parent_map 存在 / cell_ids 不在 JSON / body_zone_ids 结构 / ImportedSTL zone 也在 map / 多 Body |
| `test_scene_writer.py` | `TestWriterPaintedRegion` | 3 | B_*.stl 创建 / 三角形数量正确 / zone_parent_map 写入 JSON |
| | `TestWriterImportedSTL` | 2 | B_*.stl 拷贝 / zone_parent_map 包含导入 zone |
| `test_roundtrip.py` | `TestRoundtripWithJson` | 4 | cell_ids 恢复 / zone_id 恢复 / next_zone_id 恢复 / 无 warnings |
| | `TestRoundtripWithoutJson` | 2 | 单 Body 无 JSON 自动归入 + 恢复 / 无 unresolved |
| | `TestRoundtripSaveAndReload` | 1 | 完整保存→重新加载→涂选数据一致 |

**总计：29 用例**

## 共享 Fixtures（conftest.py）

- `parent_poly` — 三角化单位立方体（12 三角面），用作 VTK 测试基础网格
- `scene_dir` — 临时目录，包含 `S_FOAM.stl`、`B_LAT.stl`、`B_TOP.stl`、`scene.txt`，测试后自动清理
- `scene_dir_with_json` — 在 `scene_dir` 基础上添加 `.stardis_project.json`
- 辅助函数：`_make_triangulated_cube()`、`_extract_cells()`、`_write_stl()`
