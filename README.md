# AI Agent - Microservices Architecture

This project has been modularized into 5 independent components. Each component has its own environment variables and `docker-compose.yml` file, allowing you to run, scale, or modify them completely independently.

## 🏗️ Project Structure

```text
.
├── ai-agent-database/  # PostgreSQL + pgvector container (Stores data & API keys)
├── ai-agent-ollama/    # Local LLM server (pulls qwen2.5:7b & nomic-embed-text)
├── ai-agent-litellm/   # API Gateway for Billing, Rate Limiting & Routing
├── ai-agent-api/       # FastAPI backend logic
└── ai-agent-frontend/  # Vite React User Interface
```

## 🚀 Getting Started

Because the projects are separated, you must start them individually. They communicate securely over your host network via `host.docker.internal`.

### 1. Start the Database
This runs the Postgres vector database on port **5432**.
```bash
cd ai-agent-database
docker-compose up -d
```

### 2. Start the Local AI (Ollama)
This runs Ollama on port **11434** and automatically pulls your required models.
```bash
cd ../ai-agent-ollama
docker-compose up -d
```

### 3. Start the API Gateway (LiteLLM)
This starts your billing and security proxy on port **4000**. It connects to Ollama to generate text, and to the Database to track API Keys and token spending.
```bash
cd ../ai-agent-litellm
docker-compose up -d
```

### 4. Start the Backend API
This builds and runs your FastAPI application on port **8000**.
```bash
cd ../ai-agent-api
docker-compose up --build -d
```

### 5. Start the Frontend
This builds and runs your Vite UI on port **5173**.
```bash
cd ../ai-agent-frontend
docker-compose up --build -d
```

---

## 🛑 Stopping Services
To stop any specific service, navigate to its respective directory and run:
```bash
docker-compose down
```
