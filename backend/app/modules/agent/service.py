from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.agent.models import Agent, AgentKnowledgeBase
from app.modules.agent.repository import AgentRepository
from app.modules.agent.schemas import AgentCreate, AgentKnowledgeBaseBind, AgentUpdate
from app.modules.knowledge.repository import KnowledgeRepository


def _is_agent_kb_unique_constraint_error(exc: IntegrityError) -> bool:
    """判断 IntegrityError 是否来自 Agent-KB 绑定唯一约束。"""
    constraint_name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    if constraint_name == "uq_agent_knowledge_base":
        return True

    message = str(exc.orig).lower()
    return (
        "uq_agent_knowledge_base" in message
        or (
            "agent_knowledge_base" in message
            and "agent_id" in message
            and "knowledge_base_id" in message
        )
    )


class AgentService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = AgentRepository(db)
        self.knowledge_repository = KnowledgeRepository(db)

    def create_agent(self, payload: AgentCreate) -> Agent:
        if self.repository.get_agent_by_code(payload.code):
            raise ConflictError("agent code already exists")
        agent = Agent(**payload.model_dump())
        self.repository.add_agent(agent)
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def update_agent(self, agent_id: str, payload: AgentUpdate) -> Agent:
        agent = self.repository.get_agent(agent_id)
        if agent is None:
            raise NotFoundError("agent not found")
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(agent, field, value)
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def bind_knowledge_base(self, agent_id: str, payload: AgentKnowledgeBaseBind) -> AgentKnowledgeBase:
        if self.repository.get_agent(agent_id) is None:
            raise NotFoundError("agent not found")
        if self.knowledge_repository.get_knowledge_base(payload.knowledge_base_id) is None:
            raise NotFoundError("knowledge base not found")
        existing = self.repository.get_agent_knowledge_base(agent_id, payload.knowledge_base_id)
        if existing is not None:
            raise ConflictError("knowledge base already bound to agent")
        binding = AgentKnowledgeBase(
            agent_id=agent_id,
            knowledge_base_id=payload.knowledge_base_id,
            priority=payload.priority,
        )
        self.repository.add_agent_knowledge_base(binding)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if not _is_agent_kb_unique_constraint_error(exc):
                raise
            raise ConflictError("knowledge base already bound to agent")
        self.db.refresh(binding)
        return binding

    def get_agent_by_code(self, code: str) -> Agent:
        agent = self.repository.get_agent_by_code(code)
        if agent is None:
            raise NotFoundError("agent not found")
        return agent

    def list_agent_knowledge_bases(self, agent_id: str) -> list[AgentKnowledgeBase]:
        if self.repository.get_agent(agent_id) is None:
            raise NotFoundError("agent not found")
        return self.repository.list_agent_knowledge_bases(agent_id)

    def unbind_knowledge_base(self, agent_id: str, knowledge_base_id: str) -> None:
        binding = self.repository.get_agent_knowledge_base(agent_id, knowledge_base_id)
        if binding is None:
            raise NotFoundError("binding not found")
        self.repository.delete_agent_knowledge_base(binding)
        self.db.commit()

    def list_agents(self) -> list[Agent]:
        return self.repository.list_agents()
