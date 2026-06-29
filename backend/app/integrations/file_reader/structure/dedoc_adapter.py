from app.integrations.file_reader.errors import FileReaderDependencyError


class DedocStructureAnalyzer:
    """Dedoc PoC 占位适配器。

    Input:
        未来会接收 ``ParsedDocumentV1`` 或文件路径，并调用 Dedoc 尝试结构识别。

    Output:
        未来必须输出 AgentHub 自有的 ``ParsedDocumentV1`` / ``InferredSection``，
        不允许把 Dedoc 原生类型返回给业务层。

    Current Behavior:
        当前只检查 Dedoc 是否安装；未安装时抛出明确依赖错误。

    Boundary:
        业务层不得依赖 Dedoc 类型；后续评估通过后再在这里完成类型转换。
        现在只负责明确提示依赖缺失，避免调用方误以为 Dedoc 已接入主链路。
    """

    def __init__(self) -> None:
        """初始化 Dedoc 适配器。

        Raises:
            FileReaderDependencyError: 未安装 dedoc。当前主链路应继续使用
            ``DocumentStructureAnalyzer``。
        """
        try:
            import dedoc  # noqa: F401
        except ImportError as exc:
            raise FileReaderDependencyError(
                "dedoc is not installed; use DocumentStructureAnalyzer for now"
            ) from exc
