from app.integrations.file_reader.base import FileSource
from app.integrations.file_reader.errors import FileReaderError
from app.integrations.file_reader.structure.schema import (
    ParsedDocumentV1,
    ParsedMetadata,
    StructureWarning,
)


SUPPORTED_IMAGE_TYPES = frozenset({"png", "jpg", "jpeg"})


class ImageReader:
    """图片文件的最小读取器。

    一期不在 FileReader 内调用 OCR/VLM。该 reader 只确认原图可读并输出稳定的
    ParsedDocumentV1；后续 DocumentExtractor 通过 file_parse_task.source_uri 读取原图。
    """

    reader_type = "image-metadata"

    async def parse(self, source: FileSource) -> ParsedDocumentV1:
        if not source.path.exists():
            raise FileReaderError(f"file not found: {source.path}")
        if source.file_type not in SUPPORTED_IMAGE_TYPES:
            raise FileReaderError("ImageReader only supports PNG/JPG images")

        size_bytes = source.path.stat().st_size
        if size_bytes <= 0:
            raise FileReaderError("image file is empty")

        return ParsedDocumentV1(
            metadata=ParsedMetadata(
                filename=source.filename,
                file_type=source.file_type,
                reader_type=self.reader_type,
                page_count=1,
                extra={
                    "size_bytes": size_bytes,
                    "requires_extraction": True,
                },
            ),
            warnings=[
                StructureWarning(
                    code="IMAGE_REQUIRES_EXTRACTION",
                    message="图片没有原生文本层，后续字段抽取需要读取原图。",
                    severity="warning",
                )
            ],
        )
