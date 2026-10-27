"""
工具函数
"""

import yaml


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """
    解析 Markdown frontmatter

    Args:
        content: Markdown 文本

    Returns:
        (frontmatter 字典, body 文本)
    """
    if not content.startswith("---\n"):
        return {}, content

    parts = content.split("---\n", 2)
    if len(parts) < 3:
        return {}, content

    try:
        meta = yaml.safe_load(parts[1])
        return meta or {}, parts[2].strip()
    except yaml.YAMLError:
        return {}, content


def format_frontmatter(meta: dict, body: str) -> str:
    """
    格式化为带 frontmatter 的 Markdown

    Args:
        meta: frontmatter 字典
        body: body 文本

    Returns:
        完整的 Markdown 文本
    """
    if not meta:
        return body

    yaml_str = yaml.dump(meta, allow_unicode=True, sort_keys=False)
    return f"---\n{yaml_str}---\n\n{body}"


def read_jsonl(path: str) -> list[dict]:
    """
    读取 JSONL 文件

    Args:
        path: 文件路径

    Returns:
        记录列表
    """
    import json
    from pathlib import Path

    file_path = Path(path)
    if not file_path.exists():
        return []

    records = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def append_jsonl(path: str, record: dict):
    """
    追加记录到 JSONL 文件

    Args:
        path: 文件路径
        record: 记录字典
    """
    import json
    from pathlib import Path

    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    line = json.dumps(record, ensure_ascii=False)
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
