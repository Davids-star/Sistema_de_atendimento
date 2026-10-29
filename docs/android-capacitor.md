# App Android (Capacitor) com avisos mesmo fechado

O painel vira um app Android com o **Capacitor**. Os avisos chegam de duas formas:
- **Com o app aberto:** o sino do painel (atualiza sozinho a cada 20 s) e um aviso na tela.
- **Com o app fechado:** push pelo **Firebase Cloud Messaging (FCM, gratuito)**.

## 1. Firebase (uma vez)
1. Em https://console.firebase.google.com crie um projeto (pode desativar o Google Analytics).
2. **Adicionar app → Android.** Nome do pacote: `br.com.agenda.app` (é o `appId` de `frontend/capacitor.config.json`; se mudar um, mude o outro).
3. Baixe o **`google-services.json`** e coloque em `frontend/android/app/` (a pasta aparece no passo 3).
4. Em **Configurações do projeto → Contas de serviço → Gerar nova chave privada**, baixe o JSON.
   **Guarde fora do projeto** (ex.: `/home/felipe/segredos/firebase.json`). Ele dá poder de enviar push: nunca vá para o Git nem para o chat.
5. No `.env` do servidor: `FCM_SERVICE_ACCOUNT_FILE=/home/felipe/segredos/firebase.json` e reinicie a API.

## 2. Servidor
- A API precisa de **HTTPS** (o Android bloqueia HTTP puro). Para testar em casa use um túnel com HTTPS (ex.: Cloudflare Tunnel ou ngrok).
- No `.env`, libere a origem do app: `CORS_ORIGINS=http://localhost:5173,https://localhost`
- Rode `alembic upgrade head` (cria as tabelas de notificações e aparelhos).

## 3. Gerar o app
Precisa do **Android Studio** (traz o SDK e o emulador).
```bash
cd frontend
VITE_API_URL=https://SEU-ENDERECO-HTTPS npm run build
npx cap add android        # só na primeira vez (cria a pasta android/)
npx cap sync android       # sempre que mudar o código web
npx cap open android       # abre o Android Studio: ▶ Run
```
Dica de ícone do aviso: o Firebase recomenda um ícone branco sobre fundo transparente em
`android/app/src/main/res/drawable` e, no `AndroidManifest.xml`, o meta-data `com.google.firebase.messaging.default_notification_icon`.

## 4. Como funciona
- Ao entrar no app, ele cria o canal **"Avisos"**, **pede a permissão de notificações** (Android 13+) e registra o aparelho no servidor.
- Quando algo acontece (cancelamento, novo agendamento, novo cadastro), o servidor cria a notificação e, em até ~5 s, envia o push.
  Quem **já leu** o aviso dentro do app não recebe o push.
- Tocar no aviso abre a tela relacionada. Só links internos do painel são aceitos.
- Ao **sair** da conta, o aparelho deixa de receber os avisos dela. Se o mesmo aparelho entra com outra conta, os avisos passam para ela.
- O servidor apaga sozinho tokens que o Firebase informa como inválidos (`UNREGISTERED`). Outros erros nunca apagam o token.

## 5. Para testar
Com o app instalado e logado, cancele um agendamento pelo bot do cliente (ou como outro usuário). O push deve chegar em segundos.
Se não chegar: confira `logs/app.log` (mensagens "FCM recusou" ou "falha no despachante de push") e se `FCM_SERVICE_ACCOUNT_FILE` está preenchido.

## Limitações conhecidas
- Se o FCM estiver fora do ar na hora, o push daquele aviso **não é reenviado** (o aviso continua no sino).
- Avisos com mais de 10 minutos não viram push (evita enxurrada ao ligar o push depois).
- Só Android. iOS exigiria outra configuração (APNs) e conta Apple de desenvolvedor.
