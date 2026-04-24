# AI Agent - Microservices Architecture

This project has been modularized into 4 independent components. Each component has its own environment variables and `docker-compose.yml` file, allowing you to run, scale, or modify them completely independently.

## 🏗️ Project Structure

```text
.
├── ai-agent-database/  # PostgreSQL + pgvector container
├── ai-agent-ollama/    # Local LLM server (pulls qwen2.5:7b & nomic-embed-text)
├── ai-agent-api/       # FastAPI backend logic
└── ai-agent-frontend/  # Vite React User Interface
```

## 🚀 Getting Started

Because the projects are separated, you must start them individually. By default, they are configured to communicate with each other over your host network (e.g., the API reaches the DB via `host.docker.internal:5432`).

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
*(Wait a few minutes on the first run for the models to finish downloading).*

### 3. Start the Backend API
This builds and runs your FastAPI application on port **8000**.
```bash
cd ../ai-agent-api
docker-compose up --build -d
```

### 4. Start the Frontend
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
*Note: Your database data and downloaded LLM models are saved in permanent Docker volumes, so you won't lose your data when shutting down.*
