<div align="center">

<img src="public/banner.png" alt="OASIS Dashboard Banner" width="500"/>

# OASIS Dashboard

**A Professional Web Platform for OASIS Simulation Engine Monitoring and Control**

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Node](https://img.shields.io/badge/node-%3E%3D20.0.0-brightgreen)
![TypeScript](https://img.shields.io/badge/TypeScript-5.8-blue)
![React](https://img.shields.io/badge/React-19-61DAFB)
![Python](https://img.shields.io/badge/Python-3.11%2B-yellow)
![License](https://img.shields.io/badge/license-Proprietary-red)
![Status](https://img.shields.io/badge/status-Active%20Development-yellow)

</div>

---

## Overview

**OASIS Dashboard** is an enterprise-grade web application designed for real-time monitoring and control of the **OASIS (Open-ended Autonomous Social Intelligence Simulation)** engine. It provides an intuitive interface for configuring, executing, and analyzing complex social simulation experiments with support for local large language models (e.g., Qwen3-8B).

---

## Features

### 🎯 Core Capabilities

- **Real OASIS Engine Integration**: Built on the authentic `camel-oasis` framework, ensuring simulation accuracy and depth
- **Local Model Support**: Run local LLMs via Ollama (Qwen3-8B) without external API dependencies, reducing costs and protecting data privacy
- **Real-time Monitoring**: Live tracking of simulation status, KPI metrics (active agents, total posts, polarization index), and agent activities
- **Dynamic Control**: Adjust parameters, inject events, and intervene in agent behaviors during simulation runtime
- **Advanced Visualization**: Social network graphs, trend analysis, and geospatial heatmaps for intuitive data understanding
- **User Persona Generation**: Create culturally nuanced agent profiles based on real-world datasets (e.g., Reddit)
- **Comprehensive Logging**: Detailed recording and analysis of each agent's decision-making process and interactions
- **Group Chat Monitoring**: Observe group discussions, opinion formation, and coordination behaviors
- **Modular Architecture**: Clean separation of frontend and backend for easy extension and development

---

## Tech Stack

### Frontend
![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?style=for-the-badge&logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white)
![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)

### Backend
![Node.js](https://img.shields.io/badge/Node.js-43853D?style=for-the-badge&logo=node.js&logoColor=white)
![Express](https://img.shields.io/badge/Express-000000?style=for-the-badge&logo=express&logoColor=white)
![Socket.io](https://img.shields.io/badge/Socket.io-010101?style=for-the-badge&logo=socket.io&logoColor=white)

### Simulation Engine
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-000000?style=for-the-badge&logo=ollama&logoColor=white)

### Tools & Platforms
![Git](https://img.shields.io/badge/Git-F05032?style=for-the-badge&logo=git&logoColor=white)
![GitHub](https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white)

| Category | Technology |
|----------|-----------|
| **Frontend** | React 19, TypeScript, Vite, TailwindCSS, Recharts, Framer Motion |
| **Backend** | Node.js, Express, Socket.io, TypeScript |
| **Simulation Engine** | Python 3.11+, CAMEL-AI, Ollama, Qwen3-8B |
| **Database** | SQLite (built-in with OASIS) |
| **State Management** | Zustand, TanStack Query |
| **UI Components** | Lucide Icons, Sonner |

---

## Performance

| Metric | Ollama (RTX 3060) | OpenRouter (DeepSeek) | Description |
|--------|------------------|----------------------|-------------|
| Qwen3-8B Load Time | 0.26s | <0.1s | Initial model loading |
| OASIS Initialization | 9.75s | 9.75s | Per agent |
| Average Step (Ollama) | 5.87s | - | With local LLM |
| Average Step (OpenRouter) | - | 1-2s | 3-6x faster |
| Timeout Limit | 30s | 30s | Optimized for UX |

---

## Getting Started

### Prerequisites

- **Operating System**: Ubuntu 22.04 LTS (recommended)
- **Hardware**:
  - For Ollama: 4+ core CPU, 8GB+ RAM, 40GB+ storage, GPU with 8GB+ VRAM
  - For OpenRouter: No special hardware required
- **Software**: Node.js 20+, Python 3.11+
- **LLM Backend**:
  - Option 1: Ollama (local, free)
  - Option 2: OpenRouter account (cloud, paid, faster)

### Installation

1. **Clone Repository**
   ```bash
   git clone https://github.com/swjtu-dev-squad/oasis-dashboard.git
   cd oasis-dashboard
   ```

2. **Install Dependencies**
   ```bash
   # Install Node.js dependencies
   pnpm install

   # Install Python dependencies
   uv sync
   ```

3. **Start Local Model Service**
   ```bash
   ollama pull qwen3:8b
   ollama run qwen3:8b
   ```

4. **Configure Environment**

   **Method 1: Using a .env File (Recommended)**

   Copy the example environment file and edit as needed:
   ```bash
   cp .env.example .env
   ```

   The `.env` file comes pre-configured with sensible defaults for local Ollama:
   - `OASIS_MODEL_PLATFORM=ollama`
   - `OASIS_MODEL_TYPE=qwen3:8b`
   - `OASIS_MODEL_URL=http://127.0.0.1:11434/v1`
   - `OASIS_MODEL_CONTEXT_WINDOW=8192`
   - `OASIS_CONTEXT_TOKEN_LIMIT=6144`
   - `OASIS_MODEL_GENERATION_MAX_TOKENS=256`

   The `.env` file is automatically loaded when the backend starts.

   **Method 2: Manual Environment Variables (Alternative)**

   For development or CI/CD, you can export variables manually:
   ```bash
   export OASIS_MODEL_PLATFORM=ollama
   export OASIS_MODEL_TYPE=qwen3:8b
   export OASIS_MODEL_URL=http://127.0.0.1:11434/v1
   export OASIS_MODEL_CONTEXT_WINDOW=8192
   export OASIS_CONTEXT_TOKEN_LIMIT=6144
   export OASIS_MODEL_GENERATION_MAX_TOKENS=256
   ```

   **Note:** Environment variables set manually (Method 2) take precedence over those in `.env`.

   **Configuration Reference:**
   - `OASIS_MODEL_PLATFORM`: Inference backend type. Use `ollama` for local Ollama, `vllm` for OpenAI-compatible vLLM services.
   - `OASIS_MODEL_TYPE`: Model name exposed by the backend, for example `qwen3:8b`.
   - `OASIS_MODEL_URL`: Base URL of the model service. For local Ollama, the recommended value is `http://127.0.0.1:11434/v1`.
   - `OASIS_MODEL_CONTEXT_WINDOW`: Declared model context window. Set this to the actual context length of your deployed model.
   - `OASIS_CONTEXT_TOKEN_LIMIT`: Budget reserved for short-term conversation context. A practical recommendation is to keep it below the full context window to leave room for system prompt and generation.
   - `OASIS_MODEL_GENERATION_MAX_TOKENS`: Maximum tokens for a single model response. A conservative local development value such as `256` is recommended.

   For a detailed explanation of why these settings are explicit in the current architecture, see [OASIS Memory Optimization](docs/OASIS_MEMORY_OPTIMIZATION.md).

5. **Start Development Server**
   ```bash
   pnpm dev
   ```

6. **Build for Production**
   ```bash
   pnpm build
   NODE_ENV=production npx tsx server.ts
   ```

---

## Model Backend Comparison

### Ollama vs OpenRouter

| Feature | Ollama (Local) | OpenRouter (Cloud) |
|---------|---------------|-------------------|
| **Speed** | ~5.87s/step (RTX 3060) | ~1-2s/step (3-6x faster) |
| **Cost** | Free (requires hardware) | ~$0.14/1M tokens (DeepSeek) |
| **Setup** | Install Ollama + GPU | Just get API key |
| **Privacy** | 100% local | Data sent to API |
| **Scalability** | Limited by GPU | Virtually unlimited |
| **Models** | Open source only | 100+ models available |

### When to use each?

**Use Ollama if you:**
- Have a powerful GPU (RTX 3060 or better)
- Need 100% data privacy
- Want zero ongoing costs
- Are running small simulations (< 20 agents)

**Use OpenRouter if you:**
- Need faster execution speed
- Don't have a powerful GPU
- Are running large-scale simulations (50+ agents)
- Want access to diverse models
- Prefer cloud scalability

### OpenRouter Model Recommendations

| Model | Speed | Cost | Quality | Best For |
|-------|-------|------|---------|----------|
| `deepseek/deepseek-chat` | Very Fast | $0.14/1M | Good | Large simulations |
| `google/gemini-flash-1.5` | Very Fast | $0.08/1M | Excellent | Balanced choice |
| `meta-llama/llama-3.1-8b-instruct` | Fast | $0.08/1M | Good | Cost-effective |
| `openai/gpt-4o-mini` | Fast | $0.15/1M | Excellent | Best quality |

**Cost Example**: 100 agents × 50 steps ≈ 2M tokens
- DeepSeek: ~$0.28 total
- GPT-4o-mini: ~$0.30 total
- Ollama: Free (but slower)

---

## Documentation

- **[Installation & Configuration Guide](docs/INSTALL_AND_CONFIG_MANUAL.md)**: Detailed setup instructions
- **[Developer Guide](docs/DEVELOPER_MANUAL.md)**: Code structure, API documentation, and development guidelines
- **[OASIS Architecture](docs/OASIS_AND_ARCHITECTURE.md)**: System architecture and design principles
- **[OASIS Memory Optimization](docs/OASIS_MEMORY_OPTIMIZATION.md)**: Current memory/context optimization architecture, runtime configuration, validation workflow, and future evolution path

---

## Scripts

```bash
# Development
pnpm dev              # Start development server
pnpm dev:log          # Start with logging enabled
pnpm build            # Build for production
pnpm preview          # Preview production build
pnpm lint             # Run TypeScript checks
pnpm clean            # Clean build artifacts
```

---

## Project Status

![Development Status](https://img.shields.io/badge/status-Active%20Development-yellow)
![Environment](https://img.shields.io/badge/environment-Development-orange)
![Deployment](https://img.shields.io/badge/deployment-Not%20Deployed-red)

This project is currently under active development and has not yet been deployed to production environments.

---

## Metrics

![GitHub commit activity](https://img.shields.io/github/commit-activity/t/swjtu-dev-squad/oasis-dashboard)
![GitHub last commit](https://img.shields.io/github/last-commit/swjtu-dev-squad/oasis-dashboard)
![GitHub repo size](https://img.shields.io/github/repo-size/swjtu-dev-squad/oasis-dashboard)

---

## Resources

![CAMEL-AI](https://img.shields.io/badge/CAMEL--AI-OASIS-blue?logo=python)
![Ollama](https://img.shields.io/badge/Ollama-LLM-black?logo=ollama)
![Qwen](https://img.shields.io/badge/Qwen-Model-green)

- **[CAMEL-AI OASIS](https://github.com/camel-ai/oasis)**: Core simulation framework
- **[Ollama](https://ollama.ai)**: Local LLM runtime
- **[Qwen](https://github.com/QwenLM/Qwen)**: Large language model

---

<div align="center">

![Made with](https://img.shields.io/badge/Made%20with-❤️-red)
![Team](https://img.shields.io/badge/Team-SWJTU%20Development%20Squad-blue)

**Built with ❤️ by SWJTU Development Squad**

</div>
