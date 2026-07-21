"""最小 MySQL checkpoint + LangGraph interrupt/resume 验证。

脚本不注册正式路由。第一次请求触发 LangGraph ``interrupt()`` 并把轻量 state
写入 MySQL；第二次请求使用新 Session 读取同一 thread/checkpoint，从人工复核节点
继续，验证跨请求恢复语义。
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from sqlalchemy import JSON, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class SpikeCheckpoint(Base):
    __tablename__ = "risk_graph_checkpoint_spike"

    thread_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    next_node: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[dict] = mapped_column(JSON, nullable=False)


class SpikeState(TypedDict, total=False):
    thread_id: str
    checkpoint_version: int
    review_event_id: str
    execution_state: str


@dataclass(frozen=True)
class ResumeResult:
    thread_id: str
    before_version: int
    after_version: int
    resumed_node: str
    execution_state: str


def _build_graph():
    builder = StateGraph(SpikeState)

    def route_review(state: SpikeState) -> SpikeState:
        del state
        return {"execution_state": "WAITING_REVIEW"}

    def interrupt_review(state: SpikeState) -> SpikeState:
        interrupt({"thread_id": state["thread_id"], "target": "FIELD:quantity"})
        return {}

    def apply_human_review(state: SpikeState) -> SpikeState:
        if not state.get("review_event_id"):
            raise RuntimeError("review_event_id is required")
        return {"execution_state": "SUCCEEDED"}

    builder.add_node("route_review", route_review)
    builder.add_node("interrupt_review", interrupt_review)
    builder.add_node("apply_human_review", apply_human_review)
    builder.add_conditional_edges(
        START,
        lambda state: "resume" if state.get("review_event_id") else "start",
        {"start": "route_review", "resume": "apply_human_review"},
    )
    builder.add_edge("route_review", "interrupt_review")
    builder.add_edge("interrupt_review", END)
    builder.add_edge("apply_human_review", END)
    return builder.compile(name="risk-checkpoint-spike")


def run(database_url: str) -> ResumeResult:
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    graph = _build_graph()
    thread_id = "risk-checkpoint-spike"

    first = graph.invoke(
        SpikeState(thread_id=thread_id, checkpoint_version=0),
    )
    if "__interrupt__" not in first or first.get("execution_state") != "WAITING_REVIEW":
        raise RuntimeError("LangGraph interrupt was not produced")
    first.pop("__interrupt__", None)
    with Session(engine) as session:
        session.merge(
            SpikeCheckpoint(
                thread_id=thread_id,
                version=1,
                next_node="apply_human_review",
                state=dict(first),
            )
        )
        session.commit()

    with Session(engine) as session:
        checkpoint = session.scalar(
            select(SpikeCheckpoint).where(SpikeCheckpoint.thread_id == thread_id)
        )
        if checkpoint is None or checkpoint.version != 1:
            raise RuntimeError("checkpoint was not restored")
        resume_state = SpikeState(**checkpoint.state)
        resume_state.update(
            checkpoint_version=checkpoint.version,
            review_event_id="review-spike",
        )
        resumed = graph.invoke(resume_state)
        checkpoint.version = 2
        checkpoint.next_node = "finalize_document_result"
        checkpoint.state = dict(resumed)
        session.commit()
        result = ResumeResult(
            thread_id=thread_id,
            before_version=1,
            after_version=checkpoint.version,
            resumed_node="apply_human_review",
            execution_state=resumed["execution_state"],
        )

    with engine.begin() as connection:
        SpikeCheckpoint.__table__.drop(connection, checkfirst=True)
    engine.dispose()
    return result


def main() -> int:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        raise RuntimeError("TEST_DATABASE_URL is required for the checkpoint spike")
    print(json.dumps(asdict(run(database_url)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
