# AI Model Reference — Training Center Management Software

This document explains every AI model used in the stack, what it does, when to use it,
and how to call it from your FastAPI backend.

---

## Model Overview

| Model | Alias | Port | Task | Purpose |
|---|---|---|---|---|
| `Qwen/Qwen2.5-7B-Instruct` | `qwen` | 8000 | Chat / Text generation | Generate SOPs, letters, reports |
| `Qwen/Qwen2.5-VL-7B-Instruct` | `qwen-vision` | 8002 | Vision + OCR | Scan passports, ID cards, PDFs |
| `nomic-ai/nomic-embed-text-v1` | `nomic-embed-text` | 8001 | Embeddings | Semantic search, profile lookup |

All models are accessed through **LiteLLM** on port **4000** using the OpenAI client SDK.

---

## 1. 🪪 Document Scanning & OCR — `qwen-vision`

### What it does
Reads uploaded images (passports, ID cards, student transcripts, fee receipts) and extracts structured information — no traditional OCR pipeline needed.

### When to use it
| Feature | Trigger |
|---|---|
| Student registration | Upload passport/NID → auto-fill name, DOB, nationality, document number |
| Visa application | Upload visa copy → extract visa type, expiry, entry count |
| Certificate verification | Upload academic transcript → extract grades, institution name |
| Receipt scanning | Upload fee receipt → extract amount, date, reference |

### How to call it (Python)
```python
import base64
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:4000/v1",
    api_key="sk-my-super-secret-master-key"
)

# Encode the uploaded image to base64
with open("passport.jpg", "rb") as f:
    image_b64 = base64.b64encode(f.read()).decode()

response = client.chat.completions.create(
    model="qwen-vision",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}
                },
                {
                    "type": "text",
                    "text": """Extract all personal information from this document and return as JSON:
{
  "full_name": "",
  "date_of_birth": "",
  "nationality": "",
  "document_number": "",
  "document_type": "",
  "expiry_date": "",
  "gender": "",
  "place_of_birth": ""
}
Return ONLY the JSON, no extra text."""
                }
            ]
        }
    ],
    max_tokens=512
)

import json
data = json.loads(response.choices[0].message.content)
# → use data to auto-fill the registration form
```

### Tips
- Send images as **base64** (most reliable for local vLLM) or as a public URL
- Ask for **structured JSON output** so you can parse directly into your form fields
- For PDFs: convert each page to an image first (use `pdf2image` Python library), then send page by page
- Set `max_tokens=512` — document extraction responses are short

---

## 2. 📄 Document Generation — `qwen`

### What it does
Generates professional long-form text documents from student profile data. Fast, instruction-tuned, handles structured prompts well.

### When to use it
| Document | How to trigger |
|---|---|
| **Statement of Purpose (SOP)** | Student fills basic info → AI expands into full SOP |
| **Recommendation Letter** | Teacher selects student → AI drafts a professional letter |
| **Offer Letter** | Enrolment confirmed → AI generates a formal offer letter |
| **Course Completion Certificate** | Course finished → AI generates certificate text |
| **Progress Report** | End of term → AI summarises student performance |
| **Visa Support Letter** | Student requests → AI generates embassy support letter |

### How to call it (Python)
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:4000/v1",
    api_key="sk-my-super-secret-master-key"
)

# Example: Generate an SOP
student = {
    "name": "Mohammad Rahman",
    "nationality": "Bangladeshi",
    "course": "English Language Program",
    "target_university": "University of Edinburgh",
    "background": "BSc Computer Science from BUET",
    "work_experience": "2 years software developer at Grameenphone"
}

response = client.chat.completions.create(
    model="qwen",
    messages=[
        {
            "role": "system",
            "content": "You are an expert academic writer specialising in university application documents."
        },
        {
            "role": "user",
            "content": f"""Write a professional Statement of Purpose for:
- Name: {student['name']}
- Nationality: {student['nationality']}
- Applying for: {student['course']} at {student['target_university']}
- Academic background: {student['background']}
- Work experience: {student['work_experience']}

The SOP should be 400-500 words, formal tone, no generic phrases."""
        }
    ],
    max_tokens=1024,
    temperature=0.7
)

sop_text = response.choices[0].message.content
```

### Tips
- Use a **system prompt** to set the tone (formal, academic, official)
- Provide **all relevant student data** in the user message — more context = better output
- Set `temperature=0.7` for natural-sounding text (lower for more factual, higher for creative)
- Use `max_tokens=1024–2048` for full-length documents

---

## 3. 🔍 Semantic Search — `nomic-embed-text`

### What it does
Converts text into numeric vectors (embeddings) so you can find semantically similar content, even when exact words don't match.

### When to use it
| Feature | How it helps |
|---|---|
| **Student profile search** | Search "students from Bangladesh interested in IELTS" without exact keyword match |
| **Duplicate detection** | Find if a student is already registered (fuzzy name + DOB matching) |
| **Similar document retrieval** | "Show me SOPs similar to this one" |
| **FAQ / Knowledge base** | Student asks a question → retrieve the most relevant answer from your docs |

### How to call it (Python)
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:4000/v1",
    api_key="sk-my-super-secret-master-key"
)

response = client.embeddings.create(
    model="embeddings",   # ← alias registered in LiteLLM
    input="Student from Bangladesh looking for IELTS preparation course"
)

vector = response.data[0].embedding  # 768-dimensional float list
# → store in pgvector, or cosine-compare against stored profiles
```

### Tips
- Store embeddings in **pgvector** (already in your database stack) for fast similarity search
- Embed student profiles when they register, re-embed when key fields change
- Use `pgvector`'s `<=>` cosine distance operator for nearest-neighbour search

---

## 4. Starting the Models

```powershell
cd ai-agent-vllm

.\manage.ps1 start all       # start all three models
.\manage.ps1 start vision    # start only the OCR model
.\manage.ps1 start qwen      # start only the chat/generation model
.\manage.ps1 start embed     # start only the embedding model
.\manage.ps1 list            # see all models with use cases
.\manage.ps1 test            # health-check all running endpoints
```

---

## 5. GPU Memory Budget (single GPU)

| Model | GPU Fraction | VRAM (16 GB) | VRAM (24 GB) |
|---|---|---|---|
| `qwen` (chat) | 0.40 | 6.4 GB | 9.6 GB |
| `qwen-vision` (OCR) | 0.45 | 7.2 GB | 10.8 GB |
| `nomic-embed-text` | 0.10 | 1.6 GB | 2.4 GB |
| **Total** | **0.95** | **15.2 GB** | **22.8 GB** |

> ⚠️ Running all three simultaneously requires at least **16 GB VRAM**.
> On a 16 GB card, start `vision` and `embed` for OCR workflows, or `qwen` and `embed` for document generation workflows.
> On 24 GB+, all three run comfortably.

---

## 6. Recommended Architecture (Training Center App)

```
Upload passport/ID image
        │
        ▼
  qwen-vision (:8002)           ← extracts JSON fields from image
        │
        ▼
  Registration form auto-filled  ← your FastAPI backend maps JSON → form
        │
  Student clicks "Generate SOP"
        │
        ▼
  qwen (:8000)                   ← generates the SOP using student data
        │
        ▼
  Embedding created              ← your backend calls nomic-embed-text (:8001)
        │
        ▼
  Stored in pgvector             ← enables future similarity search
```
