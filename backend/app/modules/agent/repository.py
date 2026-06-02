from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.agent.models import Agent, AgentKnowledgeBase


class AgentRepository:
    def __init__(self, db: Session):
        self.db = db

    def add_agent(self, agent: Agent) -> Agent:
        self.db.add(agent)
        self.db.flush()
        return agent

    def get_agent(self, agent_id: str) -> Agent | None:
        return self.db.get(Agent, agent_id)

    def get_agent_by_code(self, code: str) -> Agent | None:
        stmt = select(Agent).where(Agent.code == code)
        return self.db.scalars(stmt).one_or_none()

    def list_agents(self, limit: int = 100, offset: int = 0) -> list[Agent]:
        stmt = select(Agent).order_by(Agent.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def add_agent_knowledge_base(self, binding: AgentKnowledgeBase) -> AgentKnowledgeBase:
        self.db.add(binding)
        self.db.flush()
        return binding

    def list_agent_knowledge_bases(self, agent_id: str) -> list[AgentKnowledgeBase]:
        stmt = (
            select(AgentKnowledgeBase)
            .where(AgentKnowledgeBase.agent_id == agent_id)
            .order_by(AgentKnowledgeBase.priority.desc())
        )
        return list(self.db.scalars(stmt))

    def get_agent_knowledge_base(self, agent_id: str, knowledge_base_id: str) -> AgentKnowledgeBase | None:
        stmt = select(AgentKnowledgeBase).where(
            AgentKnowledgeBase.agent_id == agent_id,
            AgentKnowledgeBase.knowledge_base_id == knowledge_base_id,
        )
        return self.db.scalars(stmt).one_or_none()

    def delete_agent_knowledge_base(self, binding: AgentKnowledgeBase) -> None:
        self.db.delete(binding)
        self.db.flush()
