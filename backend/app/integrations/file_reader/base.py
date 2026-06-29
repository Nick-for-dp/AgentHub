from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.integrations.file_reader.structure.schema import ParsedDocumentV1


@dataclass(frozen=True)
class FileSource:
    """文件来源。

    Attributes:
        path: 本地文件绝对路径。首期 PoC 只支持本地路径；后续接入 MinIO 时，
            应在 FileSource 层扩展对象存储 URI 或临时下载路径，不让业务层关心来源。
        filename: 原始文件名，用于 metadata、日志和前端展示。
        file_type: 不带点的扩展名，例如 ``docx``、``pdf``。
    """

    path: Path
    filename: str
    file_type: str

    @classmethod
    def from_path(cls, path: str | Path) -> "FileSource":
        """从本地路径构造文件来源。

        Args:
            path: 本地文件路径。可以是字符串或 ``Path``，允许相对路径和 ``~``。

        Returns:
            标准化后的 ``FileSource``，其中 ``path`` 已解析为绝对路径，
            ``file_type`` 已从扩展名归一化为小写。

        Processing:
            1. 展开用户目录和相对路径。
            2. 从文件名后缀提取扩展名。
            3. 返回供 reader/factory 使用的统一来源对象。
        """
        resolved = Path(path).expanduser().resolve()
        suffix = resolved.suffix.lower().lstrip(".")
        return cls(path=resolved, filename=resolved.name, file_type=suffix)


class FileReader(Protocol):
    """具体 reader 的统一协议。

    Implementations:
        ``DocxReader``、``PdfReader`` 等格式读取器必须实现该协议。
        每个实现负责把一种文件格式转成 ``ParsedDocumentV1``。

    Boundary:
        业务模块只能依赖本协议和 ``ParsedDocumentV1``，不能直接依赖
        python-docx、pymupdf、Dedoc 等第三方库类型。
    """

    async def parse(self, source: FileSource) -> ParsedDocumentV1:
        """解析文件。

        Args:
            source: 文件来源，当前主要是本地路径。

        Returns:
            ``ParsedDocumentV1``，包含 ``metadata``、``blocks``、``sections`` 和
            ``warnings``。

        Raises:
            FileReaderError: 文件类型或内容不符合当前 reader 能力。
            FileReaderDependencyError: 当前格式需要的可选依赖未安装。
        """
