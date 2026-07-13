import type {
  ContractClauseReviewResult,
  ContractClauseSourceSpan,
  ParsedDocumentBlock,
} from '../api/internalContractReview'

export interface HighlightWarning {
  code: string
  message: string
  clauseIndex: number
  blockId?: string
}

export interface HighlightMark {
  key: string
  clauseIndex: number
  spanIndex: number
  blockId: string
  startOffset: number
  endOffset: number
  matchedText: string
  isSensitive: boolean
  riskLevel: string
}

export interface HighlightSegment {
  kind: 'text' | 'highlight'
  text: string
  mark?: HighlightMark
}

export interface ClauseTarget {
  clauseIndex: number
  blockId?: string
  markKey?: string
  precise: boolean
  disabled: boolean
}

export interface HighlightIndex {
  marksByBlock: Record<string, HighlightMark[]>
  warningsByClause: Record<number, HighlightWarning[]>
  targetsByClause: Record<number, ClauseTarget>
}

export function buildHighlightIndex(
  blocks: ParsedDocumentBlock[],
  clauses: ContractClauseReviewResult[],
): HighlightIndex {
  const blockTextById = new Map(blocks.map((block) => [block.id, block.text]))
  const warningsByClause: Record<number, HighlightWarning[]> = {}
  const marksByBlock: Record<string, HighlightMark[]> = {}
  const targetsByClause: Record<number, ClauseTarget> = {}

  clauses.forEach((clause, clauseIndex) => {
    const validMarks: HighlightMark[] = []
    for (const [spanIndex, span] of clause.source_spans.entries()) {
      const mark = validateSpan({
        span,
        spanIndex,
        clauseIndex,
        clause,
        blockTextById,
        addWarning: (warning) => addWarning(warningsByClause, warning),
      })
      if (!mark) continue
      validMarks.push(mark)
      ;(marksByBlock[mark.blockId] ??= []).push(mark)
    }

    const firstValidMark = validMarks[0]
    if (firstValidMark) {
      targetsByClause[clauseIndex] = {
        clauseIndex,
        blockId: firstValidMark.blockId,
        markKey: firstValidMark.key,
        precise: true,
        disabled: false,
      }
      return
    }

    const fallbackBlockId = clause.source_block_ids.find((blockId) => blockTextById.has(blockId))
    if (fallbackBlockId) {
      addWarning(warningsByClause, {
        code: 'PRECISE_HIGHLIGHT_UNAVAILABLE',
        message: '该条款缺少可用的字符级来源位置，已提供原文块定位。',
        clauseIndex,
        blockId: fallbackBlockId,
      })
      targetsByClause[clauseIndex] = {
        clauseIndex,
        blockId: fallbackBlockId,
        precise: false,
        disabled: false,
      }
      return
    }

    addWarning(warningsByClause, {
      code: 'SOURCE_LOCATION_UNAVAILABLE',
      message: '该条款没有可用的原文来源位置，无法在解析文本中定位。',
      clauseIndex,
    })
    targetsByClause[clauseIndex] = { clauseIndex, precise: false, disabled: true }
  })

  for (const [blockId, marks] of Object.entries(marksByBlock)) {
    const acceptedMarks = resolveOverlaps(blockId, marks, warningsByClause)
    marksByBlock[blockId] = acceptedMarks
  }

  reconcileTargetsAfterOverlap(targetsByClause, marksByBlock, warningsByClause)
  return { marksByBlock, warningsByClause, targetsByClause }
}

export function renderHighlightSegments(text: string, marks: HighlightMark[]): HighlightSegment[] {
  if (marks.length === 0) return [{ kind: 'text', text }]
  const characters = Array.from(text)
  const segments: HighlightSegment[] = []
  let cursor = 0

  for (const mark of marks) {
    if (mark.startOffset > cursor) {
      segments.push({ kind: 'text', text: characters.slice(cursor, mark.startOffset).join('') })
    }
    segments.push({
      kind: 'highlight',
      text: characters.slice(mark.startOffset, mark.endOffset).join(''),
      mark,
    })
    cursor = mark.endOffset
  }
  if (cursor < characters.length) {
    segments.push({ kind: 'text', text: characters.slice(cursor).join('') })
  }
  return segments.length > 0 ? segments : [{ kind: 'text', text }]
}

interface ValidateSpanOptions {
  span: ContractClauseSourceSpan
  spanIndex: number
  clauseIndex: number
  clause: ContractClauseReviewResult
  blockTextById: Map<string, string>
  addWarning: (warning: HighlightWarning) => void
}

function validateSpan(options: ValidateSpanOptions): HighlightMark | null {
  const { span, spanIndex, clauseIndex, clause, blockTextById, addWarning } = options
  const blockText = blockTextById.get(span.block_id)
  if (blockText === undefined) {
    addWarning({
      code: 'SOURCE_BLOCK_NOT_FOUND',
      message: `未找到来源文本块 ${span.block_id}，无法精确高亮。`,
      clauseIndex,
      blockId: span.block_id,
    })
    return null
  }
  if (!Number.isInteger(span.start_offset) || !Number.isInteger(span.end_offset)) {
    addWarning({
      code: 'SOURCE_OFFSET_INVALID',
      message: '来源位置不是有效的整数 offset，无法精确高亮。',
      clauseIndex,
      blockId: span.block_id,
    })
    return null
  }

  const characters = Array.from(blockText)
  if (span.start_offset < 0 || span.end_offset <= span.start_offset || span.end_offset > characters.length) {
    addWarning({
      code: 'SOURCE_OFFSET_OUT_OF_RANGE',
      message: '来源位置超出解析文本范围，无法精确高亮。',
      clauseIndex,
      blockId: span.block_id,
    })
    return null
  }

  const actualText = characters.slice(span.start_offset, span.end_offset).join('')
  if (actualText !== span.matched_text) {
    addWarning({
      code: 'SOURCE_TEXT_MISMATCH',
      message: '来源位置与匹配文本不一致，已停止精确高亮以避免错误标记。',
      clauseIndex,
      blockId: span.block_id,
    })
    return null
  }

  return {
    key: `${clauseIndex}:${spanIndex}:${span.block_id}:${span.start_offset}:${span.end_offset}`,
    clauseIndex,
    spanIndex,
    blockId: span.block_id,
    startOffset: span.start_offset,
    endOffset: span.end_offset,
    matchedText: span.matched_text,
    isSensitive: clause.is_sensitive,
    riskLevel: clause.risk_level,
  }
}

function resolveOverlaps(
  blockId: string,
  marks: HighlightMark[],
  warningsByClause: Record<number, HighlightWarning[]>,
): HighlightMark[] {
  const sorted = [...marks].sort((left, right) => (
    left.startOffset - right.startOffset
    || left.endOffset - right.endOffset
    || left.clauseIndex - right.clauseIndex
    || left.spanIndex - right.spanIndex
  ))
  const accepted: HighlightMark[] = []
  let cursor = 0
  for (const mark of sorted) {
    if (mark.startOffset < cursor) {
      addWarning(warningsByClause, {
        code: 'SOURCE_SPAN_OVERLAP',
        message: '该条款来源位置与另一条高亮重叠，未生成可能误导的嵌套高亮。',
        clauseIndex: mark.clauseIndex,
        blockId,
      })
      continue
    }
    accepted.push(mark)
    cursor = mark.endOffset
  }
  return accepted
}

function reconcileTargetsAfterOverlap(
  targetsByClause: Record<number, ClauseTarget>,
  marksByBlock: Record<string, HighlightMark[]>,
  warningsByClause: Record<number, HighlightWarning[]>,
): void {
  const acceptedMarkKeys = new Set(
    Object.values(marksByBlock).flatMap((marks) => marks.map((mark) => mark.key)),
  )
  const fallbackByClause = new Map<number, HighlightMark>()
  for (const marks of Object.values(marksByBlock)) {
    for (const mark of marks) {
      if (!fallbackByClause.has(mark.clauseIndex)) fallbackByClause.set(mark.clauseIndex, mark)
    }
  }

  for (const target of Object.values(targetsByClause)) {
    if (!target.markKey || acceptedMarkKeys.has(target.markKey)) continue
    const fallback = fallbackByClause.get(target.clauseIndex)
    if (fallback) {
      target.blockId = fallback.blockId
      target.markKey = fallback.key
      target.precise = true
      continue
    }
    addWarning(warningsByClause, {
      code: 'PRECISE_HIGHLIGHT_OVERLAPPED',
      message: '条款来源位置与其他高亮重叠，已降级为原文块定位。',
      clauseIndex: target.clauseIndex,
      blockId: target.blockId,
    })
    target.markKey = undefined
    target.precise = false
  }
}

function addWarning(
  warningsByClause: Record<number, HighlightWarning[]>,
  warning: HighlightWarning,
): void {
  ;(warningsByClause[warning.clauseIndex] ??= []).push(warning)
}
