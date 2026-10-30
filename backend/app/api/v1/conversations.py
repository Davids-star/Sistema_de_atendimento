"""Tela "Atendimento": clientes que pediram para falar com uma pessoa."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models import AdminUser, Client, Conversation
from app.schemas.conversation import ConversationOut
from app.services import audit

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _out(db: Session, conv: Conversation) -> ConversationOut:
    client = db.get(Client, conv.client_id) if conv.client_id else None
    return ConversationOut(id=conv.id, channel=conv.channel, client_name=client.name if client else None,
                           client_phone=(client.phone if client else None) or conv.phone, phone_verified=conv.phone_verified,
                           needs_human=conv.needs_human, handoff_at=conv.handoff_at, handoff_note=conv.handoff_note,
                           last_message_at=conv.last_message_at)


@router.get("", response_model=list[ConversationOut])
def list_conversations(needs_human: bool = Query(True), limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db),
                       _: AdminUser = Depends(get_current_admin)):
    """Por padrão, só as que esperam por uma pessoa (a mais antiga primeiro: quem espera há mais tempo aparece no topo)."""
    query = select(Conversation).where(Conversation.needs_human == needs_human).limit(limit)
    query = query.order_by(Conversation.handoff_at.asc(), Conversation.id) if needs_human else query.order_by(Conversation.id.desc())
    return [_out(db, c) for c in db.scalars(query)]


@router.post("/{conversation_id}/resolve", response_model=ConversationOut)
def resolve(conversation_id: int, db: Session = Depends(get_db), me: AdminUser = Depends(get_current_admin)):
    """O assunto foi resolvido: tira da lista e devolve a conversa ao assistente."""
    conv = db.get(Conversation, conversation_id)
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversa não encontrada")
    if conv.needs_human:
        conv.needs_human, conv.handoff_note = False, None
        if conv.state == "handoff":
            conv.state, conv.context = "idle", {}
        audit.record(db, me, "handoff_resolve", "conversation", conv.id)
        db.commit()
    return _out(db, conv)
