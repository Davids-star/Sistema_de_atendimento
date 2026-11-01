# Manual de Integração da API: Sistema de Agendamento & WhatsApp AI Agent

Este documento descreve a API HTTP Machine-to-Machine (M2M) disponibilizada pelo **Sistema de Agendamento** para consumo exclusivo pelo **WhatsApp AI Agent**.

---

## 1. Visão Geral da Arquitetura

O **Sistema de Agendamento** é a autoridade central e única fonte oficial para dados, disponibilidade de agenda, regras de negócio e integridade cadastral.

O **WhatsApp AI Agent** atua como cliente HTTP autenticado, executando operações em nome dos clientes via API RESTful.

```
┌─────────────────────────┐         HTTP (M2M)        ┌─────────────────────────┐
│   WhatsApp AI Agent     │ ────────────────────────► │  Sistema de Agendamento │
│ (bot_agendamento)       │   X-Agent-API-Key: ...    │  (backend FastAPI)      │
└─────────────────────────┘                           └────────────┬────────────┘
                                                                   │ SQL
                                                                   ▼
                                                      ┌─────────────────────────┐
                                                      │ PostgreSQL com Exclude  │
                                                      │ Constraint GiST         │
                                                      └─────────────────────────┘
```

> [!IMPORTANT]
> O WhatsApp AI Agent **nunca acessa o PostgreSQL diretamente**. Todas as operações passam pelas validações de horário, concorrência atômica, normalização e auditoria do Sistema de Agendamento.

---

## 2. Configurações de Ambiente

A URL-base e o segredo de integração são configuráveis por variáveis de ambiente em ambos os projetos, eliminando referências fixas a `localhost`.

### No Sistema de Agendamento (`agendamento/.env`):
```ini
WHATSAPP_AGENT_API_KEY=sua_chave_secreta_aqui
```

### No WhatsApp AI Agent (`bot_agendamento/.env`):
```ini
BOOKING_API_BASE_URL=http://127.0.0.1:8000/api/v1/agent
BOOKING_API_KEY=sua_chave_secreta_aqui
BOOKING_API_TIMEOUT_SECONDS=10
```

*Para ambientes de produção com servidores Linux, basta apontar `BOOKING_API_BASE_URL=https://agenda.seudominio.com/api/v1/agent`.*

---

## 3. Segurança e Autenticação

Todas as requisições enviadas pelo WhatsApp AI Agent devem incluir a chave de autenticação em um dos cabeçalhos abaixo:

- **Cabeçalho Dedicado (Recomendado):**
  `X-Agent-API-Key: sua_chave_secreta_aqui`
- **Cabeçalho Padrão Bearer:**
  `Authorization: Bearer sua_chave_secreta_aqui`

Caso a chave esteja incorreta ou ausente:
`HTTP 401 Unauthorized` com JSON estruturado.

---

## 4. Padrão Uniforme de Resposta (Envelope JSON)

Todas as respostas da API seguem estritamente a mesma estrutura.

### Sucesso (`success: true`):
```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

### Falha (`success: false`):
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "HORARIO_INDISPONIVEL",
    "message": "Esse horário já está ocupado por outro agendamento"
  }
}
```

### Tabela de Códigos de Erro Semânticos:
| Código | HTTP Status | Significado / Orientação para a IA |
|---|---|---|
| `NAO_AUTORIZADO` | 401 / 403 | Chave de integração inválida ou cliente tentando alterar agendamento de terceiros. |
| `DADOS_INVALIDOS` | 422 | Telefone fora do formato ou parâmetros nulos. |
| `CLIENTE_NAO_ENCONTRADO` | 404 | Nenhum cadastro para o telefone informado. O bot deve solicitar o nome do cliente. |
| `SERVICO_INEXISTENTE` | 404 | O `service_id` informado não existe ou está inativo. |
| `HORARIO_INDISPONIVEL` | 409 | Vaga já ocupada ou fora da grade. O bot deve consultar `/availability` e sugerir alternativas. |
| `AGENDAMENTO_NAO_ENCONTRADO` | 404 | ID de agendamento não existe. |
| `OPERACAO_INVALIDA` | 409 | Tentativa de cancelar agendamento já concluído ou já cancelado. |
| `ERRO_INTERNO` | 500 | Falha inesperada do servidor. |

---

## 5. Formatos de Dados

- **Telefone:** Dígitos com DDD (E.164 sem `+`). Ex.: `5511999998888`. A API aceita variações com máscara (ex.: `(11) 99999-8888`) e as normaliza automaticamente.
- **Data:** `YYYY-MM-DD` (ex.: `2026-11-02`).
- **Data e Hora (Timestamp):** Padrão ISO 8601 com fuso horário (ex.: `2026-11-02T14:30:00-03:00`).
- **Valores Monetários:** Centavos de Real (`price_cents: 5000` = R$ 50,00) acompanhados de `price_formatted` (`"R$ 50,00"`).

---

## 6. Catálogo de Endpoints

### 6.1. Consultar Serviços e Preços
Retorna a lista de serviços ativos do negócio.

- **Método / Rota:** `GET /services` *(alias: `/servicos`)*
- **Exemplo de Resposta:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "Corte Tradicional",
      "duration_minutes": 30,
      "price_cents": 5000,
      "price_formatted": "R$ 50,00"
    },
    {
      "id": 2,
      "name": "Barba Completa",
      "duration_minutes": 30,
      "price_cents": 3500,
      "price_formatted": "R$ 35,00"
    }
  ],
  "error": null
}
```

---

### 6.2. Consultar Horários Disponíveis
Calcula em tempo real os horários de início livres para o dia informado, cruzando expediente, bloqueios e agendamentos existentes.

- **Método / Rota:** `GET /availability` *(alias: `/horarios-disponiveis`)*
- **Parâmetros de Consulta (Query):**
  - `date` *(obrigatório)*: data no formato `YYYY-MM-DD` (ex.: `2026-11-02`).
  - `service_id` *(obrigatório)*: ID do serviço (ex.: `1`).
- **Exemplo de Resposta:**
```json
{
  "success": true,
  "data": {
    "date": "2026-11-02",
    "service_id": 1,
    "duration_minutes": 30,
    "available_slots": [
      "09:00",
      "09:30",
      "10:00",
      "14:00",
      "15:30"
    ],
    "available_slots_iso": [
      "2026-11-02T09:00:00-03:00",
      "2026-11-02T09:30:00-03:00",
      "2026-11-02T10:00:00-03:00",
      "2026-11-02T14:00:00-03:00",
      "2026-11-02T15:30:00-03:00"
    ]
  },
  "error": null
}
```

---

### 6.3. Localizar Cliente por Telefone
Permite ao agente saber se a pessoa que está conversando no WhatsApp já é cliente cadastrada.

- **Método / Rota:** `GET /clients/by-phone` *(alias: `/clientes/por-telefone`)*
- **Query Param:** `phone` (ex.: `11999998888` ou `5511999998888`).
- **Exemplo de Resposta (Encontrado):**
```json
{
  "success": true,
  "data": {
    "id": 42,
    "name": "Maria Silva",
    "phone": "5511999998888"
  },
  "error": null
}
```
- **Se não encontrado:** Retorna `HTTP 404` com erro `CLIENTE_NAO_ENCONTRADO`.

---

### 6.4. Cadastrar Cliente
Cria ou recupera atomicamente o cadastro do cliente pelo telefone.

- **Método / Rota:** `POST /clients` *(alias: `/clientes`)*
- **Corpo da Requisição (JSON):**
```json
{
  "name": "Maria Silva",
  "phone": "11999998888"
}
```
- **Exemplo de Resposta (`HTTP 201 Created`):**
```json
{
  "success": true,
  "data": {
    "id": 42,
    "name": "Maria Silva",
    "phone": "5511999998888",
    "created": true
  },
  "error": null
}
```

---

### 6.5. Criar Agendamento (Reserva com Validação Estrita)
Cria o agendamento no sistema. O sistema verifica a disponibilidade no exato instante da gravação e impede duplicidade via restrição atômica no banco de dados.

- **Método / Rota:** `POST /appointments` *(alias: `/agendamentos`)*
- **Corpo da Requisição (JSON):**
```json
{
  "client_phone": "11999998888",
  "client_name": "Maria Silva",
  "service_id": 1,
  "starts_at": "2026-11-02T14:00:00-03:00",
  "notes": "Agendado via WhatsApp AI Agent"
}
```
- **Exemplo de Resposta (`HTTP 201 Created`):**
```json
{
  "success": true,
  "data": {
    "appointment_id": 150,
    "client_id": 42,
    "client_name": "Maria Silva",
    "client_phone": "5511999998888",
    "service_id": 1,
    "service_name": "Corte Tradicional",
    "status": "confirmed",
    "starts_at": "2026-11-02T14:00:00-03:00",
    "ends_at": "2026-11-02T14:30:00-03:00",
    "price_cents": 5000,
    "price_formatted": "R$ 50,00",
    "notes": "Agendado via WhatsApp AI Agent",
    "cancelled_by": null
  },
  "error": null
}
```

---

### 6.6. Consultar Agendamentos de um Cliente
Lista os agendamentos que pertencem ao número de telefone do WhatsApp.

- **Método / Rota:** `GET /appointments` *(alias: `/agendamentos/cliente`)*
- **Query Params:**
  - `phone` *(obrigatório)*: telefone do cliente.
  - `upcoming` *(opcional, default `true`)*: se `true`, traz apenas agendamentos futuros confirmados/pendentes.
- **Exemplo de Resposta:**
```json
{
  "success": true,
  "data": [
    {
      "appointment_id": 150,
      "client_id": 42,
      "client_name": "Maria Silva",
      "client_phone": "5511999998888",
      "service_id": 1,
      "service_name": "Corte Tradicional",
      "status": "confirmed",
      "starts_at": "2026-11-02T14:00:00-03:00",
      "ends_at": "2026-11-02T14:30:00-03:00",
      "price_cents": 5000,
      "price_formatted": "R$ 50,00"
    }
  ],
  "error": null
}
```

---

### 6.7. Remarcar Agendamento
Permite ao cliente alterar o horário ou o serviço do agendamento.
O sistema valida a **titularidade** (se o agendamento pertence ao telefone informado) e a **disponibilidade estrita** do novo horário.

- **Método / Rota:** `PATCH /appointments/{id}` *(alias: `/agendamentos/{id}`)*
- **Corpo da Requisição (JSON):**
```json
{
  "phone": "11999998888",
  "starts_at": "2026-11-02T16:00:00-03:00",
  "service_id": 1
}
```
- **Regra de Segurança:** Se o agendamento `{id}` pertencer a outro telefone, a API responde `HTTP 403 Forbidden` (`NAO_AUTORIZADO`).

---

### 6.8. Cancelar Agendamento
Cancela o agendamento e libera imediatamente o horário para outros clientes.

- **Método / Rota:** `POST /appointments/{id}/cancel` *(alias: `/agendamentos/{id}/cancelar`)*
- **Corpo da Requisição (JSON):**
```json
{
  "phone": "11999998888",
  "reason": "Imprevisto pessoal"
}
```
- **Regra de Segurança:** Validação de posse do telefone (`HTTP 403` se pertencer a outro cliente).
- **Notificação:** O sistema registra a autoria do cancelamento no log de auditoria e avisa o painel do dono.

---

## 7. Documentação OpenAPI / Swagger Interativa

Com o backend do Sistema de Agendamento em execução, a documentação OpenAPI 3.0 e a interface interativa do Swagger estão disponíveis em:

- **Swagger UI:** `http://localhost:8000/docs` (Tag: `WhatsApp AI Agent`)
- **Redoc:** `http://localhost:8000/redoc`
- **JSON OpenAPI:** `http://localhost:8000/openapi.json`

