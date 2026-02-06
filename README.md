# ContextPedia

A knowledge extraction system that crawls GitLab repositories to build a unified source of truth about business logic, data schemas, dependencies, and data flow — designed for AI agents, chat interfaces, and human search.

## 🎯 Purpose

Transform scattered codebases into structured, searchable knowledge that answers:
- "What does this data model look like?"
- "How does data flow through the system?"
- "What are the business rules for X?"
- "What depends on this service?"

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         ContextPedia                             │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────┐    ┌────────────┐    ┌─────────┐    ┌───────────┐  │
│  │ GitLab  │───▶│ Analyzers  │───▶│ Knowledge│───▶│  Query    │  │
│  │ Crawler │    │ & Extract  │    │  Store   │    │  Layer    │  │
│  └─────────┘    └────────────┘    └─────────┘    └───────────┘  │
│                                                                  │
│  Languages: Java, Python, Go, JS/HTML/CSS                        │
│  Output: JSON | Markdown | Vectors | REST API                    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## 📁 Structure

```
contextpedia/
├── src/
│   ├── crawler/        # GitLab API interaction & repo cloning
│   ├── analyzers/      # Language-specific code analysis
│   ├── extractors/     # Schema, dependency, business logic extraction
│   ├── store/          # Knowledge storage & indexing
│   ├── query/          # Search (keyword + semantic)
│   └── api/            # REST API server
├── output/
│   ├── json/           # Structured data for AI agents
│   ├── markdown/       # Human-readable documentation
│   └── vectors/        # Embeddings for semantic search
├── config/             # Configuration files
└── tests/              # Test suites
```

## 🚀 Quick Start

```bash
# 1. Configure GitLab connection
cp config/gitlab.example.yaml config/gitlab.yaml
# Edit with your GitLab URL and token

# 2. Install with all features
pip install -e ".[full]"

# 3. Run full pipeline (pattern-based, fast & free)
contextpedia --full

# OR: Run with LLM extraction (better quality, requires ANTHROPIC_API_KEY)
export ANTHROPIC_API_KEY="sk-ant-..."
contextpedia --full --llm

# 4. Index for semantic search
cpedia-semantic --index ./output/vectors/chunks.json

# 5. Start the API server
cpedia-api --port 8000
```

## 🧠 Extraction Modes

### Pattern-Based (Default)
Fast, free, deterministic. Uses regex/AST parsing per language.
```bash
contextpedia --analyze
```

### LLM-Based (Claude)
Better quality, understands business context, language-agnostic. Requires API key.
```bash
contextpedia --analyze --llm
contextpedia --analyze --llm --llm-model claude-opus-4-20250514  # Best quality
```

| Aspect | Pattern-Based | LLM (Claude) |
|--------|---------------|--------------|
| Speed | ⚡ Fast | 🐢 Slower |
| Cost | Free | ~$0.01-0.10/file |
| Quality | Good for structure | Excellent for meaning |
| Context | Syntax only | Business logic |
| Languages | Need extractor per lang | All languages |
| Caching | N/A | ✅ Cached results |

**Recommendation:** Use `--llm` for initial extraction (cached), pattern-based for updates.

## 🔍 Search Options

### Keyword Search (CLI)
```bash
cpedia-search "user account"
cpedia-search --schema User
cpedia-search --api /users
cpedia-search --service PaymentService
```

### Semantic Search (CLI)
```bash
# Natural language queries
cpedia-semantic "how do we handle user authentication"
cpedia-semantic "payment processing flow" --type service
cpedia-semantic --ask "what entities relate to orders"
```

### REST API
```bash
# Start server
cpedia-api --port 8000

# Endpoints available at http://localhost:8000/docs
```

## 🌐 REST API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/stats` | Knowledge base statistics |
| GET/POST | `/search` | Keyword search |
| GET/POST | `/semantic/search` | Semantic (embedding) search |
| GET/POST | `/ask` | Question answering (RAG context) |
| GET | `/schemas` | List schemas |
| GET | `/schemas/{name}` | Get schema by name |
| GET | `/schemas/{name}/relationships` | Get schema relationships |
| GET | `/services` | List services |
| GET | `/services/{name}` | Get service by name |
| GET | `/services/{name}/dependencies` | Get service dependency graph |
| GET | `/apis` | List API endpoints |
| GET | `/dependencies` | List dependencies |
| GET | `/dependencies/{name}/usage` | Find dependency usage |
| POST | `/semantic/index` | Reindex embeddings |
| GET | `/semantic/stats` | Embedding index stats |

### Example API Usage

```bash
# Keyword search
curl "http://localhost:8000/search?q=user+authentication&limit=10"

# Semantic search
curl "http://localhost:8000/semantic/search?q=how+does+payment+work"

# Get schema details
curl "http://localhost:8000/schemas/User"

# RAG context for AI
curl "http://localhost:8000/ask?q=what+is+the+order+lifecycle"
```

## ⚙️ Configuration

See `config/gitlab.example.yaml` for GitLab settings.

## 🔒 Privacy

This repository is **private**. Do not commit to public repos.
Contains references to internal business logic and infrastructure.

## 📊 Output Formats

### JSON (AI Agents)
Structured, typed data optimized for programmatic consumption.

### Markdown (Humans & AI Chat)
Readable documentation with cross-references and examples.

### Vectors (Semantic Search)
ChromaDB-backed embeddings using `all-MiniLM-L6-v2` for similarity search.

### REST API
Full-featured API for integration with AI agents and applications.
