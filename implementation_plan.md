# Integração de Ollama como Second-Pass Reviewer

Este documento descreve o plano técnico para integrar o Ollama como modelo secundário de revisão financeira na aplicação, mantendo a Mistral como motor principal e adotando uma arquitetura limpa com abstração de LLMs.

## User Review Required
> [!IMPORTANT]
> **Alterações no Frontend**
> Como a estrutura da resposta do backend vai mudar significativamente (de uma simples string Markdown para um objeto JSON completo com pontos de concordância, riscos, etc.), o frontend React (`StockInfo.jsx`) precisará de ser atualizado para apresentar visualmente estes novos dados. Está de acordo com a modificação do frontend para exibir a análise consolidada num formato mais estruturado?

> [!WARNING]
> **Latência da Análise**
> Como a pipeline agora executa a análise Mistral seguida de forma sequencial pela análise Ollama, o tempo total de espera do utilizador pela resposta vai aumentar. É recomendável, num passo futuro, usar WebSockets ou Server-Sent Events (SSE), mas para já usaremos chamadas REST síncronas. Concorda com esta abordagem inicial?

## Proposed Changes

### Camada de Abstração de Inteligência Artificial
Vamos criar uma nova diretoria `backend/core/ai` para centralizar a comunicação com os modelos de linguagem, promovendo abstração, reutilização e desacoplamento.

#### [NEW] `backend/core/ai/base.py`
- Criação da classe abstrata `AIProvider`.
- Definição do contrato `generate(prompt: str, is_json: bool = False) -> str | dict`.

#### [NEW] `backend/core/ai/mistral.py`
- Criação da classe `MistralProvider` estendendo `AIProvider`.
- Migração da lógica de comunicação com a API da Mistral atualmente existente em `backend/routers/stock.py` e `utils/utils.py`.
- Suporta a variável de ambiente `MISTRAL_API_KEY`.

#### [NEW] `backend/core/ai/ollama.py`
- Criação da classe `OllamaProvider` estendendo `AIProvider`.
- Lógica de comunicação com a API REST do Ollama (suportando os parâmetros `format="json"` para garantir o output estruturado).
- Suporta variáveis de ambiente `OLLAMA_BASE_URL` (default: `http://localhost:11434`) e `OLLAMA_API_KEY` (para soluções cloud).

#### [NEW] `backend/core/ai/orchestrator.py`
- Criação da classe `AnalysisOrchestrator`.
- Lógica de negócio da pipeline:
  1. Chama `MistralProvider` com os dados da ação.
  2. Recebe a resposta primária.
  3. Prepara um prompt injetando a resposta da Mistral e pedindo revisão em JSON.
  4. Chama `OllamaProvider`.
  5. Agrega as respostas no contrato de saída consolidado.

---

### Endpoints da API

#### [MODIFY] `backend/routers/stock.py`
- Refatorização da função `ai_analysis`.
- Remoção do acoplamento direto à Mistral usando o `requests`.
- Instanciação do `AnalysisOrchestrator` e devolução da estrutura JSON consolidada solicitada:
  ```json
  {
    "ticker": "...",
    "primary_analysis": "...",
    "agreement_points": [],
    "disagreement_points": [],
    "additional_risks": [],
    ...
  }
  ```

#### [MODIFY] `utils/utils.py`
- Atualização da função *legacy* `get_ai_analysis` (usada em sítios onde a pipeline antiga pode ainda ser invocada) para usar a nova abstração `MistralProvider`, garantindo que não duplicamos código de chamadas API.

---

### Atualização do Frontend (React)

#### [MODIFY] `frontend/src/pages/StockInfo.jsx`
- Atualização da função `fetchAiAnalysis` para lidar com a nova resposta JSON em vez de um texto plano.
- Construção de novos componentes visuais para exibir:
  - **A Análise Principal (Mistral)** (num formato colapsável ou primário).
  - **A Revisão do Ollama**, listando `agreement_points`, `disagreement_points`, `additional_risks`, etc.
  - **O Veredicto Consolidado** (`final_rating` e `confidence_score`).

## Verification Plan

### Automated / Backend Tests
- Correr os servidores localmente.
- Garantir que as variáveis de ambiente `OLLAMA_BASE_URL` e `MISTRAL_API_KEY` estão carregadas.
- Efetuar uma chamada de teste direta ao endpoint de análise via Postman/cURL para verificar se o JSON consolidado cumpre o formato exigido.

### Manual Verification
- Na UI da app (Frontend), introduzir um *ticker* válido, gerar a análise AI e observar o comportamento do ecrã e a interface consolidada com os *insights* de ambos os LLMs.
