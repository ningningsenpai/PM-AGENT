"""
result 结构演示示例

基于 ProjectSpecificationService._inventory_item 方法的实现
"""

# result 的最终结构
result = [
    {
        "type": "code",              # 文件类型: "doc" 或 "code"
        "file_id": 123,              # 文件唯一标识ID
        "path": "src/main.py",       # 文件在项目中的相对路径
        "content_hash": "a1b2c3d4",  # 文件内容的哈希值（用于变更检测）
        "detail_ref": "system/file_detail_123.json"  # 文件详情存储引用
    },
    {
        "type": "doc",
        "file_id": 124,
        "path": "docs/design.md",
        "content_hash": "e5f6g7h8",
        "detail_ref": "system/file_detail_124.json"
    },
    {
        "type": "code",
        "file_id": 125,
        "path": "tests/test_main.py",
        "content_hash": "i9j0k1l2",
        "detail_ref": ""             # 可能为空字符串
    },
    {
        "type": "doc",
        "file_id": 126,
        "path": "README.md",
        "content_hash": "m3n4o5p6",
        "detail_ref": "system/file_detail_126.json"
    }
]

# 结构说明
print("result 结构说明:")
print(f"- 类型: {type(result)}")
print(f"- 元素类型: list[dict[str, Any]]")
print(f"- 长度: {len(result)}")
print()

# 展示每个字段含义
print("每个字典的字段含义:")
print("- type: 文件类型，'doc' 表示文档，'code' 表示代码")
print("- file_id: 文件在数据库中的唯一标识")
print("- path: 文件在项目中的相对路径，按此字段排序")
print("- content_hash: 文件内容哈希，用于检测文件是否变更")
print("- detail_ref: 文件详情JSON的存储路径，可能为空字符串")
print()

# 展示第一条记录
print("第一条记录示例:")
import json
print(json.dumps(result[0], indent=2, ensure_ascii=False))