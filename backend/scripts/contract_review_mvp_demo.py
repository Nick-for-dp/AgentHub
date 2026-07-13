"""合同审查 MVP 本地验收报告脚本。

本脚本只服务本地验收，不进入正式合同审查主链路。它复用现有后端 service
完成 MinIO 上传、文件解析、合同审查执行，并生成一个可离线打开的 HTML 报告，
用于人工复核敏感条款与解析文本高亮是否可信。

用法示例：

    cd backend
    python -m scripts.contract_review_mvp_demo ^
      --contract-file "D:\\path\\contract.docx" ^
      --counterparty-level A1
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import app.db.models  # noqa: E402,F401  # 导入全部模型，保证 SQLAlchemy 外键元数据完整。
from app.core.config import get_settings  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.integrations.object_storage import create_file_storage  # noqa: E402
from app.modules.auth.schemas import AuthenticatedSubject  # noqa: E402
from app.modules.contract_review.executor import ContractReviewExecutionService  # noqa: E402
from app.modules.contract_review.service import ContractReviewService  # noqa: E402
from app.modules.contract_review.schemas import ContractReviewTaskCreate  # noqa: E402
from app.modules.file_parse.schemas import FileParseTaskCreate  # noqa: E402
from app.modules.file_parse.service import FileParseService  # noqa: E402
from app.modules.invocation.models import AgentInvocationRecord  # noqa: E402
from app.modules.org.models import OrgUnit, UserAccount  # noqa: E402

DEFAULT_OUTPUT_ROOT = BACKEND_ROOT / "tmp" / "contract_review_mvp_reports"
DEFAULT_USER_EMAIL = "admin@agenthub.local"
DEFAULT_CONTRACT_TYPE = "warehouse"
DEFAULT_COUNTERPARTY_LEVEL = "A1"
COUNTERPARTY_LEVELS = ("A1", "A2", "A3", "A4", "A5", "A6", "A7")


@dataclass(frozen=True)
class HighlightMark:
    """单个可渲染的高亮标记。"""

    block_id: str
    start_offset: int
    end_offset: int
    clause_index: int
    is_sensitive: bool
    risk_level: str | None
    category: str | None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="Generate contract review MVP HTML report.")
    parser.add_argument(
        "--contract-file",
        action="append",
        required=True,
        help="待验收合同 DOCX/PDF 路径；可重复传入多份文件。",
    )
    parser.add_argument(
        "--contract-type",
        default=DEFAULT_CONTRACT_TYPE,
        help=f"合同类型，默认 {DEFAULT_CONTRACT_TYPE}。",
    )
    parser.add_argument(
        "--counterparty-level",
        default=DEFAULT_COUNTERPARTY_LEVEL,
        choices=COUNTERPARTY_LEVELS,
        help=f"合同对手方资信等级，默认 {DEFAULT_COUNTERPARTY_LEVEL}。",
    )
    parser.add_argument(
        "--agent-code",
        default="contract-review",
        help="合同审查 Agent code，默认 contract-review。",
    )
    parser.add_argument(
        "--user-email",
        default=DEFAULT_USER_EMAIL,
        help=f"用于本地验收的内部用户邮箱，默认 {DEFAULT_USER_EMAIL}。",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="报告输出目录；默认写入 backend/tmp/contract_review_mvp_reports/<timestamp>。",
    )
    return parser.parse_args(argv)


async def run_demo(args: argparse.Namespace) -> dict[str, Any]:
    """执行整批合同审查验收并生成报告。"""
    output_root = resolve_output_root(args.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    db = next(get_db())
    settings = get_settings()
    storage = create_file_storage(settings)
    try:
        subject = load_demo_subject(db, args.user_email)
        documents: list[dict[str, Any]] = []
        for index, raw_path in enumerate(args.contract_file, start=1):
            file_path = Path(raw_path).expanduser().resolve()
            document_dir = output_root / f"{index:02d}_{safe_stem(file_path)}"
            document_dir.mkdir(parents=True, exist_ok=True)
            document_summary = await run_single_contract(
                db=db,
                storage=storage,
                raw_bucket=settings.object_storage_bucket_raw,
                file_path=file_path,
                contract_type=args.contract_type,
                counterparty_level=args.counterparty_level,
                agent_code=args.agent_code,
                subject=subject,
                output_dir=document_dir,
                index=index,
            )
            documents.append(document_summary)
    finally:
        db.close()

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(output_root),
        "contract_type": args.contract_type,
        "counterparty_level": args.counterparty_level,
        "documents": documents,
    }
    save_json(output_root / "summary.json", summary)
    return summary


async def run_single_contract(
    *,
    db,
    storage,
    raw_bucket: str,
    file_path: Path,
    contract_type: str,
    counterparty_level: str,
    agent_code: str,
    subject: AuthenticatedSubject,
    output_dir: Path,
    index: int,
) -> dict[str, Any]:
    """执行单份合同验收，保存 JSON 与 HTML 报告。"""
    started = perf_counter()
    if not file_path.exists():
        raise FileNotFoundError(str(file_path))

    stored = storage.upload_bytes(
        bucket=raw_bucket,
        object_key=build_demo_object_key(file_path=file_path, index=index),
        content=file_path.read_bytes(),
        content_type=guess_content_type(file_path),
    )
    parse_task = await FileParseService(db, storage=storage).create_task(
        payload=FileParseTaskCreate(source_uri=stored.storage_uri),
        subject=subject,
    )
    review_task = ContractReviewService(db).create_task(
        payload=ContractReviewTaskCreate(
            agent_code=agent_code,
            file_parse_task_id=parse_task.id,
            contract_type=contract_type,
            counterparty_level=counterparty_level,
            callback_metadata={"source": "contract_review_mvp_demo"},
        ),
        subject=subject,
    )
    executed = await ContractReviewExecutionService(db).execute_task(
        task_id=review_task.id,
        subject=subject,
        request_id=f"contract-review-mvp-demo-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{index}",
    )
    fetched = ContractReviewService(db).get_task(task_id=executed.id, subject=subject)
    invocation = db.get(AgentInvocationRecord, fetched.invocation_record_id)

    parsed_snapshot = parse_task.result_snapshot or {}
    review_result = fetched.result or {}
    report_data = build_report_data(
        file_path=file_path,
        storage_uri=stored.storage_uri,
        parse_task=parse_task,
        review_task=fetched,
        invocation=invocation,
        parsed_snapshot=parsed_snapshot,
        review_result=review_result,
        elapsed_seconds=round(perf_counter() - started, 3),
    )
    save_json(output_dir / "review_result.json", report_data)
    save_json(output_dir / "parsed_snapshot.json", parsed_snapshot)
    (output_dir / "report.html").write_text(
        render_report_html(report_data, parsed_snapshot, review_result),
        encoding="utf-8",
    )
    return {
        "contract_file": str(file_path),
        "report_html": str(output_dir / "report.html"),
        "review_result_json": str(output_dir / "review_result.json"),
        "status": report_data["status"],
        "task_id": report_data["contract_review_task_id"],
        "invocation_record_id": report_data["invocation_record_id"],
        "summary": report_data["summary"],
        "highlight": report_data["highlight"],
        "token_usage": report_data["invocation"]["token_usage"],
        "latency_ms": report_data["invocation"]["latency_ms"],
    }


def build_report_data(
    *,
    file_path: Path,
    storage_uri: str,
    parse_task,
    review_task,
    invocation: AgentInvocationRecord | None,
    parsed_snapshot: dict[str, Any],
    review_result: dict[str, Any],
    elapsed_seconds: float,
) -> dict[str, Any]:
    """构建报告 JSON。

    该 JSON 是 HTML 的数据来源，也便于 reviewer 不打开页面时直接查看关键指标。
    """
    clauses = review_result.get("clauses") or []
    highlight_stats = build_highlight_stats(review_result)
    runtime_snapshot = (invocation.snapshot or {}).get("runtime", {}) if invocation else {}
    runtime_inputs = runtime_snapshot.get("inputs") or {}
    return {
        "contract_file": str(file_path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": str(review_task.status),
        "error_message": review_task.error_message,
        "storage_uri": storage_uri,
        "file_parse_task": {
            "id": parse_task.id,
            "status": str(parse_task.status),
            "reader_type": parse_task.reader_type,
            "block_count": len(parsed_snapshot.get("blocks") or []),
        },
        "contract_review_task_id": review_task.id,
        "invocation_record_id": review_task.invocation_record_id,
        "summary": review_result.get("summary") or {},
        "highlight": highlight_stats,
        "clauses": clauses,
        "warnings": review_result.get("warnings") or [],
        "invocation": {
            "status": invocation.status if invocation else None,
            "error_message": invocation.error_message if invocation else None,
            "token_usage": invocation.token_usage if invocation else None,
            "latency_ms": invocation.latency_ms if invocation else None,
            "workflow_run_id": runtime_snapshot.get("workflow_run_id"),
            "workflow_elapsed_seconds": runtime_snapshot.get("workflow_elapsed_seconds"),
            "context_chars": runtime_inputs.get("context_chars"),
        },
        "elapsed_seconds": elapsed_seconds,
    }


def build_highlight_stats(review_result: dict[str, Any]) -> dict[str, Any]:
    """统计高亮可用性。"""
    clauses = review_result.get("clauses") or []
    clauses_with_span = sum(1 for clause in clauses if clause.get("source_spans"))
    clause_warning_count = sum(len(clause.get("warnings") or []) for clause in clauses)
    return {
        "clause_count": len(clauses),
        "clauses_with_source_spans": clauses_with_span,
        "clauses_without_source_spans": len(clauses) - clauses_with_span,
        "clause_warning_count": clause_warning_count,
        "top_level_warning_count": len(review_result.get("warnings") or []),
    }


def build_highlight_index(review_result: dict[str, Any]) -> dict[str, list[HighlightMark]]:
    """按 block_id 构建高亮标记索引。"""
    index: dict[str, list[HighlightMark]] = {}
    for clause_index, clause in enumerate(review_result.get("clauses") or [], start=1):
        for span in clause.get("source_spans") or []:
            mark = make_highlight_mark(span=span, clause=clause, clause_index=clause_index)
            if mark is None:
                continue
            index.setdefault(mark.block_id, []).append(mark)
    for marks in index.values():
        marks.sort(key=lambda item: (item.start_offset, item.end_offset, item.clause_index))
    return index


def make_highlight_mark(
    *,
    span: dict[str, Any],
    clause: dict[str, Any],
    clause_index: int,
) -> HighlightMark | None:
    """把后端 source_span 转成 HTML 渲染需要的高亮标记。"""
    block_id = str(span.get("block_id") or "").strip()
    try:
        start_offset = int(span.get("start_offset"))
        end_offset = int(span.get("end_offset"))
    except (TypeError, ValueError):
        return None
    if not block_id or start_offset < 0 or end_offset <= start_offset:
        return None
    return HighlightMark(
        block_id=block_id,
        start_offset=start_offset,
        end_offset=end_offset,
        clause_index=clause_index,
        is_sensitive=bool(clause.get("is_sensitive")),
        risk_level=optional_text(clause.get("risk_level")),
        category=optional_text(clause.get("category")),
    )


def render_report_html(
    report_data: dict[str, Any],
    parsed_snapshot: dict[str, Any],
    review_result: dict[str, Any],
) -> str:
    """渲染可离线打开的 HTML 报告。"""
    highlight_index = build_highlight_index(review_result)
    blocks_html = "\n".join(
        render_block(block, highlight_index.get(str(block.get("id") or ""), []))
        for block in parsed_snapshot.get("blocks") or []
        if isinstance(block, dict)
    )
    clauses_html = "\n".join(
        render_clause_item(clause, index)
        for index, clause in enumerate(review_result.get("clauses") or [], start=1)
    )
    summary = report_data.get("summary") or {}
    highlight = report_data.get("highlight") or {}
    invocation = report_data.get("invocation") or {}
    title = f"合同审查验收报告 - {Path(report_data.get('contract_file', '')).name}"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape_html(title)}</title>
  <style>{REPORT_CSS}</style>
</head>
<body>
  <header class="topbar">
    <div>
      <h1>{escape_html(Path(report_data.get("contract_file", "")).name)}</h1>
      <p>{escape_html(report_data.get("contract_file", ""))}</p>
    </div>
    <div class="status-pill">{escape_html(report_data.get("status", ""))}</div>
  </header>
  <section class="metrics">
    {metric("命中条款", summary.get("total_clause_count"))}
    {metric("敏感条款", summary.get("sensitive_clause_count"))}
    {metric("高亮成功", highlight.get("clauses_with_source_spans"))}
    {metric("高亮缺失", highlight.get("clauses_without_source_spans"))}
    {metric("Warnings", summary.get("warning_count"))}
    {metric("Token", (invocation.get("token_usage") or {}).get("total_tokens"))}
    {metric("耗时 ms", invocation.get("latency_ms"))}
  </section>
  <main class="workspace">
    <section class="document-pane">
      <div class="pane-title">解析文本</div>
      <div class="document-flow">{blocks_html}</div>
    </section>
    <aside class="clause-pane">
      <div class="pane-title">敏感条款</div>
      <div class="clause-list">{clauses_html or '<div class="empty">未命中条款</div>'}</div>
    </aside>
  </main>
  <script>{REPORT_JS}</script>
</body>
</html>
"""


def render_block(block: dict[str, Any], marks: list[HighlightMark]) -> str:
    """渲染单个解析 block。"""
    block_id = str(block.get("id") or "")
    kind = str(block.get("kind") or block.get("type") or "block")
    text = str(block.get("text") or "")
    hit_class = " has-hit" if marks else ""
    return (
        f'<article id="block-{escape_attr(block_id)}" '
        f'class="doc-block{hit_class}" data-block-id="{escape_attr(block_id)}">'
        f'<div class="block-meta">{escape_html(block_id)} · {escape_html(kind)}</div>'
        f'<div class="block-text">{render_highlighted_text(text, marks)}</div>'
        "</article>"
    )


def render_highlighted_text(text: str, marks: list[HighlightMark]) -> str:
    """按字符 offset 渲染高亮文本。

    如果多个高亮发生重叠，保留排序后的第一个标记，避免生成嵌套 mark 导致页面结构
    不稳定；后续正式页面如需要可在后端 warning 中显式暴露重叠情况。
    """
    if not marks:
        return escape_html(text) or "&nbsp;"
    text_length = len(text)
    cursor = 0
    parts: list[str] = []
    for mark in sorted(marks, key=lambda item: (item.start_offset, item.end_offset)):
        start = min(max(mark.start_offset, 0), text_length)
        end = min(max(mark.end_offset, start), text_length)
        if start < cursor or end <= start:
            continue
        parts.append(escape_html(text[cursor:start]))
        class_name = "hit sensitive" if mark.is_sensitive else "hit"
        title = f"条款 #{mark.clause_index}"
        if mark.risk_level:
            title = f"{title} · {mark.risk_level}"
        parts.append(
            f'<mark class="{class_name}" data-clause-index="{mark.clause_index}" '
            f'title="{escape_attr(title)}">{escape_html(text[start:end])}</mark>'
        )
        cursor = end
    parts.append(escape_html(text[cursor:]))
    return "".join(parts) or "&nbsp;"


def render_clause_item(clause: dict[str, Any], index: int) -> str:
    """渲染右侧条款列表项。"""
    spans = clause.get("source_spans") or []
    first_span = spans[0] if spans else {}
    block_id = str(first_span.get("block_id") or (clause.get("source_block_ids") or [""])[0])
    risk_level = optional_text(clause.get("risk_level")) or "-"
    category = optional_text(clause.get("category")) or "-"
    warnings = clause.get("warnings") or []
    warning_html = (
        f'<div class="clause-warning">{escape_html(json.dumps(warnings, ensure_ascii=False))}</div>'
        if warnings
        else ""
    )
    return f"""
<button class="clause-item" type="button" onclick='scrollToBlock({json.dumps(block_id)})'>
  <span class="clause-topline">
    <strong>#{index}</strong>
    <span>{escape_html(risk_level)}</span>
    <span>{escape_html(category)}</span>
  </span>
  <span class="clause-text">{escape_html(str(clause.get("text") or ""))}</span>
  <span class="clause-source">{escape_html(block_id)} · {escape_html(span_offsets(first_span))}</span>
  {warning_html}
</button>
"""


def metric(label: str, value: Any) -> str:
    """渲染顶部指标。"""
    display = "-" if value is None else str(value)
    return (
        '<div class="metric">'
        f'<span class="metric-label">{escape_html(label)}</span>'
        f'<strong>{escape_html(display)}</strong>'
        "</div>"
    )


def load_demo_subject(db, user_email: str) -> AuthenticatedSubject:
    """读取本地验收使用的内部用户主体。"""
    user = db.query(UserAccount).filter(UserAccount.email == user_email).first()
    if user is None:
        raise RuntimeError(f"{user_email} user not found; run seed first")
    org = db.get(OrgUnit, user.org_unit_id)
    if org is None:
        raise RuntimeError(f"org unit not found for user {user_email}")
    return AuthenticatedSubject(
        caller_type="USER",
        user_id=user.id,
        org_unit_id=org.id,
        scopes=[],
    )


def resolve_output_root(raw_output_dir: str | None) -> Path:
    """确定报告输出目录。"""
    if raw_output_dir:
        return Path(raw_output_dir).expanduser().resolve()
    return DEFAULT_OUTPUT_ROOT / datetime.now().strftime("%Y%m%d_%H%M%S")


def build_demo_object_key(*, file_path: Path, index: int) -> str:
    """生成 MinIO 对象 key。

    key 只保留扩展名，不使用原始合同文件名，避免客户名称进入对象路径。
    """
    suffix = file_path.suffix.lower() or ".bin"
    return f"tmp/contract-review-mvp-demo/{datetime.now(timezone.utc):%Y/%m/%d}/{index:02d}_{uuid4().hex}{suffix}"


def guess_content_type(file_path: Path) -> str:
    """按扩展名返回本地验收需要的最小 MIME 类型。"""
    suffix = file_path.suffix.lower()
    if suffix == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if suffix == ".pdf":
        return "application/pdf"
    return "application/octet-stream"


def save_json(path: Path, data: Any) -> None:
    """保存 UTF-8 JSON。"""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_stem(path: Path) -> str:
    """生成适合目录名的短文件名。"""
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in path.stem)
    return (safe[:60] or "contract").strip("_") or "contract"


def span_offsets(span: dict[str, Any]) -> str:
    """格式化 span offset。"""
    if not span:
        return "no span"
    return f"{span.get('start_offset')}..{span.get('end_offset')}"


def optional_text(value: Any) -> str | None:
    """返回去空白字符串。"""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def escape_html(value: Any) -> str:
    """HTML 文本转义。"""
    return html.escape(str(value), quote=False)


def escape_attr(value: Any) -> str:
    """HTML 属性转义。"""
    return html.escape(str(value), quote=True)


REPORT_CSS = """
:root {
  color-scheme: light;
  --text: #172033;
  --muted: #65738a;
  --line: #d8e0ea;
  --soft: #f4f7fb;
  --primary: #0b6fbd;
  --danger: #b42318;
  --danger-bg: #fff0ed;
  --hit: #ffe58f;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
  color: var(--text);
  background: #eef3f8;
}
.topbar {
  height: 72px;
  padding: 12px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--line);
  background: #fff;
}
h1 { margin: 0; font-size: 18px; font-weight: 700; letter-spacing: 0; }
p { margin: 4px 0 0; color: var(--muted); font-size: 12px; }
.status-pill {
  padding: 4px 10px;
  border: 1px solid #b7ebc6;
  background: #f0fff4;
  color: #157347;
  border-radius: 6px;
  font-weight: 700;
}
.metrics {
  display: grid;
  grid-template-columns: repeat(7, minmax(120px, 1fr));
  gap: 8px;
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid var(--line);
}
.metric {
  min-height: 56px;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--soft);
}
.metric-label { display: block; color: var(--muted); font-size: 12px; }
.metric strong { display: block; margin-top: 4px; font-size: 18px; }
.workspace {
  height: calc(100vh - 145px);
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  gap: 12px;
  padding: 12px 20px 20px;
}
.document-pane, .clause-pane {
  min-height: 0;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
  overflow: hidden;
}
.pane-title {
  height: 40px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--line);
  font-weight: 700;
  background: #f8fafc;
}
.document-flow, .clause-list {
  height: calc(100% - 40px);
  overflow: auto;
}
.doc-block {
  padding: 10px 12px;
  border-bottom: 1px solid #edf1f6;
}
.doc-block.selected { outline: 2px solid var(--primary); outline-offset: -2px; }
.doc-block.has-hit { background: #fffdf2; }
.block-meta {
  margin-bottom: 6px;
  color: var(--muted);
  font-size: 12px;
}
.block-text {
  white-space: pre-wrap;
  line-height: 1.8;
  font-size: 14px;
}
mark.hit {
  padding: 1px 2px;
  border-radius: 3px;
  background: var(--hit);
}
mark.sensitive {
  background: #ffd8bf;
  box-shadow: inset 0 -2px 0 rgba(180, 35, 24, 0.45);
}
.clause-item {
  width: 100%;
  padding: 10px 12px;
  display: block;
  border: 0;
  border-bottom: 1px solid #edf1f6;
  background: #fff;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.clause-item:hover { background: #f5faff; }
.clause-topline {
  display: flex;
  gap: 8px;
  align-items: center;
  color: var(--danger);
  font-size: 12px;
  font-weight: 700;
}
.clause-text {
  display: block;
  margin-top: 6px;
  line-height: 1.6;
  font-size: 13px;
}
.clause-source {
  display: block;
  margin-top: 6px;
  color: var(--muted);
  font-size: 12px;
}
.clause-warning {
  margin-top: 6px;
  padding: 6px;
  border-radius: 4px;
  background: var(--danger-bg);
  color: var(--danger);
  font-size: 12px;
}
.empty { padding: 16px; color: var(--muted); }
@media (max-width: 980px) {
  .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .workspace { height: auto; grid-template-columns: 1fr; }
  .document-pane, .clause-pane { height: 70vh; }
}
"""


REPORT_JS = """
function scrollToBlock(blockId) {
  if (!blockId) return;
  var el = document.getElementById('block-' + blockId);
  if (!el) return;
  document.querySelectorAll('.doc-block.selected').forEach(function (node) {
    node.classList.remove('selected');
  });
  el.classList.add('selected');
  el.scrollIntoView({ behavior: 'smooth', block: 'center' });
}
"""


def main() -> None:
    """命令行入口。"""
    summary = asyncio.run(run_demo(parse_args()))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
