"""Formato comum de mensagens: o cérebro da conversa só fala com estes tipos, nunca com um canal específico."""
from dataclasses import dataclass, field


@dataclass
class Button:
    text: str
    data: str   # identifica a opção. Máx. 64 bytes (limite do Telegram), por isso é curto: "svc:3", "day:2030-01-07"


@dataclass
class Reply:
    text: str
    buttons: list[list[Button]] = field(default_factory=list)   # linhas de botões
    ask_contact: bool = False   # pede ao cliente que compartilhe o próprio número (botão nativo do canal)


@dataclass
class Incoming:
    channel: str                  # "telegram" | "whatsapp"
    external_id: str              # id da conversa no canal
    message_id: str               # único por mensagem; evita processar duas vezes (ex.: "tg:123456")
    text: str | None = None       # texto digitado
    data: str | None = None       # botão clicado
    phone: str | None = None      # SÓ quando o canal garante que é o número da pessoa (WhatsApp; contato do Telegram)
    contact_rejected: bool = False   # a pessoa compartilhou o contato de OUTRA pessoa
