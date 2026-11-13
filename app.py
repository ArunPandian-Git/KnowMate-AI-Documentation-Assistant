"""
KnowMate AI — Premium Documentation Intelligence Workspace
Single-file Streamlit application.

Core pipeline:
Upload -> Extract -> Chunk -> Embed -> ChromaDB -> Retrieve -> Groq -> Cited answer

Secrets:
  GROQ_API_KEY = "your-key"
Optional environment variables:
  GROQ_MODEL=llama-3.3-70b-versatile
  EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
  CHROMA_PATH=./chroma_db
"""

from __future__ import annotations

import hashlib
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import chromadb
import streamlit as st
from groq import Groq
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

try:
    from docx import Document as DocxDocument
except Exception:
    DocxDocument = None


# ---------------------------------------------------------------------
# 01. APP CONFIGURATION
# ---------------------------------------------------------------------
APP_NAME = "KnowMate AI"
APP_VERSION = "3.0 Premium"
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
COLLECTION_NAME = "knowmate_documents"
MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "30"))
SUPPORTED_TYPES = ["pdf", "docx", "txt", "md"]

st.set_page_config(
    page_title=f"{APP_NAME} | Documentation Intelligence",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------
# 02. PREMIUM DESIGN SYSTEM
# ---------------------------------------------------------------------
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600;700;800&family=Manrope:wght@400;500;600;700;800&display=swap');
:root {
  --bg:#080d18; --panel:#101827; --panel2:#141f31; --line:rgba(148,163,184,.16);
  --text:#edf3ff; --muted:#91a0b8; --cyan:#55d6d0; --blue:#729cff;
  --green:#65dfaa; --amber:#f6c66b; --red:#ff7d8d;
}
html, body, [class*="css"] {font-family:'DM Sans',sans-serif;}
.stApp {background:
 radial-gradient(ellipse at 12% 0%, rgba(50,112,174,.17), transparent 34%),
 radial-gradient(ellipse at 92% 8%, rgba(50,190,175,.10), transparent 28%),
 var(--bg); color:var(--text);}
.block-container {max-width:1500px; padding-top:1.5rem; padding-bottom:3rem;}
[data-testid="stSidebar"] {background:#0b1220; border-right:1px solid var(--line);}
[data-testid="stSidebar"] * {color:var(--text);}
h1,h2,h3 {font-family:'Manrope',sans-serif; letter-spacing:-.035em;}
h1 {font-weight:800;}
p, label, .stMarkdown {color:var(--text);}
small,.muted {color:var(--muted)!important;}
div[data-testid="stMetric"] {background:linear-gradient(145deg,#142238,#101827);
 border:1px solid var(--line); padding:18px 20px; border-radius:18px;}
div[data-testid="stMetricLabel"] {color:var(--muted);}
div[data-testid="stMetricValue"] {color:var(--text);font-family:'Manrope';}
.stButton>button,.stDownloadButton>button {border-radius:11px; border:1px solid rgba(85,214,208,.32);
 background:linear-gradient(110deg,#1b8d91,#356bb4); color:white; font-weight:700;
 min-height:2.7rem; transition:all .2s ease;}
.stButton>button:hover,.stDownloadButton>button:hover {border-color:var(--cyan);
 transform:translateY(-1px); color:white;}
.stTextInput input,.stTextArea textarea,.stSelectbox div[data-baseweb="select"],
.stNumberInput input {background:#111c2d!important; color:var(--text)!important;
 border-color:var(--line)!important; border-radius:10px!important;}
[data-testid="stFileUploader"] {background:rgba(17,28,45,.75);border:1px dashed rgba(85,214,208,.4);
 border-radius:16px;padding:12px;}
[data-testid="stChatMessage"] {background:rgba(17,28,45,.75);border:1px solid var(--line);
 border-radius:16px;padding:14px 16px;margin-bottom:12px;}
hr {border-color:var(--line);}
.km-brand {display:flex;align-items:center;gap:12px;margin:4px 0 24px;}
.km-mark {width:42px;height:42px;border-radius:13px;display:grid;place-items:center;
 background:linear-gradient(135deg,#2ab6ae,#426de0);font-size:22px;box-shadow:0 8px 28px #1c9c9c33;}
.km-name {font-family:'Manrope';font-weight:800;font-size:19px;line-height:1.1;color:#f4f8ff;}
.km-sub {font:10px 'DM Mono';letter-spacing:.17em;color:#8fa2bc;margin-top:5px;}
.hero {padding:30px 32px;border:1px solid var(--line);border-radius:24px;
 background:linear-gradient(115deg,rgba(24,48,75,.94),rgba(15,30,48,.92));
 position:relative;overflow:hidden;margin-bottom:22px;}
.hero:after {content:"";position:absolute;width:290px;height:290px;border-radius:50%;
 right:-80px;top:-140px;border:1px solid #55d6d022;box-shadow:0 0 0 30px #55d6d00b,0 0 0 65px #55d6d008;}
.eyebrow {font:11px 'DM Mono';letter-spacing:.18em;text-transform:uppercase;color:var(--cyan);}
.hero h1 {font-size:clamp(30px,4vw,48px);line-height:1.06;margin:12px 0;}
.hero p {max-width:720px;color:#b3c2d8;font-size:15px;line-height:1.7;margin-bottom:0;}
.section-head {display:flex;align-items:center;gap:10px;margin:24px 0 12px;}
.section-head span {font:11px 'DM Mono';color:var(--cyan);letter-spacing:.12em;}
.panel {background:linear-gradient(145deg,rgba(20,31,49,.96),rgba(14,23,37,.96));
 border:1px solid var(--line);border-radius:18px;padding:20px;}
.panel-title {font-family:'Manrope';font-weight:800;font-size:16px;color:#eef4ff;}
.panel-copy {color:var(--muted);font-size:13px;line-height:1.6;}
.pill {display:inline-block;padding:5px 9px;border-radius:30px;font:10px 'DM Mono';
 letter-spacing:.08em;background:#163c40;color:#83e9df;border:1px solid #2b7774;}
.status-dot {display:inline-block;width:8px;height:8px;border-radius:50%;
 background:#65dfaa;box-shadow:0 0 12px #65dfaa;margin-right:7px;}
.source-card {border:1px solid var(--line);border-radius:12px;padding:12px 14px;
 background:#101b2b;margin:8px 0;}
.source-meta {font:10px 'DM Mono';color:var(--cyan);letter-spacing:.08em;}
.source-text {font-size:12px;color:#b4c1d4;line-height:1.55;margin-top:7px;}
div[data-testid="stExpander"] {border:1px solid var(--line);border-radius:13px;background:#101827;}
footer {visibility:hidden;}
#MainMenu {visibility:hidden;}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------
# 03. SESSION STATE
# ---------------------------------------------------------------------
DEFAULTS = {
    "page": "Overview",
    "messages": [],
    "last_sources": [],
    "last_retrieval": [],
    "indexed_docs": [],
    "last_answer_time": None,
}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


def html_card(title: str, body: str, tag: str = "") -> None:
    tag_html = f'<span class="pill">{tag}</span>' if tag else ""
    st.markdown(
        f'<div class="panel"><div style="display:flex;justify-content:space-between;gap:12px">'
        f'<div class="panel-title">{title}</div>{tag_html}</div>'
        f'<div class="panel-copy" style="margin-top:9px">{body}</div></div>',
        unsafe_allow_html=True,
    )


def section(label: str, title: str) -> None:
    st.markdown(
        f'<div class="section-head"><span>{label}</span><h3 style="margin:0">{title}</h3></div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------
# 04. API + VECTOR DATABASE
# ---------------------------------------------------------------------
def get_api_key() -> str:
    try:
        value = st.secrets.get("GROQ_API_KEY", "")
        if value:
            return str(value).strip()
    except Exception:
        pass
    return os.getenv("GROQ_API_KEY", "").strip()


@st.cache_resource(show_spinner="Loading semantic embedding engine…")
def load_embedding_model(model_name: str) -> SentenceTransformer:
    return SentenceTransformer(model_name, device="cpu")


@st.cache_resource(show_spinner=False)
def get_chroma_collection(path: str, name: str):
    Path(path).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=path)
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def get_collection():
    return get_chroma_collection(CHROMA_PATH, COLLECTION_NAME)


def get_groq_client():
    key = get_api_key()
    if not key:
        return None
    return Groq(api_key=key)


# ---------------------------------------------------------------------
# 05. DOCUMENT EXTRACTION + CHUNKING
# ---------------------------------------------------------------------
def extract_file(uploaded_file) -> list[dict[str, Any]]:
    name = uploaded_file.name
    suffix = Path(name).suffix.lower()
    raw = uploaded_file.getvalue()
    records: list[dict[str, Any]] = []

    if suffix == ".pdf":
        reader = PdfReader(__import__("io").BytesIO(raw))
        for page_no, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            text = clean_text(text)
            if text:
                records.append({"text": text, "page": page_no})
    elif suffix == ".docx":
        if DocxDocument is None:
            raise RuntimeError("DOCX support is unavailable. Install python-docx.")
        import io
        doc = DocxDocument(io.BytesIO(raw))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        for i, text in enumerate(paragraphs, start=1):
            records.append({"text": clean_text(text), "page": i})
        for table_index, table in enumerate(doc.tables, start=1):
            table_text = "\n".join(
                " | ".join(cell.text.strip() for cell in row.cells)
                for row in table.rows
            )
            if table_text.strip():
                records.append({"text": clean_text(table_text), "page": f"table-{table_index}"})
    elif suffix in (".txt", ".md"):
        text = clean_text(raw.decode("utf-8", errors="ignore"))
        if text:
            records.append({"text": text, "page": 1})
    else:
        raise ValueError(f"Unsupported format: {suffix}")

    if not records:
        raise ValueError(
            "No extractable text was found. If this is a scanned PDF, OCR is required."
        )
    return records


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int = 1100, overlap: int = 180) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    # Split at paragraph/sentence boundaries before applying overlap.
    units = re.split(r"(?<=[.!?])\s+|\n{1,}", text)
    chunks, current = [], ""
    for unit in units:
        unit = unit.strip()
        if not unit:
            continue
        if len(current) + len(unit) + 1 <= chunk_size:
            current = f"{current} {unit}".strip()
        else:
            if current:
                chunks.append(current)
            tail = current[-overlap:] if overlap and current else ""
            current = f"{tail} {unit}".strip()
            while len(current) > chunk_size:
                chunks.append(current[:chunk_size].strip())
                current = current[chunk_size - overlap :].strip()
    if current:
        chunks.append(current)
    return [c for c in chunks if len(c) > 30]


def ingest_document(uploaded_file, chunk_size: int, overlap: int) -> dict[str, Any]:
    raw = uploaded_file.getvalue()
    if len(raw) > MAX_FILE_MB * 1024 * 1024:
        raise ValueError(f"{uploaded_file.name} exceeds the {MAX_FILE_MB} MB limit.")

    doc_id = hashlib.sha256(raw).hexdigest()
    pages = extract_file(uploaded_file)
    texts, metadatas, ids = [], [], []

    for record in pages:
        page_chunks = chunk_text(record["text"], chunk_size, overlap)
        for chunk in page_chunks:
            idx = len(texts)
            texts.append(chunk)
            metadatas.append({
                "source": uploaded_file.name,
                "page": str(record["page"]),
                "doc_id": doc_id,
                "chunk_index": idx,
                "uploaded_at": datetime.now().isoformat(timespec="seconds"),
            })
            ids.append(f"{doc_id}_{idx}")

    if not texts:
        raise ValueError("The document did not produce any indexable text chunks.")

    model = load_embedding_model(EMBEDDING_MODEL)
    embeddings = model.encode(
        texts, normalize_embeddings=True, show_progress_bar=False,
        batch_size=32
    ).tolist()

    collection = get_collection()
    # Re-uploading the same file replaces its earlier vectors.
    try:
        collection.delete(where={"doc_id": doc_id})
    except Exception:
        pass

    batch_size = 128
    for start in range(0, len(texts), batch_size):
        end = start + batch_size
        collection.add(
            ids=ids[start:end],
            documents=texts[start:end],
            metadatas=metadatas[start:end],
            embeddings=embeddings[start:end],
        )

    return {
        "name": uploaded_file.name,
        "doc_id": doc_id,
        "chunks": len(texts),
        "pages": len(pages),
        "characters": sum(len(x) for x in texts),
    }


# ---------------------------------------------------------------------
# 06. RETRIEVAL + GROUNDED ANSWER GENERATION
# ---------------------------------------------------------------------
def retrieve(question: str, top_k: int, min_similarity: float) -> list[dict[str, Any]]:
    collection = get_collection()
    if collection.count() == 0:
        return []

    model = load_embedding_model(EMBEDDING_MODEL)
    query_vector = model.encode(
        [question], normalize_embeddings=True, show_progress_bar=False
    )[0].tolist()

    result = collection.query(
        query_embeddings=[query_vector],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    items = []
    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    for text, meta, distance in zip(docs, metas, distances):
        similarity = max(0.0, min(1.0, 1.0 - float(distance)))
        if similarity >= min_similarity:
            items.append({
                "text": text,
                "metadata": meta or {},
                "similarity": similarity,
            })
    return items


def generate_answer(question: str, sources: list[dict[str, Any]], history: list[dict]):
    client = get_groq_client()
    if client is None:
        raise RuntimeError(
            "Groq API key is missing. Add GROQ_API_KEY in Streamlit Secrets."
        )
    if not sources:
        return (
            "I couldn't find sufficiently relevant information in the indexed "
            "documents to answer that reliably. Try rephrasing the question or "
            "uploading the relevant documentation."
        )

    context_blocks = []
    for i, item in enumerate(sources, start=1):
        meta = item["metadata"]
        context_blocks.append(
            f"[SOURCE {i} | FILE: {meta.get('source','Unknown')} | "
            f"PAGE/SECTION: {meta.get('page','?')}]\n{item['text']}"
        )
    context = "\n\n".join(context_blocks)

    recent_history = history[-6:]
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content'][:1200]}" for m in recent_history
    )

    system_prompt = """You are KnowMate AI, a precise documentation intelligence assistant.
Answer using ONLY the supplied source context. Do not invent facts, page numbers,
quotes, specifications, or procedures. If the context is insufficient, say so
clearly and ask a focused follow-up. Cite factual claims with [1], [2], etc.,
matching the numbered source blocks. Distinguish direct evidence from reasonable
interpretation. Use clear headings and concise explanations. Never claim that a
source says something it does not say."""
    user_prompt = f"""DOCUMENT CONTEXT
{context}

RECENT CONVERSATION
{history_text or "(No earlier conversation)"}

QUESTION
{question}

Write a useful, structured answer with inline source citations such as [1].
If the documents do not contain the answer, state that explicitly."""
    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.15,
        max_tokens=1800,
    )
    return completion.choices[0].message.content or "No answer was returned."


# ---------------------------------------------------------------------
# 07. DOCUMENT MANAGEMENT
# ---------------------------------------------------------------------
def list_documents() -> list[dict[str, Any]]:
    collection = get_collection()
    if collection.count() == 0:
        return []
    data = collection.get(include=["metadatas"])
    unique = {}
    for meta in data.get("metadatas") or []:
        if not meta:
            continue
        doc_id = meta.get("doc_id", "")
        if doc_id not in unique:
            unique[doc_id] = {
                "name": meta.get("source", "Unknown"),
                "doc_id": doc_id,
                "uploaded_at": meta.get("uploaded_at", ""),
                "chunks": 0,
            }
        unique[doc_id]["chunks"] += 1
    return sorted(unique.values(), key=lambda x: x["name"].lower())


def delete_document(doc_id: str) -> None:
    get_collection().delete(where={"doc_id": doc_id})


# ---------------------------------------------------------------------
# 08. SIDEBAR NAVIGATION
# ---------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        '<div class="km-brand"><div class="km-mark">🧠</div><div>'
        '<div class="km-name">KnowMate AI</div>'
        '<div class="km-sub">DOCUMENT INTELLIGENCE</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<span class="pill">3.0 PREMIUM</span>', unsafe_allow_html=True)
    st.markdown("")
    page = st.radio(
        "WORKSPACE",
        ["Overview", "Knowledge Library", "AI Workspace", "Analytics", "Settings"],
        label_visibility="visible",
    )
    st.session_state.page = page
    st.divider()
    try:
        doc_count = len(list_documents())
        chunk_count = get_collection().count()
        db_ok = True
    except Exception:
        doc_count, chunk_count, db_ok = 0, 0, False
    st.markdown("**SYSTEM HEALTH**")
    st.markdown(
        f'<div class="panel-copy"><span class="status-dot"></span>'
        f'{"VECTOR STORE READY" if db_ok else "VECTOR STORE ERROR"}<br><br>'
        f'<span style="color:#91a0b8">Documents</span> <b>{doc_count}</b><br>'
        f'<span style="color:#91a0b8">Indexed chunks</span> <b>{chunk_count}</b></div>',
        unsafe_allow_html=True,
    )
    st.caption(f"{APP_NAME} · {APP_VERSION}")
    st.caption("Grounded answers. Traceable sources.")


# ---------------------------------------------------------------------
# 09. OVERVIEW
# ---------------------------------------------------------------------
if page == "Overview":
    st.markdown(
        '<div class="hero"><div class="eyebrow">KNOWLEDGE, CONNECTED</div>'
        '<h1>Your documents.<br>One intelligent workspace.</h1>'
        '<p>Turn scattered documentation into a searchable knowledge system. '
        'Upload trusted sources, build a semantic index, and ask questions with '
        'evidence-linked answers.</p><div style="margin-top:20px">'
        '<span class="pill">RAG-POWERED</span> &nbsp; '
        '<span class="pill">SOURCE-AWARE</span> &nbsp; '
        '<span class="pill">PRIVATE WORKSPACE</span></div></div>',
        unsafe_allow_html=True,
    )
    docs = list_documents()
    chunks = get_collection().count()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("DOCUMENTS INDEXED", len(docs))
    c2.metric("KNOWLEDGE CHUNKS", f"{chunks:,}")
    c3.metric("EMBEDDING ENGINE", "MiniLM")
    c4.metric("AI PROVIDER", "Groq")
    section("01 / INGEST", "Build your knowledge base")
    left, right = st.columns([1.35, 1])
    with left:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown("**Add documentation**")
        st.caption("Upload PDF, DOCX, TXT, or Markdown files. Multiple files are supported.")
        uploads = st.file_uploader(
            "Choose source documents",
            type=SUPPORTED_TYPES,
            accept_multiple_files=True,
            key="overview_upload",
        )
        a, b = st.columns(2)
        with a:
            chunk_size = st.select_slider(
                "Chunk size", options=[600, 800, 1000, 1100, 1300, 1600],
                value=1100, key="overview_chunk",
            )
        with b:
            overlap = st.select_slider(
                "Overlap", options=[80, 120, 180, 220, 260, 300],
                value=180, key="overview_overlap",
            )
        if st.button("⚡ Process & index documents", use_container_width=True, disabled=not uploads):
            progress = st.progress(0, text="Preparing ingestion pipeline…")
            successes, errors = [], []
            for i, file in enumerate(uploads):
                try:
                    result = ingest_document(file, chunk_size, overlap)
                    successes.append(result)
                except Exception as exc:
                    errors.append(f"{file.name}: {exc}")
                progress.progress((i + 1) / len(uploads), text=f"Processed {i+1}/{len(uploads)}")
            progress.empty()
            for item in successes:
                st.success(f"Indexed {item['name']} · {item['chunks']} chunks")
            for error in errors:
                st.error(error)
            if successes:
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        html_card(
            "01 · Extract", "Read text from supported documents and preserve page or section metadata.",
            "PARSER",
        )
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        html_card(
            "02 · Understand", "Create semantic embeddings locally with Sentence Transformers.",
            "EMBEDDINGS",
        )
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        html_card(
            "03 · Retrieve", "Find relevant passages in ChromaDB before asking the language model.",
            "VECTOR SEARCH",
        )
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        html_card(
            "04 · Respond", "Generate answers grounded in retrieved passages with source references.",
            "GROUNDED AI",
        )
    section("02 / EXPLORE", "Your indexed library")
    if docs:
        st.dataframe(
            [{"Document": d["name"], "Chunks": d["chunks"], "Document ID": d["doc_id"][:12]}
             for d in docs],
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("Your library is empty. Upload a document to create your first searchable knowledge base.")


# ---------------------------------------------------------------------
# 10. KNOWLEDGE LIBRARY
# ---------------------------------------------------------------------
elif page == "Knowledge Library":
    st.markdown(
        '<div class="eyebrow">KNOWLEDGE MANAGEMENT</div><h1>Knowledge Library</h1>'
        '<p class="panel-copy">Manage indexed sources and inspect the material powering your answers.</p>',
        unsafe_allow_html=True,
    )
    docs = list_documents()
    st.metric("Total indexed sources", len(docs))
    if not docs:
        st.info("No documents indexed yet. Visit Overview to upload your first source.")
    else:
        query = st.text_input("⌕ Search library by filename", placeholder="Filter documents…")
        visible = [d for d in docs if query.lower() in d["name"].lower()]
        for d in visible:
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 1, 1])
                col1.markdown(f"**📄 {d['name']}**")
                col1.caption(f"ID · {d['doc_id'][:18]}…")
                col2.metric("Chunks", d["chunks"])
                if col3.button("Delete", key=f"delete_{d['doc_id']}"):
                    delete_document(d["doc_id"])
                    st.success(f"Removed {d['name']}")
                    st.rerun()
        with st.expander("Inspect indexed passages"):
            collection = get_collection()
            preview = collection.get(
                limit=20, include=["documents", "metadatas"]
            )
            for i, (txt, meta) in enumerate(zip(
                preview.get("documents") or [], preview.get("metadatas") or []
            ), 1):
                st.markdown(
                    f'<div class="source-card"><div class="source-meta">'
                    f'{i:02d} · {meta.get("source","Unknown")} · '
                    f'PAGE {meta.get("page","?")}</div>'
                    f'<div class="source-text">{txt[:700]}</div></div>',
                    unsafe_allow_html=True,
                )


# ---------------------------------------------------------------------
# 11. AI WORKSPACE
# ---------------------------------------------------------------------
elif page == "AI Workspace":
    st.markdown(
        '<div class="eyebrow">ASK YOUR KNOWLEDGE BASE</div><h1>AI Workspace</h1>'
        '<p class="panel-copy">Ask questions, compare concepts, and trace each answer to its source passages.</p>',
        unsafe_allow_html=True,
    )
    with st.sidebar:
        st.markdown("### Retrieval controls")
        top_k = st.slider("Source passages", 2, 12, 5)
        min_similarity = st.slider("Minimum similarity", 0.0, 0.85, 0.15, 0.05)
        st.caption("Higher similarity thresholds are stricter and may return fewer passages.")
        if st.button("＋ New conversation", use_container_width=True):
            st.session_state.messages = []
            st.session_state.last_sources = []
            st.session_state.last_retrieval = []
            st.rerun()

    if get_collection().count() == 0:
        st.warning("Your knowledge base is empty. Upload and index documents before asking questions.")
    else:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                if message.get("sources") and message["role"] == "assistant":
                    with st.expander(f"Evidence · {len(message['sources'])} retrieved passages"):
                        for i, source in enumerate(message["sources"], 1):
                            meta = source["metadata"]
                            st.markdown(
                                f'<div class="source-card"><div class="source-meta">'
                                f'[{i}] {meta.get("source","Unknown")} · '
                                f'PAGE {meta.get("page","?")} · '
                                f'{source["similarity"]:.0%} MATCH</div>'
                                f'<div class="source-text">{source["text"][:900]}</div></div>',
                                unsafe_allow_html=True,
                            )

        prompt = st.chat_input("Ask a question about your documents…")
        if prompt:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                with st.spinner("Retrieving evidence and composing a grounded response…"):
                    started = time.time()
                    try:
                        history = st.session_state.messages[:-1]
                        found = retrieve(prompt, top_k, min_similarity)
                        answer = generate_answer(prompt, found, history)
                        elapsed = time.time() - started
                        st.markdown(answer)
                        st.caption(f"Completed in {elapsed:.2f}s · {len(found)} evidence passages")
                        if found:
                            with st.expander(f"Evidence inspector · {len(found)} passages"):
                                for i, source in enumerate(found, 1):
                                    meta = source["metadata"]
                                    st.markdown(
                                        f'<div class="source-card"><div class="source-meta">'
                                        f'[{i}] {meta.get("source","Unknown")} · '
                                        f'PAGE {meta.get("page","?")} · '
                                        f'{source["similarity"]:.0%} MATCH</div>'
                                        f'<div class="source-text">{source["text"][:900]}</div></div>',
                                        unsafe_allow_html=True,
                                    )
                        st.session_state.messages.append({
                            "role": "assistant", "content": answer, "sources": found
                        })
                        st.session_state.last_sources = found
                        st.session_state.last_retrieval = found
                        st.session_state.last_answer_time = elapsed
                    except Exception as exc:
                        error_text = f"**The request could not be completed.**\n\n`{exc}`"
                        st.error(error_text)
                        st.session_state.messages.append({
                            "role": "assistant", "content": error_text, "sources": []
                        })


# ---------------------------------------------------------------------
# 12. ANALYTICS
# ---------------------------------------------------------------------
elif page == "Analytics":
    st.markdown(
        '<div class="eyebrow">OBSERVABILITY</div><h1>Workspace Analytics</h1>'
        '<p class="panel-copy">A transparent view of the current local vector index and session activity.</p>',
        unsafe_allow_html=True,
    )
    docs = list_documents()
    collection = get_collection()
    count = collection.count()
    a, b, c = st.columns(3)
    a.metric("Indexed documents", len(docs))
    b.metric("Stored chunks", f"{count:,}")
    c.metric("Session messages", len(st.session_state.messages))
    section("01 / INDEX", "Knowledge base composition")
    if docs:
        import pandas as pd
        df = pd.DataFrame([{"Document": d["name"], "Chunks": d["chunks"]} for d in docs])
        st.bar_chart(df.set_index("Document"))
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No indexed data to visualize.")
    section("02 / RETRIEVAL", "Latest evidence trace")
    latest = st.session_state.last_retrieval
    if latest:
        for i, item in enumerate(latest, 1):
            meta = item["metadata"]
            st.markdown(
                f"**[{i}] {meta.get('source','Unknown')} · page {meta.get('page','?')}**"
            )
            st.progress(item["similarity"], text=f"Similarity signal: {item['similarity']:.1%}")
            st.caption(item["text"][:400])
    else:
        st.caption("Ask a question in AI Workspace to populate the retrieval trace.")


# ---------------------------------------------------------------------
# 13. SETTINGS + DIAGNOSTICS
# ---------------------------------------------------------------------
elif page == "Settings":
    st.markdown(
        '<div class="eyebrow">CONFIGURATION & DIAGNOSTICS</div><h1>Settings</h1>'
        '<p class="panel-copy">Review runtime configuration and integration readiness.</p>',
        unsafe_allow_html=True,
    )
    key_ready = bool(get_api_key())
    try:
        collection = get_collection()
        chroma_ready = True
        chunk_count = collection.count()
    except Exception as exc:
        chroma_ready = False
        chunk_count = 0
        chroma_error = str(exc)
    c1, c2, c3 = st.columns(3)
    c1.metric("Groq API", "Connected" if key_ready else "Key missing")
    c2.metric("ChromaDB", "Ready" if chroma_ready else "Error")
    c3.metric("Vector records", f"{chunk_count:,}")
    section("01 / RUNTIME", "Active configuration")
    st.code(
        f"Application : {APP_NAME} {APP_VERSION}\n"
        f"LLM provider : Groq\n"
        f"LLM model : {GROQ_MODEL}\n"
        f"Embedding model : {EMBEDDING_MODEL}\n"
        f"Vector database : ChromaDB\n"
        f"Database path : {CHROMA_PATH}\n"
        f"Collection : {COLLECTION_NAME}\n"
        f"Maximum upload : {MAX_FILE_MB} MB",
        language="text",
    )
    if not key_ready:
        st.error("GROQ_API_KEY is not configured. Add it to Streamlit Secrets.")
        st.markdown(
            "In Streamlit Cloud, open **App settings → Secrets** and add:\n\n"
            '```toml\nGROQ_API_KEY = "your_groq_api_key"\n```'
        )
    else:
        st.success("Groq API key detected. The key is never displayed in the interface.")
    if not chroma_ready:
        st.error(f"ChromaDB diagnostic: {chroma_error}")
    st.warning(
        "Deployment note: Streamlit Community Cloud local storage may be ephemeral. "
        "For durable multi-user production storage, connect a managed vector database "
        "or persistent volume. Do not commit API keys or private documents to GitHub."
    )
    with st.expander("Clear current chat session"):
        st.caption("This clears the conversation only. Indexed documents remain in ChromaDB.")
        if st.button("Clear conversation history"):
            st.session_state.messages = []
            st.session_state.last_sources = []
            st.session_state.last_retrieval = []
            st.success("Conversation cleared.")
            st.rerun()

# ---------------------------------------------------------------------
# 14. FOOTER
# ---------------------------------------------------------------------
st.markdown(
    "<hr><div style='display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;"
    "color:#71829d;font:10px DM Mono;letter-spacing:.08em'>"
    "<span>KNOWMATE AI · DOCUMENTATION INTELLIGENCE</span>"
    f"<span>{APP_VERSION} · GROUNDED GENERATION · SOURCE TRACEABILITY</span></div>",
    unsafe_allow_html=True,
)
