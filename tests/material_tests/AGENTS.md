# Material Database Tests

## 测试覆盖

| 测试文件 | 覆盖内容 |
|----------|----------|
| `test_material_database.py` | Material 数据类、MaterialDatabase CRUD、内置材质、JSON 持久化、导入导出 |
| `test_material_roundtrip.py` | MaterialRef.source_material 序列化往返、project JSON body_materials 字段 |

## Fixtures

- `db` — 包含全部内置材质的 MaterialDatabase 实例
- `tmp_path` — pytest 内置临时目录
