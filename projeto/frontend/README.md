# Radar Público — Frontend

Frontend da aplicação web do **Radar Público**, ferramenta cívica para consulta de dados abertos de servidores públicos federais (ativos e aposentados).

---

## 1. Escolha e Justificativa da Stack

A stack do frontend foi selecionada visando alto desempenho, segurança de ponta a ponta, facilidade de manutenção e conformidade estrita com as diretrizes de produto (`docs/PRODUCT.md`), design system (`docs/DESIGN.md`), contrato de API (`docs/api.md`) e regras de contribuição (`CONTRIBUTING.md`).

### 1.1. React 19 + TypeScript
- **Por que React?**
  - **Interface declarativa orientada a estado:** A aplicação possui fluxos complexos de busca (nome exato, nome aproximado com `%`, busca combinada por cargo, órgão, UF e situação), paginação até 10.000 registros e visualização de detalhe. O React gerencia essas transições de estado de forma previsível e reativa.
  - **Acessibilidade (WCAG 2.2 AA):** Facilidade para integrar atributos ARIA (`aria-live="polite"`, `aria-busy`, `aria-invalid`, `aria-describedby`) e gerenciar o foco do teclado de acordo com as diretrizes do projeto.
  - **Ecossistema e maturidade:** Pacotes com licenças permissivas (MIT/BSD/Apache-2.0) e ampla compatibilidade com as rotinas de auditoria de segurança do CI (`npm audit --audit-level=high`).
- **Por que TypeScript?**
  - **Contrato de API tipado:** Garante aderência estrita às entidades definidas no contrato da API (`GET /api/servidores`), prevenindo falhas de acesso a propriedades em tempo de execução.
  - **Manutenibilidade:** Melhora o autocompletar e a refatoração segura em equipe.

### 1.2. Vite 8
- **Build ultrarrápido:** Inicialização instantânea e Hot Module Replacement (HMR) eficiente baseado em módulos ES nativos no navegador.
- **Produção otimizada:** Gera assets estáticos minificados, com hash de conteúdo e divisão de código (`dist/`), ideais para serem servidos por um webserver estático.
- **Proxy reverso no desenvolvimento:** Permite redirecionar chamadas locais `/api` para `http://localhost:5000` sem necessidade de configurar CORS no backend durante o desenvolvimento local.

### 1.3. CSS Nativo com Tokens OKLCH
- **Fidelidade ao Sistema Visual (`docs/DESIGN.md`):** Utilização direta das variáveis CSS com cores no espaço perceptivo OKLCH (`--bg`, `--surface`, `--line`, `--line-strong`, `--primary`, `--ink`, etc.).
- **Zero Runtime Overhead:** Sem dependências adicionais pesadas de CSS-in-JS ou frameworks utilitários que aumentem o bundle desnecessariamente.
- **Tipografia e Inclusão:** Fontes `IBM Plex Sans` (400 a 700) e `IBM Plex Mono` (400 e 500) servidas pelo próprio site, a partir dos pacotes `@fontsource` (licença OFL, só o subconjunto latino), sem requisições ao Google Fonts. Alvos de toque mínimos de 44px e respeito automático a `prefers-reduced-motion`.

### 1.4. Nginx Unprivileged (`nginxinc/nginx-unprivileged:alpine`)
- **Container não-root:** Executa como usuário sem privilégios (`USER nginx`), atendendo à política de segurança de containers do projeto (`no-new-privileges:true`). Os arquivos servidos pertencem ao root, e o nginx só os lê.
- **Porta 8080 nativa:** O container serve o tráfego HTTP diretamente na porta `8080`, porta padrão segura para processos não-root.
- **Proxy reverso transparente:** As rotas iniciadas em `/api/` são encaminhadas internamente para o serviço de backend (`http://backend:5000/api/`), mantendo a mesma origem para o cliente (sem CORS). O `X-Forwarded-For` é substituído pelo IP real do cliente, para que o limite de requisições por IP no backend não possa ser burlado com um cabeçalho forjado.
- **Erros do proxy em JSON:** Se o backend estiver fora do ar ou demorar mais de 15 s, o nginx responde no formato de `docs/api.md` (`SERVIDOR_INDISPONIVEL` 502, `TEMPO_ESGOTADO` 504). Os erros do próprio backend passam intactos.
- **Cabeçalhos de segurança e cache:** `security-headers.conf` (CSP só com a própria origem, `nosniff`, `Referrer-Policy`, proibição de iframe); assets com hash (inclusive as fontes) ficam em cache por 1 ano e o `index.html` é sempre revalidado.
- **SPA Fallback e Performance:** Compressão Gzip e roteamento client-side via `try_files $uri $uri/ /index.html`; arquivos com extensão que não existem retornam 404, e não o `index.html`.

### 1.5. Testes e Qualidade
- **Vitest + Testing Library:** Suíte de testes unitários e de integração de componentes rápida, com ambiente `jsdom` e matchers `@testing-library/jest-dom`.
- **Oxlint / TypeScript:** TypeScript em modo `strict` e Oxlint com regras de hooks do React e de acessibilidade (`jsx-a11y`). Avisos também reprovam o lint (`--deny-warnings`).
- **Versões exatas:** `package.json` sem `^`/`~` e `.npmrc` com `save-exact=true`; o `package-lock.json` é versionado e o CI instala com `npm ci --ignore-scripts`.
- **Hadolint:** Validação estrita de boas práticas e segurança do `Dockerfile`.

---

## 2. Estrutura de Pastas

```text
projeto/frontend/
├── public/              # Assets estáticos públicos (favicon)
├── src/
│   ├── api.ts               # GET /api/servidores: requisição, tempo limite, validação da resposta e erros
│   ├── App.css              # Estilos dos componentes (classes de docs/design/componentes.css)
│   ├── App.tsx              # Tela de busca: topo, formulário, região viva, resultados e fonte dos dados
│   ├── format.ts            # Números em pt-BR (valores e contagens)
│   ├── index.css            # Tokens globais do Design System (OKLCH, tipografia)
│   ├── main.tsx             # Ponto de entrada React e fontes IBM Plex
│   ├── mensagens.ts         # Textos dos resultados e da região viva
│   ├── NaoInformado.tsx     # Travessão de campo null, com "não informado" para leitores de tela
│   ├── nome.ts              # Normalização e validação do nome (mesmas regras do backend)
│   ├── ResultsList.tsx      # Resultados em lista (celular)
│   ├── ResultsTable.tsx     # Resultados em tabela (desktop)
│   ├── SearchForm.tsx       # Campo de nome, botão Buscar e erro no campo
│   ├── SearchResults.tsx    # Um componente por estado: carregando, vazio, erro, resultados
│   ├── SiteHeader.tsx       # Topo com a marca
│   ├── SituacaoPill.tsx     # Pílula Ativo/Aposentado com marcador
│   ├── types.ts             # Tipos do contrato da API
│   ├── useBuscaServidores.ts # Estado da busca: URL (?nome=), histórico e cancelamento
│   ├── *.test.ts(x)         # Testes (Vitest + Testing Library)
│   ├── testUtils.ts         # Respostas do contrato e fetch falso para os testes
│   └── setupTests.ts        # Configuração de matchers do Vitest
├── .dockerignore        # Arquivos ignorados no contexto de build do Docker
├── Dockerfile           # Multi-stage build com Node 24 e Nginx Unprivileged
├── index.html           # HTML base com metadados
├── nginx.conf           # Configuração do Nginx (porta 8080, gzip, cache e proxy /api/)
├── security-headers.conf # Cabeçalhos de segurança incluídos em todas as respostas
├── package.json         # Dependências e scripts de execução
├── package-lock.json    # Versões fixadas e auditadas
├── tsconfig.json        # Configuração do compilador TypeScript
└── vite.config.ts       # Configuração do Vite, Vitest e proxy reverso local
```

---

## 3. Como Executar

### 3.1. Desenvolvimento Local

1. Instale as dependências:
   ```bash
   npm ci
   ```

2. Execute o servidor de desenvolvimento:
   ```bash
   npm run dev
   ```
   A aplicação estará disponível em `http://localhost:5173`, só na sua máquina. As chamadas a `/api` vão para `http://localhost:5000`; para usar outro backend, defina `API_PROXY_TARGET` (ex.: `API_PROXY_TARGET=http://localhost:5001 npm run dev`).

3. Executar verificações de qualidade:
   ```bash
   npm run lint   # Verificação de código
   npm test       # Execução dos testes automatizados
   npm run build  # Compilação e verificação de tipos
   ```

### 3.2. Execução via Docker

1. Build da imagem:
   ```bash
   docker build -t projeto-frontend .
   ```

2. Executar o container:
   ```bash
   docker run -p 8080:8080 projeto-frontend
   ```
   Acesse `http://localhost:8080`. Fora do Docker Compose não existe o serviço `backend`, então `/api` responde `502 SERVIDOR_INDISPONIVEL`; a interface funciona normalmente.

### 3.3. Execução via Docker Compose (no diretório `projeto/`)

```bash
docker compose up --build frontend
```
O serviço estará acessível na porta 8080, pronto para se comunicar com o backend via rede interna do Docker.

---

## 4. Tela de busca (issue #11)

- **Busca por nome exato** (`GET /api/servidores?nome=`). O nome é validado antes de chamar a API com as regras do backend: de 2 a 100 caracteres depois de normalizar (sem acento, maiúsculas, espaços simples), só letras, espaços, `'`, `.` e `-`, sem `--`. O erro aparece no próprio campo (`aria-invalid` e `aria-describedby`), e um 400 da API também.
- **Estado na URL:** a busca fica em `?nome=`. Recarregar, copiar o link e voltar/avançar no navegador mantêm a busca; repetir a mesma busca não cria outra entrada no histórico.
- **Cancelamento e tempo limite:** cada busca tem o próprio `AbortController`; trocar de busca ou sair da tela cancela a anterior, e uma resposta atrasada nunca sobrescreve a atual. O navegador desiste em `SEARCH_TIMEOUT_MS` (20 s), acima dos 15 s do nginx, para o 504 do nginx chegar antes.
- **Respostas:** o corpo é conferido contra o contrato antes de ir para a tela. `404 NAO_ENCONTRADO` é o estado "nenhum vínculo"; 429 e 503 viram aviso informativo com os segundos do `Retry-After`; 502, 504, 500, falha de rede, resposta sem JSON e resposta fora do formato têm mensagens próprias.
- **Acessibilidade:** uma região viva (`<output>`) sempre presente anuncia "Buscando…" e o resultado; durante a busca o botão fica `aria-disabled` e o campo só leitura, sem perder o foco.
- **Fica para depois:** nome parecido, filtros e menu do celular (#20); paginação, detalhe e contagem regressiva do `Retry-After` (#21). Enquanto não há paginação, a tela diz quantos dos resultados estão sendo mostrados.
