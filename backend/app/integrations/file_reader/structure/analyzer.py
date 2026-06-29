from app.integrations.file_reader.structure.patterns import HeadingMatch, match_numbered_heading
from app.integrations.file_reader.structure.schema import (
    InferredSection,
    ParsedBlock,
    ParsedDocumentV1,
    StructureWarning,
)


class DocumentStructureAnalyzer:
    """基于规则的章节推断器。

    Input:
        已经由具体 reader 读取出的 ``ParsedDocumentV1``，至少包含 ``blocks``。

    Output:
        同一个 ``ParsedDocumentV1``，补充 ``sections`` 和 ``warnings``。

    Processing:
        1. 按 block 顺序扫描文档。
        2. 优先使用中文合同编号规则识别标题。
        3. 在编号不明确时，用保守版式规则识别短标题。
        4. 用 stack 维护当前章节路径，并把普通正文挂到当前路径上的章节。
        5. 对低置信度或无法确认父级的情况写入 warning。

    Scope:
        首期目标是把合同正文挂到尽量稳定的章节下，不追求一次覆盖所有格式。
        LLM 可以消费推断结果，但不参与主链路章节推断。
    """

    analyzer_name = "agenthub-rules-v1"

    def analyze(self, document: ParsedDocumentV1) -> ParsedDocumentV1:
        """基于 blocks 推断 sections，并保留 warnings。

        Args:
            document: 读取层产出的文档结构。调用前 ``document.blocks`` 应已按文档阅读顺序排序。

        Returns:
            原 ``document`` 对象，已设置 ``metadata.structure_analyzer``、
            ``sections`` 和 ``warnings``。

        Processing:
            1. 初始化当前章节路径 stack。
            2. 对每个非空 block 判断是否为标题候选。
            3. 标题候选转为 ``InferredSection`` 并更新 stack。
            4. 普通正文 block 追加到当前 stack 中所有章节的 ``block_ids``。
            5. 如果整个文档没有识别出章节，输出 ``NO_SECTION_DETECTED`` warning。
        """
        sections: list[InferredSection] = []
        warnings = list(document.warnings)
        # stack 保存当前路径上的最近章节，用于把普通段落挂到所有祖先章节。
        stack: dict[int, InferredSection] = {}

        for block in document.blocks:
            text = block.text.strip()
            if not text:
                continue

            candidate = self._detect_heading(block, has_parent=bool(stack))
            if candidate is not None:
                section = self._create_section(candidate, block, sections, stack, warnings)
                sections.append(section)
                stack[section.level] = section
                # 新章节出现后，清理比它更深的旧路径，避免后续段落挂错父级。
                for level in list(stack):
                    if level > section.level:
                        del stack[level]
                self._append_to_ancestors(block.id, section.parent_id, stack)
                continue

            self._append_to_current_sections(block.id, stack)

        document.metadata.structure_analyzer = self.analyzer_name
        document.sections = sections
        document.warnings = warnings
        if not sections and document.blocks:
            document.warnings.append(
                StructureWarning(
                    code="NO_SECTION_DETECTED",
                    message="未识别到明确章节结构，后续只能按自然段落处理。",
                    severity="warning",
                )
            )
        return document

    def _detect_heading(self, block: ParsedBlock, *, has_parent: bool) -> HeadingMatch | None:
        """识别单个 block 是否为标题候选。

        Args:
            block: 当前事实块。
            has_parent: 扫描当前位置是否已经有章节路径。

        Returns:
            命中编号或版式规则时返回 ``HeadingMatch``；否则返回 None。

        Processing:
            1. 先调用 ``match_numbered_heading`` 识别明确编号。
            2. 编号未命中时，再调用 ``_looks_like_style_heading`` 做保守版式判断。
        """
        text = block.text.strip()
        numbered = match_numbered_heading(text, has_parent=has_parent)
        if numbered is not None:
            return numbered

        if self._looks_like_style_heading(block):
            return HeadingMatch(
                level=1,
                numbering=None,
                title=text,
                confidence=0.62,
                code="STYLE_HEADING",
            )
        return None

    @staticmethod
    def _looks_like_style_heading(block: ParsedBlock) -> bool:
        """判断无编号短文本是否像标题。

        Args:
            block: 当前事实块。

        Returns:
            True 表示可以作为无编号标题候选；False 表示按普通正文处理。

        Rules:
            - 空文本、过长文本不是标题。
            - 含常见句末/分隔标点和冒号的文本不是标题。
            - Word Heading 样式和居中文本可作为标题信号。
            - 仅粗体不作为标题信号。

        Reason:
            这里刻意保守，避免把合同当事人、地址、联系方式等元数据误判为章节。
        """
        text = block.text.strip()
        if not text or len(text) > 24:
            return False
        if any(mark in text for mark in "。；，,.;:："):
            return False
        features = block.style_features
        if features.style_name and features.style_name.lower().startswith("heading"):
            return True
        if features.alignment == "center":
            return True
        # 粗体短文本容易把“甲方：”“委托方：”等元数据误判为标题，首版先保守处理。
        return False

    def _create_section(
        self,
        candidate: HeadingMatch,
        block: ParsedBlock,
        sections: list[InferredSection],
        stack: dict[int, InferredSection],
        warnings: list[StructureWarning],
    ) -> InferredSection:
        """把标题候选转换为 section。

        Args:
            candidate: 标题识别结果。
            block: 产生标题候选的原始 block。
            sections: 已创建的章节列表，用于生成递增 ID。
            stack: 当前章节路径。
            warnings: warning 输出列表。

        Returns:
            新建的 ``InferredSection``。

        Processing:
            1. 根据 candidate.level 查找父章节。
            2. 如果子级标题找不到父级，记录 ``LOW_CONFIDENCE_PARENT``。
            3. 如果是纯版式标题，记录 ``POSSIBLE_HEADING_AS_PARAGRAPH``。
            4. 构造 section，但不在这里修改 stack，由调用方统一处理。
        """
        section_id = f"s-{len(sections) + 1:04d}"
        parent = stack.get(candidate.level - 1) if candidate.level > 1 else None
        if candidate.level > 1 and parent is None:
            warnings.append(
                StructureWarning(
                    code="LOW_CONFIDENCE_PARENT",
                    message="识别到子级编号，但未找到稳定父级章节。",
                    block_id=block.id,
                    severity="warning",
                )
            )
        if candidate.code == "STYLE_HEADING":
            warnings.append(
                StructureWarning(
                    code="POSSIBLE_HEADING_AS_PARAGRAPH",
                    message="根据版式推断为标题，建议后续样本复核。",
                    block_id=block.id,
                    severity="info",
                )
            )
        return InferredSection(
            id=section_id,
            title=candidate.title,
            level=candidate.level,
            heading_block_id=block.id,
            parent_id=parent.id if parent else None,
            numbering=candidate.numbering,
            confidence=candidate.confidence,
        )

    @staticmethod
    def _append_to_current_sections(block_id: str, stack: dict[int, InferredSection]) -> None:
        """把普通正文块挂到当前路径上的所有章节。

        Args:
            block_id: 普通正文 block ID。
            stack: 当前章节路径。

        Output:
            原地更新 stack 中各章节的 ``block_ids``。

        Reason:
            同一个正文块同时归属于当前叶子章节和它的父章节，便于后续按任一层级
            生成 LLM 上下文。
        """
        for section in stack.values():
            if block_id not in section.block_ids:
                section.block_ids.append(block_id)

    @staticmethod
    def _append_to_ancestors(
        block_id: str,
        parent_id: str | None,
        stack: dict[int, InferredSection],
    ) -> None:
        """把新子章节标题挂到祖先章节内容范围。

        Args:
            block_id: 新 section 的 heading block ID。
            parent_id: 新 section 的父章节 ID。
            stack: 当前章节路径。

        Output:
            原地更新父章节相关 ``block_ids``。

        Reason:
            子章节标题本身也是父章节的一部分；否则按父章节取上下文时会丢失
            子项标题。
        """
        if parent_id is None:
            return
        for section in stack.values():
            if section.id == parent_id or section.parent_id == parent_id:
                if block_id not in section.block_ids:
                    section.block_ids.append(block_id)
