# 📅 Sistema de Atendimento e Agendamento Inteligente

Um sistema completo de gestão de atendimentos e agendamentos integrado com **Bot de Inteligência Artificial para WhatsApp**, desenvolvido para modernizar e automatizar o fluxo de barbearias, salões de beleza, estúdios e clínicas.

---

## 💡 O que é o projeto?

O sistema funciona como uma recepção digital inteligente para o negócio:
- **Painel de Gestão (Web e App Mobile):** Permite acompanhar faturamento em tempo real, gerenciar clientes, serviços, horários de funcionamento e atendimentos.
- **Cálculo Dinâmico de Vagas:** Encadeamento automático de horários baseado na duração de cada serviço (ex.: se o procedimento dura 50 minutos, a próxima vaga é calculada exatamente para 50 minutos depois).
- **Garantia Anti-Conflito:** Bloqueio atômico no banco de dados para impedir que duas pessoas agendem o mesmo horário simultaneamente.
- **Multiplataforma:** Acessível via Web pelo navegador e instalado no celular como aplicativo nativo (Android).

---

## 🤖 Por que usamos o Bot no WhatsApp?

A maioria dos clientes prefere agendar e tirar dúvidas diretamente pelo WhatsApp. Em vez de o profissional interromper os atendimentos para responder mensagens ou perder clientes fora do expediente:

- O **Bot com IA** atende 24 horas por dia de forma natural e humanizada.
- Consulta os serviços, preços e horários livres direto no sistema em tempo real.
- Concretiza e confirma o agendamento sozinho, já atualizando a agenda e notificando o dono.

---

## 🛠️ Tecnologias Utilizadas

- **Frontend & App:** Vue 3, Vuetify 3, Vite, Capacitor (geração do APK Android).
- **Backend API:** Python, FastAPI, SQLAlchemy 2, Alembic.
- **Banco de Dados:** PostgreSQL hospedado no Neon (Lakebase Postgres Serverless).
- **Hospedagem & Nuvem:** Render (Backend API) e Vercel (Frontend Web).
- **Mensageria & IA:** WhatsApp Gateway (Baileys / Node.js) conectado ao Agent Core (FastAPI / Gemini).
