from fastapi import status

from app.core.exceptions import AgentHubError


class FileReaderError(AgentHubError):
    """文件内容、路径或格式不符合当前 reader 能力。

    Args:
        message: 面向调用方的稳定错误说明。

    Output:
        HTTP 422 / ``FILE_READER_ERROR``，表示请求文件无法被当前解析器处理。
    """

    def __init__(self, message: str = "file reader error"):
        super().__init__("FILE_READER_ERROR", message, status.HTTP_422_UNPROCESSABLE_ENTITY)


class FileReaderDependencyError(AgentHubError):
    """解析所需的可选依赖未安装。

    Args:
        message: 缺失依赖的说明，通常包含需要安装的包名。

    Output:
        HTTP 503 / ``FILE_READER_DEPENDENCY_MISSING``。

    Reason:
        file_reader 面向 internal profile 扩展，部分依赖不能强加给 external profile；
        因此这里用明确错误提示部署方安装对应内部依赖组。
    """

    def __init__(self, message: str = "file reader dependency is not installed"):
        super().__init__(
            "FILE_READER_DEPENDENCY_MISSING",
            message,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
