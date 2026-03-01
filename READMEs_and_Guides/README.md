# ✈️ FilePilot AI

> **Privacy-first AI file organizer** — uses a local Llama 3.2 model (via Ollama) to intelligently categorize loose files into folders, then lets you find, restore, and manage them through a plain-English chat interface. Your data never leaves your machine.

---

## ✨ Features

| Feature | Details |
|---|---|
| 🤖 **AI-powered sorting** | Llama 3.2 analyses each file's name, extension & content preview |
| 🖥️ **No-terminal UI** | Organize a folder directly from the Streamlit app — no CLI required |
| 🔍 **Semantic search** | ChromaDB lets you ask "where are my tax docs?" in plain English |
| 🛡️ **Dry-run mode** | Preview all proposed moves before anything is touched |
| ↩️ **Undo moves** | Restore any file back to its original location with one click |
| 💬 **Intent-aware chatbot** | Understands organize / undo / list / search requests automatically |
| 📝 **Persistent chat history** | Conversation survives page refresh (saved to `~/.cleanslate/`) |
| 🚫 **`.aiignore`** | Block sensitive files/folders from being organized |
| 💾 **Portable DB** | Index stored in `~/.cleanslate/chroma/` — survives project moves |
| 🔄 **Collision handling** | Duplicate destinations get a short hash appended automatically |

---

## 🚀 Quick Start

### 1 — Prerequisites

- **Python 3.10+**
- **Ollama** installed → [ollama.com/download](https://ollama.com/download)

```bash
# Pull the required model
ollama pull llama3.2

# Start the server (keep this running in a separate terminal)
ollama serve
```

### 2 — Install dependencies

```bash
cd FilePilot-AI/Python_Scripts
pip install -r ../Requirements/requirements.txt
```

### 3 — Verify environment

```bash
python check_env.py
```

Expected output: three green ✅ checks (Ollama binary, server, model).

---

## 🌐 Streamlit App (Recommended)

The Streamlit app is the primary interface — no terminal commands needed for everyday use.

```bash
cd CleanSlateAI/Python_Scripts
streamlit run app.py
# Open http://localhost:8501
```

### Tab 1 — 🗂️ Organize

1. Enter the **absolute path** of the folder you want to sort.
2. Leave **Dry Run** ON to preview moves without touching any files.
3. Click **▶ Organize Now** — a progress bar shows each file being analyzed.
4. Toggle **Dry Run** OFF and click again to apply the moves.

### Tab 2 — 💬 Find Files

Type anything in plain English. The chatbot detects what you mean:

| What you type | What happens |
|---|---|
| *"Where are my Python scripts?"* | Semantic search of the index |
| *"Show me everything"* / *"List all files"* | All indexed moves displayed as cards |
| *"Undo last move"* / *"Restore my file"* | Last 5 moves shown with ↩ Undo buttons |
| *"Can you organize my folder?"* | Friendly redirect to the Organize tab |

Click any **example query** in the sidebar to prefill the input instantly.

---

## 🖥️ CLI Usage (Advanced)

The CLI is still available for scripting and automation.

### Organize a directory

```bash
# Dry-run: preview proposed moves (no files moved, no Ollama needed)
python main.py organize --path "C:\Users\You\Downloads" --dry-run

# Live run: AI sorts your files and indexes them
python main.py organize --path "C:\Users\You\Downloads"
```

### Search for a file

```bash
python main.py search --query "visa document"
python main.py search --query "Python scripts" --limit 10
```

---

## 📁 Project Structure

```
FilePilot-AI/
├── Python_Scripts/
│   ├── app.py           # Streamlit UI — Organize tab + Find Files chatbot
│   ├── main.py          # Typer CLI — organize & search commands
│   ├── organizer.py     # Ollama LLM reasoning + file mover + restore_file()
│   ├── scanner.py       # pathlib directory scanner + .aiignore
│   ├── database.py      # ChromaDB vector store + search + undo_move()
│   ├── models.py        # Pydantic schemas (MoveDecision, FileRecord)
│   └── check_env.py     # Pre-flight environment checker
├── Requirements/
│   └── requirements.txt
├── READMEs_and_Guides/
│   └── README.md
└── .aiignore            # Template ignore file (copy to target directories)
```

---

## 🛡️ `.aiignore`

Place a `.aiignore` file **in any directory you organize** to prevent FilePilot
from touching specific files or folders:

```
# Ignore all private key files
*.key
*.pem

# Ignore a specific folder
Confidential
```

---

## 🏗️ Data Flow

```
┌──────────────────────────────────┐
│   Streamlit App  (app.py)        │
│                                  │
│  Tab 1: Organize a Folder        │
│    folder path + Dry Run toggle  │
│    ▶ Organize Now button         │
│           │                      │
│           ▼                      │
│  scanner.py → loose files        │
│  organizer.py → ask_llm() x N   │
│  execute_moves() → shutil.move   │
│  database.py → ChromaDB index    │
│                                  │
│  Tab 2: Find Files (chatbot)     │
│    intent detection              │
│    ├─ search → ChromaDB query    │
│    ├─ list   → list_all_moves()  │
│    └─ undo   → restore_file()    │
│               + undo_move()      │
└──────────────────────────────────┘

CLI (main.py) → same organizer.py / database.py pipeline
```

---

## 🗄️ Local Storage

Everything is stored in `~/.cleanslate/`:

```
~/.cleanslate/
├── chroma/            # ChromaDB vector index (file move records)
└── chat_history.json  # Persistent chatbot conversation history
```

Delete this directory to fully reset FilePilot AI.

---

## 📋 Requirements

See `Requirements/requirements.txt`:
- `ollama` — local LLM client
- `chromadb` — vector database
- `pydantic` — data validation
- `typer` — CLI framework
- `streamlit` — web UI
- `rich` — terminal formatting
- `httpx` — HTTP client for env checker

---

## ⚠️ Disclaimer

FilePilot AI **moves files**. Always use Dry Run first on important directories.
The author is not responsible for data loss. Back up important files before organizing.
