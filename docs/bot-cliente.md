# Bot do cliente (agendamento por conversa)

O cliente agenda, vê e cancela horários conversando com um bot. Hoje no **Telegram** (gratuito, ótimo para testar);
o **WhatsApp** entra depois trocando só o adaptador, porque a conversa é toda feita por um "cérebro" que não conhece o canal.

## Onde fica (pasta `backend/app/bot/`)
```
backend/app/bot/
├── types.py            formato comum de mensagens (Incoming, Reply, Button)
├── texts.py            TODOS os textos do bot (ajuste o tom aqui)
├── engine.py           o cérebro: passos da conversa, validações, agendamento
└── channels/
    └── telegram.py     adaptador do Telegram (traduz de/para o cérebro)
backend/customer_bot.py  programa que mantém o bot do cliente rodando
```
Para o WhatsApp, o futuro adaptador ficará em `channels/whatsapp.py`, sem mexer no cérebro.

## Como a conversa funciona
Menu → **Agendar** → serviço → dia (só dias com horário livre) → horário → [celular] → [nome] → resumo → **Confirmar**.
Também há **Meus agendamentos** (com cancelamento). Tudo por botões; texto livre só para o nome.

- Cliente conhecida (mesmo celular) nunca digita nada: o bot já sabe quem é.
- Horário ocupado no meio do caminho: o bot avisa e oferece outros.
- O agendamento sai como **confirmado** (a cliente já confirmou no chat) e o dono é avisado no Telegram, se estiver configurado.

## Segurança
- No Telegram o celular só vale pelo botão **"Compartilhar meu número"** e se o contato for da própria pessoa.
  Digitar um número não prova nada, então não dá para ver ou cancelar agendamentos de outra pessoa.
- Botões antigos ou forjados são revalidados no banco antes de qualquer ação.
- Cada mensagem é registrada uma única vez (o Telegram pode reenviar).
- Limite de 30 mensagens por minuto por conversa.
- Só conversas privadas; grupos são ignorados.

## Ligar (uma vez, gratuito)
1. No Telegram, abra o **@BotFather**, envie `/newbot` e crie um bot **para clientes** (nome e usuário à sua escolha).
   Use um bot **diferente** do bot de avisos do dono.
2. Coloque o token no `.env` (não compartilhe): `CUSTOMER_BOT_TOKEN=...`
3. Rode a migração do banco e o bot, cada um uma vez:
   ```bash
   cd /home/felipe/Vscode/agendamento/backend && source ../.venv/bin/activate && alembic upgrade head
   python customer_bot.py
   ```
4. No Telegram, abra o seu bot e envie `/start`.

Antes de testar, deixe cadastrados no painel: ao menos um **serviço**, o **horário de funcionamento** e o **intervalo** dos horários.
