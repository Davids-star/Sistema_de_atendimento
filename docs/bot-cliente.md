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
**Menu da cliente (3 opções):**
- **💅 Agendar horário**: o fluxo abaixo.
- **🕒 Horários de atendimento**: mostra o seu expediente (ex.: *Seg a sex: 09:00–12:00 e 14:00–19:00 · Sábado: 09:00–16:00 · Domingo: fechado*)
  e os **próximos dias que ainda têm vaga**, sem precisar escolher serviço. Também abre se a cliente digitar *horários*, *agenda*, *vagas* ou *expediente*.
  Os horários vêm do que você cadastrou em Configurações; dias lotados ou bloqueados não aparecem como livres.
- **🗓 Meus agendamentos**: o que ela marcou (e cancelamento).

Fluxo de agendar: Menu → **Agendar** → serviço → dia (só dias com horário livre) → horário → [celular] → [nome] → resumo → **Confirmar**.
Também há **Meus agendamentos** (com cancelamento). Tudo por botões; texto livre só para o nome.

- Cliente conhecida (mesmo celular) nunca digita nada: o bot já sabe quem é.
- Horário ocupado no meio do caminho: o bot avisa e oferece outros.
- O agendamento sai como **confirmado** (a cliente já confirmou no chat) e o dono é avisado no Telegram, se estiver configurado.

## Segurança
- No Telegram o celular só vale pelo botão **"Compartilhar meu número"** e se o contato for da própria pessoa.
  - **Modo de teste** (`BOT_ALLOW_TYPED_PHONE=true`): aceita o número digitado, mas esse número não é confirmado. Nesse caso a pessoa
    **vê e cancela só o que ela mesma marcou naquela conversa** (cada agendamento guarda a conversa que o criou). Para ver os demais
    agendamentos do cadastro, precisa compartilhar o contato. Isso impede que alguém digite o número de outra pessoa e depois enxergue
    o que ela marcar.
  - No **WhatsApp** o número já vem confirmado, então a cliente vê e cancela todos os seus agendamentos normalmente.
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

## Avisos e lembretes para a cliente
Funcionam pelo Telegram, para quem já conversou com o bot (o sistema não tem como achar o Telegram de alguém só pelo telefone).

- **Mudança pelo painel:** ao **remarcar o horário** ou **cancelar** um agendamento no painel, a cliente recebe a mensagem
  (no cancelamento, com um botão para marcar outro horário). Quando é a própria cliente que cancela pelo bot, não há aviso.
  Trocar só as observações ou o serviço sem mudar o horário também não avisa.
- **Lembrete antes do atendimento:** para agendamentos **confirmados**, 4 horas antes: *"chegue 20 minutos antes, por volta das HH:MM"*.
  - Não é enviado entre 21h e 7h; atendimento cedo recebe o lembrete às 7h.
  - Sai uma vez só, mesmo com o programa do bot rodando em dois lugares.
  - Se o envio falhar, tenta de novo no minuto seguinte (até 10 vezes).
  - Se você **remarcar**, a cliente recebe um lembrete novo para o novo horário.
  - Agendamentos feitos só pelo painel, para quem nunca falou com o bot, não têm para onde enviar.
- O lembrete roda junto com o bot: basta deixar `python customer_bot.py` aberto.
- Ajustes no `.env`: `REMINDER_HOURS_BEFORE` (4), `ARRIVE_EARLY_MINUTES` (20), `REMINDER_QUIET_START_HOUR` (21), `REMINDER_QUIET_END_HOUR` (7).

No WhatsApp, mensagens que o sistema inicia fora da janela de 24 horas exigem modelos aprovados pela Meta; isso entra na etapa do WhatsApp.

## Cancelamentos: quem cancelou e aviso ao dono
- Todo cancelamento guarda **quem cancelou e quando** (ex.: *Maria Souza (cliente, pelo Telegram)* ou *Ana (painel)*). Aparece em vermelho no cartão
  do agendamento cancelado, na aba Agendamentos, e fica na trilha de auditoria.
- O **dono é avisado** (e-mail e, se estiver configurado, Telegram) quando:
  - a **cliente cancela pelo bot**; ou
  - **outro usuário do painel** (não o dono) cancela. Quando o próprio dono cancela, não há aviso.
  O aviso traz cliente, celular, serviço, horário, **quem cancelou** e quando.
- Quando o cancelamento é feito **pelo painel**, a **cliente** também é avisada pelo bot (com botão para marcar outro horário).

## Números do dashboard
- **Agendamentos**: o que está/foi agendado, **sem os cancelados** (o texto abaixo informa quantos foram cancelados).
- **Clientes atendidos**: só quem teve ao menos um atendimento **concluído** no período. Cancelado, ausente, pendente e confirmado não contam.
- **Clientes novos**: pessoas **cadastradas** no período (ainda não significa que foram atendidas).
