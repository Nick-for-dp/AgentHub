from pathlib import Path

from app.integrations.file_reader.base import FileReader, FileSource
from app.integrations.file_reader.errors import FileReaderError
from app.integrations.file_reader.structure.schema import ParsedDocumentV1


def get_file_reader(file_type: str) -> FileReader:
    """按文件扩展名选择 reader。

    Args:
        file_type: 文件扩展名，可带点或不带点，例如 ``.docx``、``docx``。

    Returns:
        匹配该文件类型的 ``FileReader`` 实例。

    Raises:
        FileReaderError: 文件类型暂不支持；`.doc` 需要先经 LibreOffice 转换。

    Processing:
        1. 归一化扩展名。
        2. 延迟导入具体 reader，避免 external profile 启动时加载内部可选依赖。
        3. 返回具体 reader 实例。
    """
    normalized = file_type.lower().lstrip(".")
    if normalized == "docx":
        from app.integrations.file_reader.docx_reader import DocxReader

        return DocxReader()
    if normalized == "pdf":
        from app.integrations.file_reader.pdf_reader import PdfReader

        return PdfReader()
    if normalized == "doc":
        raise FileReaderError("legacy .doc requires LibreOffice conversion before parsing")
    raise FileReaderError(f"unsupported file type: {file_type}")


async def parse_local_file(path: str | Path) -> ParsedDocumentV1:
    """直接解析本地文件路径。

    Args:
        path: 本地文件路径。

    Returns:
        ``ParsedDocumentV1``，包含读取事实块和章节推断结果。

    Raises:
        FileReaderError: 文件不存在、类型不支持或内容无法解析。
        FileReaderDependencyError: 当前 reader 所需依赖未安装。

    Processing:
        1. 将本地路径转换为 ``FileSource``。
        2. 按扩展名选择 reader。
        3. 调用 reader 产出统一解析结构。

    Note:
        这是章节推断 PoC 的入口；正式接入 MinIO 后，业务服务应先把对象存储 URI
        转成 FileSource，再调用具体 reader。
    """
    source = FileSource.from_path(path)
    reader = get_file_reader(source.file_type)
    return await reader.parse(source)
