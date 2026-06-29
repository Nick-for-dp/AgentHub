from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SourceLocation:
    """文本块在源文件中的位置。

    Attributes:
        paragraph_index: 段落序号，从 1 开始；表格 block 可为空。
        table_index: 表格序号，从 1 开始；普通段落可为空。
        row_index: 表格行序号，预留给未来 cell 级 block。
        cell_index: 表格单元格序号，预留给未来 cell 级 block。
        page_number: PDF 页码或未来 DOCX 渲染页码，从 1 开始。

    Usage:
        用于审计追溯、前端定位、人工复核和 LLM 输出证据回链。
    """

    paragraph_index: int | None = None
    table_index: int | None = None
    row_index: int | None = None
    cell_index: int | None = None
    page_number: int | None = None


@dataclass
class StyleFeatures:
    """章节推断使用的版式特征。

    Attributes:
        style_name: 源文档样式名，例如 ``Normal``、``Heading 1``。
        alignment: 归一化对齐方式：``left``、``center``、``right``、``justify``、``unknown``。
        first_line_indent: 首行缩进，单位沿用 python-docx / EMU 整数值。
        left_indent: 左缩进，单位沿用 python-docx / EMU 整数值。
        bold_ratio: 段落中显式加粗字符占比，范围 0 到 1。
        font_size_pt: 段落中最常见显式字号，单位 pt。

    Note:
        这些字段不是最终业务事实，只是帮助判断某段是否可能是标题。
    """

    style_name: str | None = None
    alignment: str = "unknown"
    first_line_indent: int | None = None
    left_indent: int | None = None
    bold_ratio: float = 0.0
    font_size_pt: float | None = None


@dataclass
class NumberingInfo:
    """标准化后的编号信息。

    Attributes:
        raw: 原文编号，例如 ``第一条``、``1.``、``附件二``。
        normalized: 归一化编号字符串，例如 ``1``、``2``。
        scheme: 编号模式，例如 ``chinese_article``、``arabic_dot``。
        ordinal: 可计算时的整数序号；无法稳定计算时为空。
    """

    raw: str
    normalized: str
    scheme: str
    ordinal: int | None = None


@dataclass
class ParsedBlock:
    """读取层产出的事实块。

    Attributes:
        id: 稳定块 ID，当前格式为 ``b-000001``。
        kind: 物理块类型，例如 ``paragraph``、``table``。
        text: 归一化文本；会压缩多余空白，但不做业务改写。
        order: 在文档流中的顺序号，从 1 开始。
        source_location: 源文件位置。
        style_features: 版式特征。
        metadata: 格式相关附加信息，例如表格 cell 网格或 PDF bbox。

    Rule:
        block 是 ParsedDocument 的事实源；sections 只引用 block，不重复保存正文。
    """

    id: str
    kind: str
    text: str
    order: int
    source_location: SourceLocation = field(default_factory=SourceLocation)
    style_features: StyleFeatures = field(default_factory=StyleFeatures)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class InferredSection:
    """章节推断层产出的结构节点。

    Attributes:
        id: 稳定章节 ID，当前格式为 ``s-0001``。
        title: 章节标题文本，来自 ``heading_block_id`` 指向的 block。
        level: 推断层级。合同标题/一级章节通常为 1，条款子项通常为 2。
        heading_block_id: 产生该 section 的标题 block ID。
        parent_id: 父 section ID；一级章节为空。
        block_ids: 归属于该章节的正文 block ID。父章节会包含子章节标题和内容。
        numbering: 标准化编号信息；纯版式标题可为空。
        confidence: 结构推断置信度，范围 0 到 1。
    """

    id: str
    title: str
    level: int
    heading_block_id: str
    parent_id: str | None = None
    block_ids: list[str] = field(default_factory=list)
    numbering: NumberingInfo | None = None
    confidence: float = 0.0


@dataclass
class StructureWarning:
    """章节推断中的不确定性或质量问题。

    Attributes:
        code: 稳定机器码，例如 ``LOW_CONFIDENCE_PARENT``。
        message: 面向开发/运营人员的中文说明。
        severity: ``info``、``warning`` 或未来扩展的严重级别。
        block_id: 相关 block ID；文档级 warning 可为空。
    """

    code: str
    message: str
    severity: str = "warning"
    block_id: str | None = None


@dataclass
class ParsedMetadata:
    """解析结果的文档级元数据。

    Attributes:
        filename: 源文件名。
        file_type: 源文件扩展名，例如 ``docx``、``pdf``。
        reader_type: 使用的读取器，例如 ``python-docx``、``pymupdf``。
        structure_analyzer: 使用的章节推断器版本。
        paragraph_count: 读取到的非空段落数量。
        table_count: 读取到的表格数量。
        page_count: PDF 页数或未来渲染页数。
        extra: 其他格式相关元数据。
    """

    filename: str
    file_type: str
    reader_type: str
    structure_analyzer: str = "agenthub-rules-v1"
    paragraph_count: int = 0
    table_count: int = 0
    page_count: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocumentV1:
    """文件读取与章节推断的 v1 输出结构。

    Attributes:
        metadata: 文档级元数据。
        blocks: 事实块列表，是后续所有结构和业务抽取的事实源。
        sections: 基于 blocks 推断出的章节/段落结构。
        warnings: 解析和推断过程中的不确定性。

    Output Contract:
        v1 保持简单：metadata / blocks / sections / warnings。
        后续 LLM 输入片段可由 sections + blocks 派生。
    """

    metadata: ParsedMetadata
    blocks: list[ParsedBlock] = field(default_factory=list)
    sections: list[InferredSection] = field(default_factory=list)
    warnings: list[StructureWarning] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化字典。

        Returns:
            递归展开 dataclass 后的普通字典，可直接写入 JSON snapshot 或 API 响应。
        """
        return asdict(self)
