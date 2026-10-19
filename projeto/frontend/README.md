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

### 1.2. Vite 6
- **Build ultrarrápido:** Inicialização instantânea e Hot Module Replacement (HMR) eficiente baseado em módulos ES nativos no navegador.
- **Produção otimizada:** Gera assets estáticos minificados, com hash de conteúdo e divisão de código (`dist/`), ideais para serem servidos por um webserver estático.
- **Proxy reverso no desenvolvimento:** Permite redirecionar chamadas locais `/api` para `http://localhost:5000` sem necessidade de configurar CORS no backend durante o desenvolvimento local.

### 1.3. CSS Nativo com Tokens OKLCH
- **Fidelidade ao Sistema Visual (`docs/DESIGN.md`):** Utilização direta das variáveis CSS com cores no espaço perceptivo OKLCH (`--bg`, `--surface`, `--line`, `--line-strong`, `--primary`, `--ink`, etc.).
- **Zero Runtime Overhead:** Sem dependências adicionais pesadas de CSS-in-JS ou frameworks utilitários que aumentem o bundle desnecessariamente.
- **Tipografia e Inclusão:** Fontes `IBM Plex Sans` e `IBM Plex Mono`, alvos de toque mínimos de 44px e respeito automático a `prefers-reduced-motion`.

### 1.4. Nginx Unprivileged (`nginxinc/nginx-unprivileged:alpine`)
- **Container não-root:** Executa como usuário sem privilégios (`USER nginx`), atendendo à política de segurança de containers do projeto (`no-new-privileges:true`).
- **Porta 8080 nativa:** O container serve o tráfego HTTP diretamente na porta `8080`, porta padrão segura para processos não-root.
- **Proxy reverso transparente:** As rotas iniciadas em `/api/` são encaminhadas internamente para o serviço de backend (`http://backend:5000/api/`), mantendo a mesma origem para o cliente e simplificando o tráfego de rede.
- **SPA Fallback e Performance:** Suporte a compressão Gzip e roteamento client-side via `try_files $uri $uri/ /index.html`.

### 1.5. Testes e Qualidade
- **Vitest + Testing Library:** Suíte de testes unitários e de integração de componentes rápida, com ambiente `jsdom` e matchers `@testing-library/jest-dom`.
- **Oxlint / TypeScript:** Verificação de tipos e linting rápido.
- **Hadolint:** Validação estrita de boas práticas e segurança do `Dockerfile`.

---

## 2. Estrutura de Pastas

```text
projeto/frontend/
├── public/              # Assets estáticos públicos (favicons, manifest)
├── src/
│   ├── App.css          # Estilos do componente principal
│   ├── App.test.tsx     # Testes automatizados do componente
│   ├── App.tsx          # Componente base da aplicação
│   ├── index.css        # Tokens globais do Design System (OKLCH, tipografia)
│   ├── main.tsx         # Ponto de entrada React
│   └── setupTests.ts    # Configuração de matchers do Vitest
├── .dockerignore        # Arquivos ignorados no contexto de build do Docker
├── Dockerfile           # Multi-stage build com Node 24 e Nginx Unprivileged
├── index.html           # HTML base com importação de fontes e metadados
├── nginx.conf           # Configuração do Nginx (porta 8080, gzip e proxy /api/)
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
   A aplicação estará disponível em `http://localhost:8080`.

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
   Acesse `http://localhost:8080`.

### 3.3. Execução via Docker Compose (no diretório `projeto/`)

```bash
docker compose up --build frontend
```
O serviço estará acessível na porta 8080, pronto para se comunicar com o backend via rede interna do Docker.
