"""
app.py — FilePilot AI  |  Streamlit UI

Two tabs:
  🗂️ Organize  — scan + AI-move files without touching the terminal
  💬 Find Files — natural-language chatbot with intent detection

Run with:
  streamlit run app.py          (from the Python_Scripts directory)
"""

from __future__ import annotations

import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import streamlit as st

# ── Local imports ─────────────────────────────────────────────────────────────
# app.py lives in Python_Scripts/ alongside the other modules
sys.path.insert(0, str(Path(__file__).parent))

from database import init_db, list_all_moves, search_files, undo_move
from organizer import (
    ask_llm,
    execute_moves,
    get_file_meta,
    restore_file,
)
from scanner import scan_directory

# ── Persistent history ────────────────────────────────────────────────────────
_HISTORY_PATH = Path.home() / ".cleanslate" / "chat_history.json"
_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)


# ── Native folder picker ──────────────────────────────────────────────────────

def pick_folder() -> str:
    """Open a native OS folder-picker dialog and return the selected path."""
    root = tk.Tk()
    root.withdraw()                      # hide the empty root window
    root.wm_attributes("-topmost", 1)   # bring dialog to front
    folder = filedialog.askdirectory(title="Select folder to organize")
    root.destroy()
    return folder or ""


def load_history() -> list[dict]:
    try:
        return json.loads(_HISTORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_history(messages: list[dict]) -> None:
    try:
        _HISTORY_PATH.write_text(
            json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


# ── Intent detection ──────────────────────────────────────────────────────────
_ORGANIZE_KWORDS = {"organize", "sort", "clean", "tidy", "arrange", "categorize"}
_UNDO_KWORDS = {"undo", "revert", "restore", "reverse", "rollback", "put back", "move back"}
_LIST_KWORDS = {"list", "show all", "everything", "all files", "what did you move", "history"}


def detect_intent(text: str) -> str:
    low = text.lower()
    if any(k in low for k in _UNDO_KWORDS):
        return "undo"
    if any(k in low for k in _ORGANIZE_KWORDS):
        return "organize"
    if any(k in low for k in _LIST_KWORDS):
        return "list"
    return "search"


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FilePilot AI",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .stApp {
        background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
        color: #e6edf3;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background: #161b22;
        border-radius: 10px;
        padding: 4px;
        gap: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        color: #8b949e;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background: #21262d !important;
        color: #58a6ff !important;
    }

    /* Headers */
    h1 { color: #58a6ff; letter-spacing: -0.5px; }
    h2, h3 { color: #79c0ff; }

    /* Cards */
    .result-card {
        background: rgba(33, 38, 45, 0.95);
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 12px;
        transition: border-color 0.2s, box-shadow 0.2s;
    }
    .result-card:hover {
        border-color: #58a6ff;
        box-shadow: 0 0 0 1px #58a6ff22;
    }
    .result-card .filename {
        font-size: 1.05rem;
        font-weight: 700;
        color: #58a6ff;
    }
    .result-card .path {
        font-size: 0.82rem;
        color: #8b949e;
        font-family: monospace;
        margin-top: 4px;
    }
    .result-card .reason {
        font-size: 0.9rem;
        color: #c9d1d9;
        margin-top: 6px;
    }
    .result-card .score-badge {
        display: inline-block;
        background: #238636;
        color: #aff5b4;
        border-radius: 20px;
        padding: 2px 10px;
        font-size: 0.78rem;
        margin-top: 8px;
    }
    .result-card .timestamp {
        font-size: 0.78rem;
        color: #6e7681;
        float: right;
    }

    /* Progress bar */
    .stProgress > div > div > div > div { background: #58a6ff; }

    /* Sidebar */
    section[data-testid="stSidebar"] { background: #0d1117; }

    /* Inputs */
    .stTextInput > div > div > input,
    .stTextArea textarea {
        background: #21262d;
        border: 1px solid #30363d;
        color: #e6edf3;
        border-radius: 8px;
    }

    /* Buttons */
    .stButton > button {
        background: #21262d;
        border: 1px solid #30363d;
        color: #e6edf3;
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.15s;
    }
    .stButton > button:hover {
        border-color: #58a6ff;
        color: #58a6ff;
        background: #161b22;
    }



    /* Universal browse button fix — target by surrounding context */
    .browse-wrapper .stButton > button {
        height: 42px !important;
        min-height: 42px !important;
        max-height: 42px !important;
        border-radius: 8px !important;
        border: 1px solid #58a6ff !important;
        color: #58a6ff !important;
        background: transparent !important;
        font-size: 0.85rem !important;
        font-weight: 500 !important;
        white-space: nowrap !important;
        margin-top: -230px;
        width: 100%;
        padding: 0 12px !important;
        line-height: 42px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    .browse-wrapper .stButton > button:hover {
        background: rgba(88, 166, 255, 0.08) !important;
    }
    /* Remove the extra gap Streamlit injects inside button wrapper */
    .browse-wrapper .stButton {
        margin: 0 !important;
        padding: 0 !important;
    }

    /* Primary button */
    .stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #1f6feb, #388bfd);
        border: none;
        color: white;
        font-weight: 600;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(90deg, #388bfd, #1f6feb);
        color: white;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session state init ────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state["messages"] = load_history()
if "prefill_query" not in st.session_state:
    st.session_state["prefill_query"] = ""
if "org_log" not in st.session_state:
    st.session_state["org_log"] = []   # per-run progress logs


# ── Helpers ───────────────────────────────────────────────────────────────────

def render_result_card(r: dict, show_undo: bool = False, card_key: str = "") -> None:
    """Render a single file-move result card."""
    score = r.get("relevance_score", None)
    ts = r.get("timestamp", "")[:19].replace("T", " ")
    score_html = (
        f'<span class="score-badge">Relevance: {score:.1%}</span>' if score is not None else ""
    )
    st.markdown(
        f"""
        <div class="result-card">
            <span class="filename">📄 {r.get("filename", "Unknown")}</span>
            <span class="timestamp">{ts}</span>
            <div class="path">
                <span style="color:#8b949e;">From:</span> {r.get("original_path", "?")}
                <br>
                <span style="color:#3fb950;">→ To:</span> {r.get("new_path", "?")}
            </div>
            <div class="reason">💬 {r.get("reason", "")}</div>
            {score_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
    if show_undo and r.get("id"):
        if st.button(f"↩ Undo this move", key=f"undo_{card_key}_{r['id']}"):
            ok_disk, msg_disk = restore_file(r)
            ok_db = undo_move(r["id"]) if ok_disk else False
            if ok_disk and ok_db:
                st.success(f"✅ {msg_disk} — record removed from index.")
                st.rerun()
            else:
                st.error(f"❌ {msg_disk}")


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ✈️ FilePilot AI")
    st.markdown("_Privacy-first • Runs 100% locally_")
    st.divider()

    total_count = len(list_all_moves())
    st.metric("Files Indexed", total_count)

    st.divider()
    st.markdown("**💡 Example queries**")
    examples = [
        "Where are my Python scripts?",
        "Find my tax documents",
        "Visa or passport scan",
        "Photos from last year",
        "Budget spreadsheet",
        "Show me everything",
        "Undo last move",
    ]
    for ex in examples:
        if st.button(ex, key=f"ex_{ex}", use_container_width=True):
            st.session_state["prefill_query"] = ex
            st.rerun()  # clean rerun: sidebar button triggers query reliably

    st.divider()
    n_results = st.slider("Max results", min_value=1, max_value=20, value=5)

    if st.button("🗑️ Clear chat history", use_container_width=True):
        st.session_state["messages"] = []
        save_history([])
        st.rerun()


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_org, tab_chat = st.tabs(["🗂️  Organize", "💬  Find Files"])


# ══════════════════════════════════════════════════════════════════
# TAB 1 — ORGANIZE
# ══════════════════════════════════════════════════════════════════
with tab_org:
    st.title("🗂️ Organize a Folder")
    st.markdown(
        "Point the AI at any directory and it will sort your loose files into "
        "labelled subfolders — all locally, no data leaves your machine."
    )
    st.divider()

    # Dry Run toggle — full width above the path row for clarity
    dry_run = st.toggle(
        "Dry Run (preview only)",
        value=True,
        help="When ON, the AI proposes moves but nothing is touched. Toggle OFF to apply moves.",
    )
    st.caption("_Safe by default — uncheck to apply moves._")

    # ── Folder path + Browse button row ───────────────────────────────────────
    st.markdown("**📁 Folder to organize**")
    col_path, col_browse = st.columns([5, 1], vertical_alignment="bottom")

    with col_path:
        folder_path = st.text_input(
            "Folder to organize",
            value=st.session_state.get("picked_folder", ""),
            placeholder=r"e.g. C:\Users\You\Downloads",
            label_visibility="collapsed",
        )
        # Keep picked_folder in sync when user types manually
        st.session_state["picked_folder"] = folder_path

    with col_browse:
        if st.button("Browse", key="browse_btn", use_container_width=True):
            picked = pick_folder()
            if picked:
                st.session_state["picked_folder"] = picked
                st.rerun()


    run_btn = st.button("▶  Organize Now", type="primary", use_container_width=True)

    if run_btn:
        if not folder_path:
            st.warning("Please enter a folder path first.")
        else:
            target = Path(folder_path)
            if not target.exists() or not target.is_dir():
                st.error(f"❌ Path not found or not a directory: `{folder_path}`")
            else:
                # ── Scan ──────────────────────────────────────────────────────
                with st.status("🔍 Scanning directory…", expanded=True) as status:
                    scan = scan_directory(target)
                    st.write(f"Found **{len(scan.loose_files)}** loose file(s) · "
                             f"**{len(scan.existing_folders)}** existing folder(s)")

                    if not scan.loose_files:
                        status.update(label="✅ Nothing to organize!", state="complete")
                        st.success("No loose files found — your folder is already clean! 🎉")
                    else:
                        mode_label = "Dry Run — no files will be moved" if dry_run else "Live Run — files WILL be moved"
                        st.write(f"_Mode: {mode_label}_")

                        # ── LLM loop ──────────────────────────────────────────
                        if dry_run:
                            # Skip Ollama in dry-run, just show scanner results
                            status.update(label=f"📋 Dry run complete — {len(scan.loose_files)} file(s) found", state="complete")
                            import pandas as pd
                            df = pd.DataFrame([
                                {
                                    "File": f.name,
                                    "Extension": f.suffix or "(none)",
                                    "Available Folders": ", ".join(scan.existing_folders) or "—",
                                }
                                for f in scan.loose_files
                            ])
                            st.dataframe(df, use_container_width=True, hide_index=True)
                            st.info("Remove **Dry Run** toggle to let the AI categorize and move files.")
                        else:
                            decisions = []
                            progress_bar = st.progress(0, text="Starting AI categorization…")
                            total = len(scan.loose_files)

                            for i, file_path in enumerate(scan.loose_files):
                                progress_bar.progress(
                                    (i) / total,
                                    text=f"🤖 Analyzing `{file_path.name}` ({i + 1}/{total})…",
                                )
                                meta = get_file_meta(file_path)
                                decision = ask_llm(meta, scan.existing_folders)
                                if decision:
                                    decisions.append((file_path, decision))

                            progress_bar.progress(1.0, text="✅ AI categorization complete!")

                            if not decisions:
                                status.update(label="❌ No decisions made — check Ollama is running.", state="error")
                            else:
                                execute_moves(decisions, target, dry_run=False)
                                status.update(
                                    label=f"✅ Moved {len(decisions)} file(s) successfully!",
                                    state="complete",
                                )
                                # Show results table
                                import pandas as pd
                                df = pd.DataFrame([
                                    {
                                        "File": src.name,
                                        "→ Folder": dec.target_folder,
                                        "Reason": dec.reason,
                                    }
                                    for src, dec in decisions
                                ])
                                st.dataframe(df, use_container_width=True, hide_index=True)
                                st.balloons()
                                st.success(
                                    f"**{len(decisions)} file(s) organized!** "
                                    "Switch to the 💬 Find Files tab to search for them."
                                )
                                import time as _time
                                _time.sleep(2)   # let balloons play before rerun
                                st.rerun()       # refreshes sidebar "Files Indexed" count


# ══════════════════════════════════════════════════════════════════
# TAB 2 — CHATBOT
# ══════════════════════════════════════════════════════════════════
with tab_chat:
    st.title("💬 Find Your Files")
    st.markdown("_Ask me where your files went, list everything, or undo a move._")
    st.divider()

    # ── Chat input ────────────────────────────────────────────────
    prefill = st.session_state.pop("prefill_query", "")
    user_query = st.chat_input(
        "e.g. 'Where did my tax files go?' or 'Show me everything' or 'Undo last move'"
    )
    active_query = prefill if prefill else user_query

    if active_query:
        st.session_state["messages"].append({"role": "user", "content": active_query})
        intent = detect_intent(active_query)

        # ── Intent: ORGANIZE redirect ─────────────────────────────
        if intent == "organize":
            response_text = (
                "Looks like you want to **organize a folder**! 🗂️  \n\n"
                "Switch to the **🗂️ Organize** tab, enter your folder path, and hit ▶ Organize Now. "
                "No terminal needed!"
            )
            response_html = ""
            response_cards = []

        # ── Intent: UNDO ─────────────────────────────────────────
        elif intent == "undo":
            all_moves = list_all_moves()
            recent = all_moves[:5]  # already sorted newest-first
            if recent:
                response_text = (
                    f"Here are the **{len(recent)} most recent move(s)**. "
                    "Each has an ↩ Undo button to restore the file to its original location."
                )
                response_cards = recent
            else:
                response_text = "😕 No moves found in the index yet. Run an organization first!"
                response_cards = []
            response_html = ""

        # ── Intent: LIST ALL ──────────────────────────────────────
        elif intent == "list":
            all_moves = list_all_moves()
            if all_moves:
                response_text = f"Here are all **{len(all_moves)}** indexed file move(s):"
                response_cards = all_moves
            else:
                response_text = (
                    "😕 No files indexed yet.  \n"
                    "Go to the **🗂️ Organize** tab to let the AI sort a folder first."
                )
                response_cards = []
            response_html = ""

        # ── Intent: SEARCH (default) ─────────────────────────────
        else:
            results = search_files(active_query, n_results=n_results)
            if results:
                response_text = f"Found **{len(results)}** file(s) matching your query:"
                response_cards = results
            else:
                response_text = (
                    "😕 No files found for that query.  \n"
                    "Run an organization in the **🗂️ Organize** tab first to index your files."
                )
                response_cards = []
            response_html = ""

        st.session_state["messages"].append(
            {
                "role": "assistant",
                "content": response_text,
                "cards": response_cards if "response_cards" in dir() else [],
                "intent": intent,
            }
        )
        save_history(st.session_state["messages"])

    # ── Render chat history (newest first) ──────────────────────────
    for msg_idx, msg in enumerate(reversed(st.session_state["messages"])):
        real_idx = len(st.session_state["messages"]) - 1 - msg_idx
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant", avatar="🗂️"):
                st.markdown(msg["content"])
                cards = msg.get("cards", [])
                intent = msg.get("intent", "search")
                show_undo_btn = intent in ("undo", "list")
                for card_i, card in enumerate(cards):
                    render_result_card(
                        card,
                        show_undo=show_undo_btn,
                        card_key=f"msg{real_idx}_card{card_i}",
                    )

    # ── Empty state ───────────────────────────────────────────────
    if not st.session_state["messages"]:
        st.markdown(
            """
            <div style="text-align:center; padding: 60px 0; color: #8b949e;">
                <div style="font-size: 4rem;">💬</div>
                <h3 style="color: #58a6ff; margin-top: 12px;">Ask me anything about your files</h3>
                <p>Try: <code>Where are my Python scripts?</code> · <code>Show me everything</code> · <code>Undo last move</code></p>
                <p style="font-size: 0.85rem;">
                    First time? Head to the <strong>🗂️ Organize</strong> tab to let the AI sort a folder.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
