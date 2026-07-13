"""合同审查 Dify workflow 本地对比实验脚本。

用法示例：

    cd backend
    python -m scripts.contract_review_compare_workflows ^
      --contract-file "D:\\path\\contract.docx" ^
      --contract-type warehouse

脚本只服务本地实验，不进入正式合同审查主链路。
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Literal, Protocol

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.exceptions import AgentHubError  # noqa: E402
from app.integrations.dify.client import DifyClient  # noqa: E402
from app.integrations.dify.schemas import (  # noqa: E402
    DifyWorkflowRunRequest,
    DifyWorkflowRunResult,
)
from app.integrations.file_reader.factory import parse_local_file  # noqa: E402
from app.modules.contract_review.context_experiment.builder import (  # noqa: E402
    FilterMode,
    build_full_context_input,
)
from app.modules.contract_review.context_experiment.block_loop_input import (  # noqa: E402
    build_document_blocks_json,
)

BLOCK_LOOP_API_KEY_ENV = "CONTRACT_REVIEW_BLOCK_LOOP_DIFY_API_KEY"
FULL_CONTEXT_API_KEY_ENV = "CONTRACT_REVIEW_FULL_CONTEXT_DIFY_API_KEY"
DEFAULT_EXPERIMENT_USER = "agenthub-contract-review-experiment"
DEFAULT_OUTPUT_ROOT = BACKEND_ROOT / "tmp" / "contract_review_experiments"
WorkflowMode = Literal["both", "block_loop", "full_context"]

_CODE_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


class WorkflowClient(Protocol):
    """实验脚本需要的 Dify client 最小协议，便于单元测试替换。"""

    async def run_workflow(
        self,
        runtime_app_id: str,
        payload: DifyWorkflowRunRequest,
        api_key: str | None = None,
    ) -> DifyWorkflowRunResult:
        """执行 Dify workflow。"""


@dataclass(frozen=True)
class WorkflowExperimentCall:
    """一次 workflow 实验调用参数。"""

    name: str
    runtime_app_id: str
    api_key: str
    inputs: dict[str, Any]
    user: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="Compare contract review block-loop and full-context Dify workflows."
    )
    parser.add_argument(
        "--contract-file",
        action="append",
        required=True,
        help="待实验合同文件路径，可重复传入多份文件。",
    )
    parser.add_argument(
        "--contract-type",
        required=True,
        help="合同类型，例如 warehouse 或 transport。",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="实验输出目录；默认写入 backend/tmp/contract_review_experiments/<timestamp>。",
    )
    parser.add_argument(
        "--file-parse-task-id",
        default=None,
        help="实验用 file_parse_task_id。多文件时会自动追加序号；不传则按文件生成本地 ID。",
    )
    parser.add_argument(
        "--filter-mode",
        choices=["none", "conservative"],
        default="none",
        help="full-context 输入过滤模式，默认 none，避免实验默认丢失正文。",
    )
    parser.add_argument(
        "--max-context-chars",
        type=int,
        default=None,
        help="full-context 最大上下文字符数；不传则不截断。",
    )
    parser.add_argument(
        "--user",
        default=DEFAULT_EXPERIMENT_USER,
        help="传给 Dify 的 user 字段，仅用于 provider 侧追踪。",
    )
    parser.add_argument(
        "--dify-base-url",
        default=None,
        help="Dify Base URL。默认读取 DIFY_BASE_URL。",
    )
    parser.add_argument(
        "--block-api-key-env",
        default=BLOCK_LOOP_API_KEY_ENV,
        help=f"逐块识别 workflow API Key 环境变量名，默认 {BLOCK_LOOP_API_KEY_ENV}。",
    )
    parser.add_argument(
        "--full-api-key-env",
        default=FULL_CONTEXT_API_KEY_ENV,
        help=f"整体识别 workflow API Key 环境变量名，默认 {FULL_CONTEXT_API_KEY_ENV}。",
    )
    parser.add_argument(
        "--workflow",
        choices=["both", "block_loop", "full_context"],
        default="both",
        help="选择要实际执行的 workflow，默认 both。",
    )
    return parser.parse_args(argv)


async def run_experiments(args: argparse.Namespace) -> dict[str, Any]:
    """执行整批合同 workflow 对比实验并返回总摘要。"""
    env_values = load_local_env_values()
    block_api_key = (
        required_env_value(args.block_api_key_env, env_values)
        if args.workflow in {"both", "block_loop"}
        else ""
    )
    full_api_key = (
        required_env_value(args.full_api_key_env, env_values)
        if args.workflow in {"both", "full_context"}
        else ""
    )
    base_url = args.dify_base_url or env_value("DIFY_BASE_URL", env_values)

    client = DifyClient()
    if base_url:
        client.base_url = normalize_dify_base_url(base_url)

    output_root = resolve_output_root(args.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    documents: list[dict[str, Any]] = []
    for index, raw_path in enumerate(args.contract_file, start=1):
        file_path = Path(raw_path).expanduser().resolve()
        file_parse_task_id = build_file_parse_task_id(
            file_path=file_path,
            explicit_id=args.file_parse_task_id,
            index=index,
            total=len(args.contract_file),
        )
        document_summary = await run_single_document_experiment(
            client=client,
            file_path=file_path,
            contract_type=args.contract_type,
            file_parse_task_id=file_parse_task_id,
            block_api_key=block_api_key,
            full_api_key=full_api_key,
            filter_mode=args.filter_mode,
            max_context_chars=args.max_context_chars,
            user=args.user,
            output_root=output_root,
            workflow=args.workflow,
        )
        documents.append(document_summary)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract_type": args.contract_type,
        "output_dir": str(output_root),
        "documents": documents,
    }
    save_json(output_root / "summary.json", summary)
    return summary


async def run_single_document_experiment(
    *,
    client: WorkflowClient,
    file_path: Path,
    contract_type: str,
    file_parse_task_id: str,
    block_api_key: str,
    full_api_key: str,
    filter_mode: FilterMode,
    max_context_chars: int | None,
    user: str,
    output_root: Path,
    workflow: WorkflowMode,
) -> dict[str, Any]:
    """对单份合同执行两组 workflow 调用并保存实验产物。"""
    parsed_document = await parse_local_file(file_path)
    parsed_snapshot = parsed_document.to_dict()

    document_dir = output_root / f"{file_path.stem}_{short_hash(str(file_path))}"
    document_dir.mkdir(parents=True, exist_ok=True)
    save_json(document_dir / "parsed_document.json", parsed_snapshot)

    block_payload_json = build_document_blocks_json(
        file_parse_task_id=file_parse_task_id,
        contract_type=contract_type,
        parsed_document=parsed_document,
    )
    block_payload = json.loads(block_payload_json)
    block_inputs = build_block_loop_workflow_inputs(
        block_payload=block_payload,
        block_payload_json=block_payload_json,
    )
    save_json(
        document_dir / "block_loop_input.json",
        {
            "workflow_inputs": block_inputs,
            "document_blocks_payload": block_payload,
        },
    )

    full_payload = build_full_context_input(
        file_parse_task_id=file_parse_task_id,
        contract_type=contract_type,
        parsed_document=parsed_document,
        filter_mode=filter_mode,
        max_context_chars=max_context_chars,
    )
    full_inputs = {
        "file_parse_task_id": file_parse_task_id,
        "contract_type": contract_type,
        "context_text": full_payload.context_text,
    }
    save_json(
        document_dir / "full_context_input.json",
        {
            "workflow_inputs": full_inputs,
            "full_context_payload": full_payload.model_dump(mode="json"),
        },
    )

    workflow_results: dict[str, dict[str, Any]] = {}
    if workflow in {"both", "block_loop"}:
        block_result = await run_workflow_call(
            client,
            WorkflowExperimentCall(
                name="block_loop",
                runtime_app_id="contract-review-block-loop",
                api_key=block_api_key,
                inputs=block_inputs,
                user=user,
            ),
        )
        save_json(document_dir / "block_loop_result.json", block_result)
        workflow_results["block_loop"] = block_result
    if workflow in {"both", "full_context"}:
        full_result = await run_workflow_call(
            client,
            WorkflowExperimentCall(
                name="full_context",
                runtime_app_id="contract-review-full-context",
                api_key=full_api_key,
                inputs=full_inputs,
                user=user,
            ),
        )
        save_json(document_dir / "full_context_result.json", full_result)
        workflow_results["full_context"] = full_result

    document_summary = {
        "file": str(file_path),
        "file_parse_task_id": file_parse_task_id,
        "artifact_dir": str(document_dir),
        "input_stats": build_input_stats(
            parsed_snapshot=parsed_snapshot,
            block_payload=block_payload,
            block_payload_json=block_payload_json,
            full_payload=full_payload.model_dump(mode="json"),
        ),
        "workflows": {
            name: summarize_workflow_result(result)
            for name, result in workflow_results.items()
        },
    }
    save_json(document_dir / "summary.json", document_summary)
    return document_summary


def build_block_loop_workflow_inputs(
    *,
    block_payload: dict[str, Any],
    block_payload_json: str,
) -> dict[str, Any]:
    """构建逐块识别 workflow 的顶层 inputs。

    Dify start node 会校验顶层表单变量，不能只把这些字段包在
    ``document_blocks_json`` 内部；否则 workflow 会在进入执行前返回 400。
    当前 Dify 表单中 ``document_blocks_json`` 的类型是 object，因此这里传 dict，
    字段名沿用 workflow 现有命名。
    """
    return {
        "schema_version": block_payload.get("schema_version"),
        "file_parse_task_id": block_payload.get("file_parse_task_id"),
        "contract_type": block_payload.get("contract_type"),
        "document_blocks_json": block_payload,
    }


async def run_workflow_call(
    client: WorkflowClient,
    call: WorkflowExperimentCall,
) -> dict[str, Any]:
    """执行单次 workflow 调用，稳定记录耗时、错误和 Dify 输出。"""
    started = perf_counter()
    try:
        result = await client.run_workflow(
            call.runtime_app_id,
            DifyWorkflowRunRequest(inputs=call.inputs, user=call.user),
            api_key=call.api_key,
        )
    except Exception as exc:  # noqa: BLE001 - 实验脚本需要把错误落盘用于对比
        return {
            "name": call.name,
            "status": "failed",
            "elapsed_ms": elapsed_ms_since(started),
            "error": public_error_message(exc),
            "outputs": {},
            "raw": None,
        }

    status = "succeeded"
    error = result.error
    if result.status and result.status.lower() not in {"succeeded", "finished", "success"}:
        status = "failed"
        error = error or result.status
    elif error:
        status = "failed"

    return {
        "name": call.name,
        "status": status,
        "elapsed_ms": elapsed_ms_since(started),
        "workflow_run_id": result.workflow_run_id,
        "task_id": result.task_id,
        "dify_status": result.status,
        "workflow_elapsed_seconds": result.elapsed_time,
        "total_tokens": result.total_tokens,
        "error": error,
        "outputs": result.outputs,
        "raw": result.raw,
    }


def summarize_workflow_result(result: dict[str, Any]) -> dict[str, Any]:
    """把 workflow 原始结果压缩成实验人员可直接阅读的摘要。"""
    contract_output = extract_contract_output(result.get("outputs") or {})
    clauses = normalize_clauses(contract_output.get("clauses"))
    warnings = normalize_warnings(contract_output.get("warnings"))
    clauses_with_source = sum(1 for clause in clauses if clause["source_block_ids"])
    return {
        "status": result.get("status"),
        "elapsed_ms": result.get("elapsed_ms"),
        "workflow_elapsed_seconds": result.get("workflow_elapsed_seconds"),
        "total_tokens": result.get("total_tokens"),
        "error": result.get("error"),
        "clause_count": len(clauses),
        "clauses_with_source_block_ids": clauses_with_source,
        "warning_count": len(warnings),
        "clauses": clauses,
        "warnings": warnings,
    }


def extract_contract_output(outputs: Any) -> dict[str, Any]:
    """从 Dify outputs 中提取合同条款包装结果。"""
    found = find_contract_payload(outputs)
    if isinstance(found, list):
        return {"clauses": found, "warnings": []}
    if isinstance(found, dict):
        clauses = found.get("clauses")
        if clauses is None:
            clauses = found.get("items") or found.get("results") or []
        warnings = found.get("warnings") or found.get("warning") or []
        return {
            "schema_version": found.get("schema_version"),
            "clauses": clauses,
            "warnings": warnings,
        }
    return {"clauses": [], "warnings": []}


def find_contract_payload(value: Any, *, depth: int = 0) -> Any:
    """递归寻找包含 clauses/warnings/schema_version 的 payload。"""
    if depth > 8:
        return None
    parsed = parse_possible_json(value)
    if isinstance(parsed, list):
        return parsed
    if not isinstance(parsed, dict):
        return None
    if any(key in parsed for key in ("clauses", "warnings", "schema_version")):
        return parsed
    for key in ("result", "text", "answer", "output", "outputs", "data"):
        if key in parsed:
            found = find_contract_payload(parsed[key], depth=depth + 1)
            if found is not None:
                return found
    if len(parsed) == 1:
        only_value = next(iter(parsed.values()))
        return find_contract_payload(only_value, depth=depth + 1)
    return None


def parse_possible_json(value: Any) -> Any:
    """兼容 Dify 常见的 JSON 字符串和 Markdown code fence。"""
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return value
    fence_match = _CODE_FENCE_RE.match(stripped)
    if fence_match:
        stripped = fence_match.group(1).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return value


def normalize_clauses(raw_clauses: Any) -> list[dict[str, Any]]:
    """将 Dify 条款输出裁剪为 summary.json 需要的字段。"""
    if not isinstance(raw_clauses, list):
        return []
    clauses: list[dict[str, Any]] = []
    for index, item in enumerate(raw_clauses, start=1):
        if isinstance(item, str):
            clauses.append(
                {
                    "index": index,
                    "text": item.strip(),
                    "category": None,
                    "source_block_ids": [],
                    "confidence": None,
                }
            )
            continue
        if not isinstance(item, dict):
            continue
        clauses.append(
            {
                "index": index,
                "text": first_text(
                    item,
                    "text",
                    "clause_text",
                    "content",
                    "original_text",
                    "matched_text",
                ),
                "category": first_text(item, "category", "clause_type", "type"),
                "source_block_ids": extract_source_block_ids(item),
                "confidence": optional_float(item.get("confidence")),
            }
        )
    return clauses


def normalize_warnings(raw_warnings: Any) -> list[dict[str, Any]]:
    """将 Dify warning 输出裁剪为稳定摘要。"""
    if raw_warnings is None:
        return []
    items = raw_warnings if isinstance(raw_warnings, list) else [raw_warnings]
    warnings: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, str):
            text = item.strip()
            if text:
                warnings.append({"message": text})
            continue
        if not isinstance(item, dict):
            continue
        warning = {
            "code": first_text(item, "code", "type", "reason"),
            "message": first_text(item, "message", "text", "detail"),
            "block_id": first_text(item, "block_id", "source_block_id"),
        }
        warnings.append({key: value for key, value in warning.items() if value})
    return warnings


def extract_source_block_ids(item: dict[str, Any]) -> list[str]:
    """从条款 item 中提取 source_block_ids，支持多种 Dify 输出写法。"""
    candidates: list[Any] = [
        item.get("source_block_ids"),
        item.get("source_blocks"),
        item.get("block_ids"),
        item.get("block_id"),
        item.get("source_block_id"),
    ]
    source = item.get("source")
    if isinstance(source, dict):
        candidates.extend(
            [
                source.get("source_block_ids"),
                source.get("block_ids"),
                source.get("block_id"),
                source.get("source_block_id"),
            ]
        )
    block_ids: list[str] = []
    for candidate in candidates:
        for block_id in coerce_string_list(candidate):
            if block_id not in block_ids:
                block_ids.append(block_id)
    return block_ids


def build_input_stats(
    *,
    parsed_snapshot: dict[str, Any],
    block_payload: dict[str, Any],
    block_payload_json: str,
    full_payload: dict[str, Any],
) -> dict[str, Any]:
    """构建输入规模统计，避免 summary.json 塞入完整上下文。"""
    blocks = parsed_snapshot.get("blocks") if isinstance(parsed_snapshot.get("blocks"), list) else []
    sections = (
        parsed_snapshot.get("sections")
        if isinstance(parsed_snapshot.get("sections"), list)
        else []
    )
    metadata = parsed_snapshot.get("metadata") if isinstance(parsed_snapshot.get("metadata"), dict) else {}
    document_text_chars = sum(len(str(block.get("text") or "")) for block in blocks if isinstance(block, dict))
    block_loop_blocks = block_payload.get("blocks") if isinstance(block_payload.get("blocks"), list) else []
    return {
        "filename": metadata.get("filename"),
        "file_type": metadata.get("file_type"),
        "reader_type": metadata.get("reader_type"),
        "paragraph_count": metadata.get("paragraph_count"),
        "table_count": metadata.get("table_count"),
        "parsed_block_count": len(blocks),
        "section_count": len(sections),
        "document_text_chars": document_text_chars,
        "block_loop_block_count": len(block_loop_blocks),
        "block_loop_input_json_chars": len(block_payload_json),
        "full_context_chars": len(str(full_payload.get("context_text") or "")),
        "full_context_included_block_count": len(full_payload.get("included_block_ids") or []),
        "full_context_filtered_block_count": len(full_payload.get("filtered_block_ids") or []),
        "full_context_warnings": full_payload.get("warnings") or [],
    }


def load_local_env_values() -> dict[str, str]:
    """读取本地 .env，支持从仓库根目录或 backend 目录运行脚本。"""
    env_paths = [
        Path.cwd() / ".env",
        BACKEND_ROOT / ".env",
    ]
    values: dict[str, str] = {}
    for env_path in env_paths:
        if not env_path.exists():
            continue
        values.update(parse_env_file(env_path))
    return values


def parse_env_file(path: Path) -> dict[str, str]:
    """解析简单 KEY=VALUE 形式的 .env 文件。"""
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def env_value(name: str, env_values: dict[str, str]) -> str | None:
    """优先读取真实环境变量，其次读取本地 .env。"""
    value = os.getenv(name)
    if value:
        return value
    return env_values.get(name) or None


def required_env_value(name: str, env_values: dict[str, str]) -> str:
    """读取必填环境变量，缺失时给出稳定错误。"""
    value = env_value(name, env_values)
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


def normalize_dify_base_url(value: str) -> str:
    """归一化 Dify base url，兼容带 /v1 的配置。"""
    normalized = value.rstrip("/")
    if normalized.endswith("/v1"):
        normalized = normalized[: -len("/v1")]
    return normalized


def resolve_output_root(output_dir: str | None) -> Path:
    """确定本次实验输出根目录。"""
    if output_dir:
        return Path(output_dir).expanduser().resolve()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return DEFAULT_OUTPUT_ROOT / timestamp


def build_file_parse_task_id(
    *,
    file_path: Path,
    explicit_id: str | None,
    index: int,
    total: int,
) -> str:
    """构建实验用 file_parse_task_id。"""
    if explicit_id and total == 1:
        return explicit_id
    if explicit_id:
        return f"{explicit_id}-{index:02d}"
    stat = file_path.stat()
    seed = f"{file_path}|{stat.st_size}|{int(stat.st_mtime)}"
    return f"local-{short_hash(seed)}"


def short_hash(value: str) -> str:
    """返回短哈希，用于实验 ID 和目录名去重。"""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]


def save_json(path: Path, payload: Any) -> None:
    """保存 UTF-8 JSON 文件。"""
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def elapsed_ms_since(started: float) -> int:
    """计算毫秒耗时。"""
    return int((perf_counter() - started) * 1000)


def public_error_message(exc: Exception) -> str:
    """生成可写入实验结果的错误信息。"""
    if isinstance(exc, AgentHubError):
        return str(exc)
    return f"{exc.__class__.__name__}: {exc}"


def first_text(data: dict[str, Any], *keys: str) -> str | None:
    """按候选字段读取第一个非空字符串。"""
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def optional_float(value: Any) -> float | None:
    """宽松转换 float。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def coerce_string_list(value: Any) -> list[str]:
    """把字符串或列表值统一成字符串列表。"""
    if value is None:
        return []
    if isinstance(value, str):
        normalized = value.strip()
        return [normalized] if normalized else []
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = first_text(item, "block_id", "source_block_id", "id")
            else:
                text = str(item).strip() if item is not None else None
            if text:
                result.append(text)
        return result
    return []


def main(argv: list[str] | None = None) -> None:
    """脚本入口。"""
    args = parse_args(argv)
    summary = asyncio.run(run_experiments(args))
    print(json.dumps({"summary": summary["output_dir"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
