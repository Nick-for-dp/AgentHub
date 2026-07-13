import { describe, expect, it } from 'vitest'

import type { ContractClauseReviewResult, ParsedDocumentBlock } from '../api/internalContractReview'
import { buildHighlightIndex, renderHighlightSegments } from './contractHighlight'

function block(id: string, text: string): ParsedDocumentBlock {
  return { id, kind: 'paragraph', text, order: 1 }
}

function clause(overrides: Partial<ContractClauseReviewResult> = {}): ContractClauseReviewResult {
  return {
    text: '乙方应承担责任',
    category: 'liability',
    source: {},
    source_block_ids: ['b-1'],
    source_spans: [],
    is_sensitive: true,
    risk_level: 'HIGH',
    matched_rules: ['liability_01'],
    reason: '测试规则',
    confidence: 0.9,
    warnings: [],
    ...overrides,
  }
}

describe('contract highlight', () => {
  it('uses Unicode code point offsets for Chinese and non-BMP characters', () => {
    const source = block('b-1', '甲方😀乙方承担责任')
    const clauses = [clause({
      source_spans: [{
        block_id: 'b-1',
        start_offset: 4,
        end_offset: 6,
        matched_text: '方承',
      }],
    })]

    const index = buildHighlightIndex([source], clauses)
    const segments = renderHighlightSegments(source.text, index.marksByBlock['b-1'])

    expect(segments.map((segment) => segment.text)).toEqual(['甲方😀乙', '方承', '担责任'])
    expect(index.targetsByClause[0]).toMatchObject({ precise: true, blockId: 'b-1' })
  })

  it('rejects out-of-range, reversed, and mismatched spans without guessing', () => {
    const source = block('b-1', '甲方应当付款')
    const clauses = [
      clause({ source_spans: [{ block_id: 'b-1', start_offset: -1, end_offset: 2, matched_text: '甲方' }] }),
      clause({ source_spans: [{ block_id: 'b-1', start_offset: 4, end_offset: 2, matched_text: '当付' }] }),
      clause({ source_spans: [{ block_id: 'b-1', start_offset: 0, end_offset: 2, matched_text: '乙方' }] }),
    ]

    const index = buildHighlightIndex([source], clauses)

    expect(index.marksByBlock['b-1']).toBeUndefined()
    expect(index.warningsByClause[0][0].code).toBe('SOURCE_OFFSET_OUT_OF_RANGE')
    expect(index.warningsByClause[1][0].code).toBe('SOURCE_OFFSET_OUT_OF_RANGE')
    expect(index.warningsByClause[2][0].code).toBe('SOURCE_TEXT_MISMATCH')
    expect(index.targetsByClause[0]).toMatchObject({ precise: false, blockId: 'b-1' })
  })

  it('keeps the first non-overlapping mark and records the skipped overlap', () => {
    const source = block('b-1', '甲方应在十日内付款')
    const clauses = [
      clause({ source_spans: [{ block_id: 'b-1', start_offset: 0, end_offset: 4, matched_text: '甲方应在' }] }),
      clause({ source_spans: [{ block_id: 'b-1', start_offset: 2, end_offset: 6, matched_text: '应在十日' }] }),
    ]

    const index = buildHighlightIndex([source], clauses)

    expect(index.marksByBlock['b-1']).toHaveLength(1)
    expect(index.marksByBlock['b-1'][0].clauseIndex).toBe(0)
    expect(index.warningsByClause[1].some((warning) => warning.code === 'SOURCE_SPAN_OVERLAP')).toBe(true)
    expect(index.targetsByClause[1]).toMatchObject({ precise: false, blockId: 'b-1' })
  })

  it('falls back to block location when clauses have no source span', () => {
    const index = buildHighlightIndex([block('b-1', '条款正文')], [clause()])

    expect(index.targetsByClause[0]).toEqual({
      clauseIndex: 0,
      blockId: 'b-1',
      precise: false,
      disabled: false,
    })
    expect(index.warningsByClause[0][0].code).toBe('PRECISE_HIGHLIGHT_UNAVAILABLE')
  })
})
