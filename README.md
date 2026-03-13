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

| Metric | Value | Description |
|--------|-------|-------------|
| Qwen3-8B Load Time | 0.26s | Initial model loading |
| OASIS Initialization | 9.75s | Per agent |
| Step 1 Execution | 1.08s | With real LLM calls |
| Step 2-5 Average | 0.14s | With real LLM calls |
| Timeout Limit | 30s | Optimized for UX |

---

## Getting Started

### Prerequisites

- **Operating System**: Ubuntu 22.04 LTS (recommended)
- **Hardware**: 4+ core CPU, 8GB+ RAM, 40GB+ storage
- **Software**: Node.js 20+, Python 3.11+, Ollama

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

3. **Configure Local Model**
   ```bash
   ollama pull qwen3:8b
   ```

4. **Start Development Server**
   ```bash
   pnpm dev
   ```

5. **Build for Production**
   ```bash
   pnpm build
   NODE_ENV=production npx tsx server.ts
   ```

---

## Documentation

- **[Installation & Configuration Guide](docs/INSTALL_AND_CONFIG_MANUAL.md)**: Detailed setup instructions
- **[Developer Guide](docs/DEVELOPER_MANUAL.md)**: Code structure, API documentation, and development guidelines
- **[OASIS Architecture](docs/OASIS_AND_ARCHITECTURE.md)**: System architecture and design principles

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
