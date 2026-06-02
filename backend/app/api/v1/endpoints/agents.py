from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.responses import APIResponse, success
from app.db.session import get_db
from app.modules.agent.schemas import AgentCreate, AgentKnowledgeBaseBind, AgentKnowledgeBaseRead, AgentRead, AgentUpdate
from app.modules.agent.service import AgentService

router = APIRouter()


@router.get("", response_model=APIResponse[list[AgentRead]])
def list_agents(db: Session = Depends(get_db)) -> APIResponse[list[AgentRead]]:
    items = [AgentRead.model_validate(item) for item in AgentService(db).list_agents()]
    return success(items)


@router.post("", response_model=APIResponse[AgentRead])
def create_agent(payload: AgentCreate, db: Session = Depends(get_db)) -> APIResponse[AgentRead]:
    agent = AgentService(db).create_agent(payload)
    return success(AgentRead.model_validate(agent))


@router.put("/{agent_id}", response_model=APIResponse[AgentRead])
def update_agent(
    agent_id: str,
    payload: AgentUpdate,
    db: Session = Depends(get_db),
) -> APIResponse[AgentRead]:
    agent = AgentService(db).update_agent(agent_id, payload)
    return success(AgentRead.model_validate(agent))


@router.post("/{agent_id}/knowledge-bases", response_model=APIResponse[dict[str, str]])
def bind_knowledge_base(
    agent_id: str,
    payload: AgentKnowledgeBaseBind,
    db: Session = Depends(get_db),
) -> APIResponse[dict[str, str]]:
    binding = AgentService(db).bind_knowledge_base(agent_id, payload)
    return success({"id": binding.id})


@router.get("/{agent_id}/knowledge-bases", response_model=APIResponse[list[AgentKnowledgeBaseRead]])
def list_agent_knowledge_bases(
    agent_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[list[AgentKnowledgeBaseRead]]:
    bindings = AgentService(db).list_agent_knowledge_bases(agent_id)
    return success([AgentKnowledgeBaseRead.model_validate(b) for b in bindings])


@router.delete("/{agent_id}/knowledge-bases/{knowledge_base_id}", response_model=APIResponse[None])
def unbind_knowledge_base(
    agent_id: str,
    knowledge_base_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[None]:
    AgentService(db).unbind_knowledge_base(agent_id, knowledge_base_id)
    return success(None)
