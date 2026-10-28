# Login com Google (painel do dono)

O botão "Fazer login com o Google" só aparece quando `GOOGLE_CLIENT_ID` está preenchido no `.env`.

## Como funciona
1. O Google entrega ao navegador um token assinado.
2. O backend (`POST /api/v1/auth/google`) confere a assinatura, a validade e se o token foi emitido para o nosso ID de cliente.
3. A conta Google **só entra se o e-mail dela já for de um administrador cadastrado**. Nenhuma conta é criada automaticamente.
4. No primeiro acesso, a conta Google fica ligada ao administrador (campo `google_sub`). Depois disso, quem vale é o ID da conta Google, não o e-mail.

## Configuração (uma vez)
1. Acesse https://console.cloud.google.com/ e crie um projeto (gratuito).
2. **APIs e serviços → Tela de consentimento OAuth**: tipo "Externo", informe o nome do app e seu e-mail. Em "Usuários de teste", adicione o Gmail do dono.
3. **APIs e serviços → Credenciais → Criar credenciais → ID do cliente OAuth**:
   - Tipo: **Aplicativo da Web**
   - Origens JavaScript autorizadas: `http://localhost:5173` (e, na publicação, o endereço real com HTTPS)
   - Não é necessário preencher "URIs de redirecionamento" nem usar o "segredo do cliente".
4. Copie o **ID do cliente** (termina em `.apps.googleusercontent.com`) para o `.env`:
   `GOOGLE_CLIENT_ID=...`
5. Reinicie a API.

## Cadastrar um administrador que só entra com Google
```bash
source .venv/bin/activate && python backend/create_admin.py
```
Informe o e-mail da conta Google e **deixe a senha em branco**.
