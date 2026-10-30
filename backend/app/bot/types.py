"""Formato comum de mensagens: o cérebro da conversa só fala com estes tipos, nunca com um canal específico."""
from dataclasses import dataclass, field


# Limites dos canais que o bot respeita desde já (o mais apertado vence), para o WhatsApp entrar sem refazer a conversa:
MAX_BUTTON_TEXT = 20    # WhatsApp: título de botão de resposta (até 20) e de linha de lista (até 24)
MAX_DESCRIPTION = 72    # WhatsApp: descrição de linha de lista
MAX_OPTIONS = 10        # WhatsApp: no máximo 10 linhas numa lista (3 se forem botões de resposta)
MAX_DATA_BYTES = 64     # Telegram: callback_data


@dataclass
class Button:
    text: str                      # título curto (até 20 caracteres)
    data: str                      # identifica a opção ("svc:3", "day:2030-01-07"); até 64 bytes
    description: str | None = None # detalhe opcional (ex.: duração e preço). Telegram junta ao título; WhatsApp mostra abaixo
    url: str | None = None         # botão que ABRE um endereço (ex.: o WhatsApp do dono) em vez de enviar uma escolha ao bot


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
