# Avisos de cadastro pelo Telegram

Quando alguém cria uma conta e **confirma o e-mail**, o dono recebe, por e-mail e pelo Telegram: nome, celular,
e-mail, como entrou (e-mail ou Google), **localização aproximada pelo IP**, o IP e a hora. No Telegram há os botões
**Liberar acesso** e **Recusar**.

## Configurar (uma vez, gratuito)
1. No Telegram, procure **@BotFather**, envie `/newbot` e siga as perguntas. Ele entrega um **token**
   (algo como `123456:ABC...`). **Não compartilhe esse token com ninguém.**
2. No `.env`: `TELEGRAM_BOT_TOKEN=<o token>`
3. Em outro terminal, deixe o "ouvinte" rodando:
   ```bash
   cd /home/felipe/Vscode/agendamento && source .venv/bin/activate && python backend/telegram_bot.py
   ```
4. No Telegram, abra o seu bot e envie `/start`. Ele responde com a linha `TELEGRAM_CHAT_ID=...`.
5. Copie essa linha para o `.env`, **reinicie a API** e o ouvinte.
6. Envie `/start` de novo: o bot responde "Tudo certo!".

Só o chat do `TELEGRAM_CHAT_ID` consegue liberar ou recusar. Cliques de qualquer outro chat são ignorados.

## Sobre a localização
- É **aproximada** (cidade/estado, pelo IP), pode estar errada e, no celular, costuma mostrar a cidade da operadora.
- Testando no seu computador, o IP é local e a mensagem diz "rede local (sem localização)". Só funciona com acesso pela internet.
- Para descobrir a cidade, o IP é enviado a um serviço externo (`GEOIP_URL`). Confira os termos e limites dele.
  Deixe `GEOIP_URL=` vazio para desligar.
- Atrás de um proxy/HTTPS na publicação, o IP visto pela API pode ser o do proxy. Isso precisa ser ajustado na Etapa 10.
- O formulário de cadastro já avisa a pessoa de que o IP e a localização são registrados (LGPD).
