# AskMe Knowledge Base System

English | [简体中文](./README.md)

A fully localized enterprise knowledge base management system with document parsing, vector storage, semantic search, RAG intelligent Q&A, and department-level access control.

## Features

- **Document Management**: Support PDF, Word, Excel, PPT, TXT, Markdown, images and more
- **Batch Upload**: Multi-file upload with real-time progress display
- **Semantic Search**: Vector similarity-based intelligent retrieval with Chinese semantic understanding
- **RAG Q&A**: AI-powered answers with support for multiple local/cloud LLMs
- **Search Enhancement**: Cross-Encoder reranking and query enhancement for improved accuracy
- **Department Isolation**: Knowledge base isolation by department with department-level search syntax
- **User Authentication**: Local user management with department assignment
- **Internationalization**: Full Chinese/English bilingual support with language switching in settings

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18 + TypeScript + Ant Design + i18next |
| Backend | Python 3.10 + FastAPI |
| Database | SQLite |
| Vector Store | Milvus 2.4 |
| Embedding Model | BAAI/bge-large-zh-v1.5 (1024 dimensions) |
| Reranker Model | BAAI/bge-reranker-base |
| Document Parser | unstructured |
| LLM Support | Ollama / Qwen / GLM / DeepSeek / OpenAI-compatible |

## Quick Start

### 1. Environment Setup

```bash
# Clone the project
git clone https://github.com/devB2433/AskMe.git
cd AskMe

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install backend dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
```

### 2. Start Infrastructure

```bash
# Start Milvus vector database
docker-compose up -d
```

### 3. Start Application

```bash
# Start backend service (port 8001)
cd backend
uvicorn main:app --host 0.0.0.0 --port 8001

# Start frontend service (port 5173)
cd frontend
npm run dev
```

### 4. Access the System

Open browser and visit http://localhost:5173

## Search Syntax

| Syntax | Description |
|--------|-------------|
| `keyword` | Search within current user's department |
| `/department keyword` | Search within specified department |

Examples:
- `security policy` - Search for security policy documents in your department
- `/Engineering API design` - Search for API design documents in Engineering department

## System Settings

### Embedding Model Configuration
- Configure embedding model API endpoint and model name

### Search Precision Configuration
- **Fast Mode**: No reranking, recall size 10
- **Standard Mode**: Reranking enabled, recall size 15
- **Precise Mode**: Reranking + query enhancement, recall size 30

### LLM Integration Configuration
Supported LLM providers:
- **Ollama**: Local deployment, default address `http://localhost:11434`
- **Qwen**: Alibaba Cloud LLM service
- **GLM**: Zhipu AI LLM service
- **DeepSeek**: DeepSeek LLM service
- **OpenAI-compatible**: Any OpenAI-compatible API service

### Language Settings
- Support Chinese/English switching
- Language preference saved to local storage

## Directory Structure

```
AskMe/
├── backend/
│   ├── main.py              # Application entry
│   ├── routes/              # API routes
│   │   ├── document_api.py  # Document upload & management
│   │   ├── search_api.py    # Search endpoints
│   │   ├── user_api.py      # User authentication
│   │   ├── llm_api.py       # LLM configuration API
│   │   └── websocket_api.py # Real-time push
│   ├── services/            # Business services
│   │   ├── embedding_encoder.py  # Vector encoding
│   │   ├── milvus_integration.py # Vector storage
│   │   ├── document_processor.py # Document parsing
│   │   ├── task_queue.py         # Task queue
│   │   ├── reranker.py           # Cross-Encoder reranking
│   │   └── llm_service.py        # LLM service
│   └── data/                # Data storage
├── frontend/
│   └── src/
│       ├── i18n/            # Internationalization
│       │   ├── index.ts     # i18n initialization
│       │   └── locales/     # Language packs
│       │       ├── zh-CN.json
│       │       └── en-US.json
│       └── components/      # React components
│           ├── Login.tsx          # Login page
│           ├── SearchInterface.tsx # Search page
│           ├── DocumentUpload.tsx  # Document upload
│           ├── DocumentList.tsx    # Document management
│           └── Settings.tsx        # System settings
├── docker-compose.yml       # Milvus configuration
└── requirements.txt         # Python dependencies
```

## Configuration

### Chunking
- Chunk size: 400 characters
- Chunk overlap: 100 characters

### Vector Index
- Index type: HNSW
- Similarity metric: COSINE
- Search precision (ef): 256

## Development

```bash
# Run backend development server
cd backend
uvicorn main:app --reload --port 8001

# Run frontend development server
cd frontend
npm run dev
```

## License

MIT License
