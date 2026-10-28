# Redefinição e troca de senha

## Para o dono
- **Esqueci minha senha:** na tela de login, "Esqueci minha senha" → informe o e-mail → abra o link recebido (vale 30 min, uso único) → escolha a nova senha.
- **Alterar senha (logado):** Configurações → "Minha conta · Alterar senha".
- Ao trocar a senha, todas as sessões antigas são encerradas (inclusive em outros aparelhos).

## Configurar o envio de e-mail (uma vez)
O e-mail só é enviado com `MAIL_MODE=smtp`. Com Gmail (gratuito):
1. Ative a verificação em duas etapas da conta Google.
2. Em https://myaccount.google.com/apppasswords crie uma **senha de app** (16 letras).
3. No `.env`:
   ```
   MAIL_MODE=smtp
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=seuemail@gmail.com
   SMTP_PASSWORD=<a senha de app, sem espaços>
   SMTP_FROM=seuemail@gmail.com
   ```
4. Reinicie a API.

**Para testar sem e-mail:** `MAIL_MODE=console` imprime a mensagem (com o link) no terminal onde a API roda.
Nunca use esse modo em produção: o link é equivalente a uma senha temporária.

## Último recurso (sem e-mail)
Com acesso ao servidor:
```bash
source .venv/bin/activate && python backend/reset_admin_password.py
```
