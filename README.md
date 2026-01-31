# AI Agent for E-commerce

This project is a middleware AI agent that synchronizes product data from a JSON API to a PostgreSQL database with pgvector, and performs actions like checking stock and creating orders via the client's API.

## Prerequisites

- **Docker and Docker Compose:** Make sure you have Docker and Docker Compose installed on your system.
- **Ollama:** You need to have Ollama running. You can install it from [https://ollama.ai/](https://ollama.ai/).
- **Ollama Models:** Pull the required models by running:
  ```bash
  ollama pull qwen
  ollama pull nomic-embed-text
  ```

## Setup

1. **Start the services:**

   Open a terminal in the project's root directory and run:

   ```bash
   docker compose up -d --build
   ```

   This command will build the backend image and start the `postgres`, `ollama`, and `backend` services.
2. **Check the logs:**

   You can check the logs of the services to make sure they are running correctly:

   ```bash
   docker-compose logs -f
   ```

## Data Synchronization

Before you can interact with the agent, you need to synchronize the product data from the API to the database.

1. **Trigger the synchronization:**

   Send a POST request to the `/sync` endpoint:

   ```bash
   curl -X POST http://localhost:8000/sync
   ```

   This will create the `products` table in the database and populate it with data from the API.

## Interacting with the Agent

You can interact with the agent by sending POST requests to the `/chat` endpoint with a `query` parameter.

**Example 1: Asking a question about a product**

```bash
curl -X POST "http://localhost:8000/chat?query=What%20is%20the%20price%20of%20the%20Mens%20Casual%20Premium%20Slim%20Fit%20T-Shirts%20?"
```

**Example 2: Checking the stock of a product**

```bash
curl -X POST "http://localhost:8000/chat?query=check%20stock%20for%20product%20id%201"
```

**Example 3: Creating an order**

```bash
curl -X POST "http://localhost:8000/chat?query=create%20an%20order%20for%20product%20id%201%20with%20quantity%202%20for%20customer%201234567890%20at%20123%20Main%20St"
```

## Project Structure

```
.
├── app
│   ├── data_sync.py   # Script to sync data from the API to the database
│   └── main.py        # FastAPI application with the agent logic
├── docker-compose.yml # Docker Compose file for the services
├── Dockerfile         # Dockerfile for the backend service
├── requirements.txt   # Python dependencies
└── README.md          # This file
```
