# AI Agent - Microservices Architecture

This project has been modularized into 5 independent components. Each component has its own environment variables and `docker-compose.yml` file, allowing you to run, scale, or modify them completely independently.

## 🏗️ Project Structure

```text
.
├── ai-agent-database/  # PostgreSQL + pgvector container (Stores data & API keys)
├── ai-agent-vllm/      # vLLM inference server (chat on :8000, embeddings on :8001)
├── ai-agent-litellm/   # API Gateway for Billing, Rate Limiting & Routing
├── ai-agent-api/       # FastAPI backend logic
└── ai-agent-frontend/  # Vite React User Interface
```



## ⚙️ Prerequisites

- **NVIDIA GPU** with CUDA support (vLLM requires a GPU)
- **NVIDIA Container Toolkit** installed on the host ([installation guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html))
- **Docker** >= 24 with Compose V2
- At least **16 GB VRAM** recommended for running both the chat and embedding models simultaneously

## 🚀 Getting Started

Because the projects are separated, you must start them individually. They communicate securely over your host network via `host.docker.internal`.

### 1. Start the Database
This runs the Postgres vector database on port **5432**.
```bash
cd ai-agent-database
docker compose up -d
```

### 2. Start the vLLM Inference Server

Models are managed via `manage.ps1`. Each model has a **profile name** and can be started independently.

```powershell
cd ../ai-agent-vllm
cp .env.example .env      # configure models & GPU memory split

# Start all models at once
.\manage.ps1 start all

# — or — start individual models
.\manage.ps1 start qwen   # chat model  → port 8000
.\manage.ps1 start embed  # embeddings  → port 8001
```

Other useful commands:
```powershell
.\manage.ps1 list          # show all registered model profiles
.\manage.ps1 status        # show running containers
.\manage.ps1 test          # health-check every model endpoint
.\manage.ps1 logs qwen     # stream logs for a specific model
.\manage.ps1 stop qwen     # stop a specific model
```

#### ➕ Adding a New Model

1. Add its vars to `.env` (copy the TEMPLATE block at the bottom)
2. Add a service block to `docker-compose.yml` (copy the commented TEMPLATE)
3. Add an entry to `manage.ps1`'s `$models` array
4. Add it to `ai-agent-litellm/config.yaml` and `.env` (copy the TEMPLATE blocks there too)
5. Run `.\manage.ps1 start <profile>`

### 3. Start the API Gateway (LiteLLM)
This starts your billing and security proxy on port **4000**. It connects to vLLM to generate text, and to the Database to track API Keys and token spending.
```bash
cd ../ai-agent-litellm
docker compose up -d
```

### 4. Start the Backend API
This builds and runs your FastAPI application on port **8000**.
```bash
cd ../ai-agent-api
docker compose up --build -d
```

### 5. Start the Frontend
This builds and runs your Vite UI on port **5173**.
```bash
cd ../ai-agent-frontend
docker compose up --build -d
```

---

## 🛑 Stopping Services
To stop any specific service, navigate to its respective directory and run:
```bash
docker compose down
```

---

## 🔧 GPU Memory Tuning

Both vLLM containers share the same GPU(s). Adjust the split in `ai-agent-ollama/.env`:

| Variable | Default | Description |
|---|---|---|
| `VLLM_GPU_MEM_UTIL` | `0.65` | GPU fraction for chat model |
| `VLLM_EMBED_GPU_MEM_UTIL` | `0.25` | GPU fraction for embedding model |
| `VLLM_MAX_MODEL_LEN` | `8192` | Max context length (tokens) |

> ⚠️ The sum of both `GPU_MEM_UTIL` values should be ≤ 0.90 to leave headroom for the OS.
