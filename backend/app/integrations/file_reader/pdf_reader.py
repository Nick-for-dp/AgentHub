from app.integrations.file_reader.base import FileSource
from app.integrations.file_reader.errors import FileReaderDependencyError, FileReaderError
from app.integrations.file_reader.structure import DocumentStructureAnalyzer
from app.integrations.file_reader.structure.schema import (
    ParsedBlock,
    ParsedDocumentV1,
    ParsedMetadata,
    SourceLocation,
    StyleFeatures,
)


class PdfReader:
    """PDF 读取器。

    Input:
        ``FileSource``，其 ``path`` 指向本地 ``.pdf`` 文件。

    Output:
        ``ParsedDocumentV1``。每个 PyMuPDF 文本块会被转换为一个
        ``kind="paragraph"`` 的 ``ParsedBlock``，并保留页码和 bbox。

    Processing:
        1. 校验路径和扩展名。
        2. 延迟导入 PyMuPDF，避免 external profile 启动时加载 AGPL 依赖。
        3. 按页读取 ``page.get_text("blocks")``。
        4. 按 y/x 坐标粗排文本块，生成统一 blocks。
        5. 调用章节推断器补充 ``sections`` 和 ``warnings``。

    Boundary:
        首版只读取文本块和位置框，先满足章节推断 PoC。表格识别、页眉页脚剔除
        和多栏版面重排后续再独立增强。
    """

    reader_type = "pymupdf"

    async def parse(self, source: FileSource) -> ParsedDocumentV1:
        """读取 .pdf 文件并返回 ParsedDocument v1。

        Args:
            source: 文件来源，``source.file_type`` 必须为 ``pdf``。

        Returns:
            统一解析结果。``metadata.page_count`` 来自 PyMuPDF，
            ``blocks[].metadata.bbox`` 保存页面坐标。

        Raises:
            FileReaderError: 文件不存在或扩展名不是 pdf。
            FileReaderDependencyError: 未安装 pymupdf。
        """
        if not source.path.exists():
            raise FileReaderError(f"file not found: {source.path}")
        if source.file_type != "pdf":
            raise FileReaderError("PdfReader only supports .pdf files")

        try:
            import fitz
        except ImportError as exc:
            raise FileReaderDependencyError("pymupdf is required for .pdf parsing") from exc

        blocks: list[ParsedBlock] = []
        paragraph_count = 0
        with fitz.open(str(source.path)) as document:
            page_count = document.page_count
            for page_index, page in enumerate(document, start=1):
                page_blocks = page.get_text("blocks")
                # PyMuPDF 块的默认顺序不总是阅读顺序，先按页面坐标粗排一遍。
                page_blocks.sort(key=lambda item: (item[1], item[0]))
                for raw_block in page_blocks:
                    text = " ".join((raw_block[4] or "").split())
                    if not text:
                        continue
                    paragraph_count += 1
                    x0, y0, x1, y1 = raw_block[:4]
                    blocks.append(
                        ParsedBlock(
                            id=f"b-{len(blocks) + 1:06d}",
                            kind="paragraph",
                            text=text,
                            order=len(blocks) + 1,
                            source_location=SourceLocation(
                                paragraph_index=paragraph_count,
                                page_number=page_index,
                            ),
                            style_features=StyleFeatures(style_name="pdf_text_block"),
                            metadata={
                                "bbox": [float(x0), float(y0), float(x1), float(y1)],
                            },
                        )
                    )

        parsed = ParsedDocumentV1(
            metadata=ParsedMetadata(
                filename=source.filename,
                file_type=source.file_type,
                reader_type=self.reader_type,
                paragraph_count=paragraph_count,
                table_count=0,
                page_count=page_count,
            ),
            blocks=blocks,
        )
        return DocumentStructureAnalyzer().analyze(parsed)
