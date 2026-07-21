from typing import Any


def table_text_and_metadata(table: Any) -> tuple[str, dict[str, Any]]:
    """把 Word 表格转换为去重文本和最小网格 metadata。

    python-docx 会为合并单元格的每个物理网格位置返回同一个底层 ``w:tc``。
    这里按底层元素身份去重，避免横向/纵向合并内容重复进入模型上下文。
    """
    rows: list[list[str]] = []
    semantic_cells: list[dict[str, Any]] = []
    # 必须持有底层元素对象本身；只保存 ``id(cell._tc)`` 会在 wrapper 被回收后
    # 遇到 Python 对象 ID 复用，进而把后续正常单元格误判为合并重复项。
    seen_cells: set[Any] = set()

    for row_index, row in enumerate(table.rows, start=1):
        row_values: list[str] = []
        for cell_index, cell in enumerate(row.cells, start=1):
            cell_key = cell._tc
            if cell_key in seen_cells:
                row_values.append("")
                continue

            seen_cells.add(cell_key)
            text = " ".join(cell.text.split())
            row_values.append(text)
            if text:
                semantic_cells.append(
                    {
                        "row_index": row_index,
                        "cell_index": cell_index,
                        "text": text,
                    }
                )
        rows.append(row_values)

    lines = [" | ".join(value for value in row if value) for row in rows]
    text = "\n".join(line for line in lines if line)
    col_count = max((len(row) for row in rows), default=0)
    return text, {
        "rows": len(rows),
        "cols": col_count,
        "cells": rows,
        "semantic_cells": semantic_cells,
    }
