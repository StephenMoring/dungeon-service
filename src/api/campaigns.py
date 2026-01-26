from fastapi import APIRouter
from services.dm_agent import chat

campaigns_router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@campaigns_router.post("/chat", status_code=201)
def campaign_chat():
    # needs to take in the txt submitted by user and stores to db, not sureif actually needs to send this part to llm
    return chat()
