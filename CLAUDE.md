# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

The server **must be started from the `backend/` directory** so relative paths (`../docs`, `../frontend`) resolve correctly.

```bash
# Recommended: use the shell script from the project root
bash run.sh

# Or manually:
cd backend && uv run uvicorn app:app --reload --port 8000
```

- Web UI: http://localhost:8000
- API docs: http://localhost:8000/docs
- Always use `uv` to run Python and manage dependencies — never `pip` or `python` directly. `uv` is installed at `~/.local/bin/uv`
- Add dependencies: `uv add <package>` (updates `pyproject.toml` and `uv.lock`)
- Remove dependencies: `uv remove <package>`
- Sync environment: `uv sync`

## Environment

Requires a `.env` file in the project root:
```
ANTHROPIC_API_KEY=sk-ant-...
```

## Architecture

This is a **RAG (Retrieval-Augmented Generation)** chatbot over course text files. The backend is FastAPI; the frontend is plain HTML/CSS/JS with no build step.

### Request flow

```
Browser (script.js)
  └─ POST /api/query
       └─ FastAPI (app.py)
            └─ RAGSystem.query()         ← main orchestrator
                 ├─ SessionManager       ← in-memory conversation history
                 └─ AIGenerator          ← Claude API calls
                      └─ Claude Call #1: decide whether to search
                           └─ ToolManager → CourseSearchTool
                                └─ VectorStore.search() → ChromaDB
                           └─ Claude Call #2: generate final answer using search results
```

### Key design decisions

- **Two Claude calls per query**: the first lets Claude decide whether to invoke the `search_course_content` tool; the second synthesizes the tool results into a final answer.
- **ChromaDB has two collections**: `course_catalog` (course-level metadata for semantic course-name resolution) and `course_content` (chunked lesson text for retrieval).
- **Course name resolution is semantic**: when Claude passes a `course_name` filter, `VectorStore._resolve_course_name()` does a vector search against `course_catalog` to find the best-matching title — partial/fuzzy names work.
- **Documents are loaded at startup** from `docs/*.txt` and skipped if already in ChromaDB (checked by title). To force a reload, call `vector_store.clear_all_data()` or delete `backend/chroma_db/`.
- **Session history is in-memory only** — it resets on server restart. `MAX_HISTORY=2` means the last 2 exchanges (4 messages) are sent as context.

### Document format (`docs/*.txt`)

```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 0: <title>
Lesson Link: <url>
<lesson content...>

Lesson 1: <title>
...
```

The `DocumentProcessor` parses this format and chunks lesson content into ~800-char pieces with 100-char sentence overlap.

### Configuration (`backend/config.py`)

All tuneable values live here: `ANTHROPIC_MODEL`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `MAX_RESULTS`, `MAX_HISTORY`, `CHROMA_PATH`.
