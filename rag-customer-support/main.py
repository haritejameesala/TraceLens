"""Customer-support knowledge assistant using LangChain and automatic TraceLens callbacks.

This is a realistic local-first application skeleton with a curated support knowledge base.
It does not contain injected demo failures. TraceLens observes supported LangChain callback
boundaries; it does not modify retrieval or generation behavior.
"""
from __future__ import annotations

import os
import sys
import platform
import importlib.metadata
from pathlib import Path
from typing import Iterable
from hashlib import sha256

import httpx
from operator import itemgetter

ROOT = Path(__file__).resolve().parent
KB_PATH = ROOT / "knowledge_base"

SYSTEM_PROMPT = """You are a careful customer-support knowledge assistant for a SaaS product.
Answer only from the supplied internal knowledge-base excerpts. If the excerpts do not
support an answer, say what is unknown and recommend the appropriate support team. Never
invent policies, retention periods, refund eligibility, incident causes, or recovery times.
Do not request or expose passwords, one-time codes, API keys, session cookies, or payment-card
secrets. Cite supporting sources using the [Source: filename] labels included in the context.

Knowledge-base context:
{context}

Customer question: {question}

Give a concise, actionable answer and include source labels for factual claims."""


def load_knowledge_base(folder: Path):
    """Load and chunk Markdown articles with stable source and content identifiers."""
    from langchain_core.documents import Document
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    articles: list[Document] = []
    for path in sorted(folder.glob("*.md")):
        content = path.read_text(encoding="utf-8").strip()
        if content:
            articles.append(Document(page_content=content, metadata={
                "source": path.name,
                "article_id": path.stem,
                "content_hash": sha256(content.encode("utf-8")).hexdigest(),
            }))
    if not articles:
        raise RuntimeError(f"No Markdown knowledge articles found in {folder}")
    splitter = RecursiveCharacterTextSplitter(chunk_size=850, chunk_overlap=120,
        separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " ", ""])
    chunks = splitter.split_documents(articles)
    for index, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = index
        chunk.metadata["chunk_id"] = sha256(
            f"{chunk.metadata['source']}:{chunk.page_content}".encode("utf-8")
        ).hexdigest()[:24]
    return chunks


def format_documents(documents: Iterable[Document]) -> str:
    parts = []
    for doc in documents:
        source = Path(str(doc.metadata.get("source", "unknown"))).name
        chunk_id = str(doc.metadata.get("chunk_id", "unknown"))
        parts.append(f"[Source: {source}; Chunk: {chunk_id}]\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)


def build_chain():
    """Build the RAG chain; TraceLens attaches at the invocation boundary, not each step."""
    from langchain_chroma import Chroma
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import RunnableLambda, RunnableParallel
    from langchain_ollama import ChatOllama
    docs = load_knowledge_base(KB_PATH)
    embeddings = HuggingFaceEmbeddings(
        model_name=os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    persist_dir = Path(os.getenv("CHROMA_PATH", str(ROOT / ".chroma")))
    persist_dir.mkdir(parents=True, exist_ok=True)
    vectorstore = Chroma(
        collection_name="customer_support_knowledge",
        embedding_function=embeddings,
        persist_directory=str(persist_dir),
    )
    # Incremental, deterministic ingestion. Update changed chunks and remove stale ones;
    # unchanged chunk IDs are not re-embedded on every application restart.
    current = {f"support-chunk-{d.metadata['chunk_id']}": d for d in docs}
    existing = vectorstore.get(include=["metadatas"])
    existing_ids = set(existing.get("ids", []))
    stale_ids = sorted(i for i in existing_ids if str(i).startswith("support-chunk-") and i not in current)
    if stale_ids:
        vectorstore.delete(ids=stale_ids)
    for chunk_id, doc in current.items():
        if chunk_id not in existing_ids:
            vectorstore.add_documents([doc], ids=[chunk_id])
        else:
            # Upsert ensures changed content with a stable chunk identity is refreshed.
            vectorstore.update_documents([chunk_id], [doc])
    retriever = vectorstore.as_retriever(search_kwargs={"k": int(os.getenv("RETRIEVAL_K", "4"))})

    llm = ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "qwen2.5:3b"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        temperature=0,
    )
    prompt = ChatPromptTemplate.from_template(SYSTEM_PROMPT)
    # LCEL propagates callback config to the retriever and model automatically.
    return (
        RunnableParallel(
            question=itemgetter("question"),
            context=itemgetter("question") | retriever | RunnableLambda(format_documents),
        )
        | prompt
        | llm
        | StrOutputParser()
    )


def validate_configuration() -> tuple[str, str, bool]:
    project_id = os.getenv("TRACELENS_PROJECT_ID", "").strip()
    if project_id == "replace-with-project-id":
        project_id = ""
    api_url = os.getenv("TRACELENS_API_URL", "http://127.0.0.1:8000").rstrip("/")
    strict = os.getenv("TRACELENS_STRICT", "false").lower() in {"1", "true", "yes"}
    return project_id, api_url, strict


def ensure_project(project_id: str, api_url: str, strict: bool) -> str:
    """Resolve or idempotently register the app project once using a stable key."""
    if project_id:
        return project_id
    try:
        response = httpx.post(f"{api_url}/api/projects", timeout=5, json={
            "project_key": "customer-support-rag",
            "name": "Customer Support RAG",
            "description": "LangChain customer-support knowledge assistant with callback-based TraceLens instrumentation",
            "framework": "langchain",
        })
        response.raise_for_status()
        resolved = response.json().get("project_id")
        if not resolved:
            raise RuntimeError("Project registration response did not contain project_id")
        print(f"[TraceLens] Using project {resolved}")
        return resolved
    except Exception as exc:
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {401, 403}:
            raise RuntimeError(
                "TraceLens project creation requires a signed-in dashboard session. "
                "Create/select the project in the dashboard, generate its SDK key, "
                "then set TRACELENS_PROJECT_ID and TRACELENS_API_KEY in this app's environment."
            ) from exc
        if strict:
            raise RuntimeError(f"Could not resolve/register TraceLens project at {api_url}: {type(exc).__name__}") from exc
        print(f"[TraceLens] Project registration unavailable; tracing may be skipped: {type(exc).__name__}")
        return "customer-support-rag-unavailable"


def _safe_endpoint(value: str) -> str:
    """Return an endpoint suitable for telemetry without credentials or query strings."""
    from urllib.parse import urlsplit
    try:
        parsed = urlsplit(str(value).strip())
        if not parsed.scheme or not parsed.hostname:
            return "configured-endpoint-unparseable"
        host = parsed.hostname
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        port = f":{parsed.port}" if parsed.port else ""
        return f"{parsed.scheme.lower()}://{host}{port}"
    except (ValueError, TypeError):
        return "configured-endpoint-unparseable"


def _runtime_fingerprint() -> dict:
    """Record reproducibility facts without copying secret environment values."""
    packages = {}
    for package in (
        "langchain", "langchain-core", "langchain-community", "langchain-chroma",
        "langchain-ollama", "langchain-text-splitters", "chromadb",
        "sentence-transformers", "transformers", "torch", "huggingface-hub",
        "ollama", "httpx", "tracelens-sdk",
    ):
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            packages[package] = None
    manifest_fingerprints = {}
    for path in (ROOT / "requirements.txt", ROOT / "pyproject.toml", ROOT / "uv.lock"):
        try:
            data = path.read_bytes()
            manifest_fingerprints[path.name] = {
                "sha256": sha256(data).hexdigest(),
                "size_bytes": len(data),
            }
        except OSError:
            continue
    return {
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "package_versions": packages,
        "dependency_manifests": manifest_fingerprints,
        "relevant_environment_variable_names": sorted(
            key for key in os.environ
            if any(term in key.upper() for term in (
                "MODEL", "OLLAMA", "EMBEDDING", "CHROMA", "VECTOR",
                "LANGCHAIN", "HUGGINGFACE", "TRACELENS",
            ))
        ),
    }


def main() -> None:
    from dotenv import load_dotenv
    from tracelens_sdk import TraceLens, langchain_callback
    load_dotenv(ROOT / ".env")
    project_id, api_url, strict = validate_configuration()
    # Fail early with a useful message if TraceLens API is unavailable in strict mode;
    # non-strict mode keeps the support assistant available during an observability outage.
    try:
        response = httpx.get(f"{api_url}/health", timeout=3)
        response.raise_for_status()
    except Exception as exc:
        if strict:
            raise RuntimeError(f"TraceLens API is unavailable at {api_url}: {exc}") from exc
        print(f"[TraceLens] API unavailable; support queries can continue (strict=false): {type(exc).__name__}")

    project_id = ensure_project(project_id, api_url, strict)
    with TraceLens(
        project_id=project_id,
        api_url=api_url,
        strict=strict,
        api_key=os.getenv("TRACELENS_API_KEY"),
    ) as tracer:
        # Instrument initialization too: dependency, embedding-model, vector-store,
        # and configuration errors often happen before the first user query.
        with tracer.start_run(
            "application-startup",
            version=os.getenv("APP_VERSION", "1.0.0"),
            metadata={
                "application": "customer-support-knowledge-assistant",
                "environment": os.getenv("APP_ENV", "local"),
                "embedding_model": os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
                "llm_model": os.getenv("OLLAMA_MODEL", "qwen2.5:3b"),
                "llm_endpoint": _safe_endpoint(os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")),
                "retrieval_k": int(os.getenv("RETRIEVAL_K", "4")),
                "capture_mode": "application_startup",
                "runtime_fingerprint": _runtime_fingerprint(),
            },
        ):
            chain = build_chain()
        print("Customer Support Knowledge Assistant")
        print("Ask about account access, billing, incidents, or data handling. Type 'exit' to quit.\\n")
        while True:
            try:
                question = input("You> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye.")
                break
            if question.lower() in {"exit", "quit", "q"}:
                break
            if not question:
                continue
            callback = langchain_callback(
                tracer,
                run_name="customer-support-rag",
                version=os.getenv("APP_VERSION", "1.0.0"),
                metadata={"application": "customer-support-knowledge-assistant", "environment": os.getenv("APP_ENV", "local"),
                          "retrieval_k": int(os.getenv("RETRIEVAL_K", "4")), "embedding_model": os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
                          "llm_model": os.getenv("OLLAMA_MODEL", "qwen2.5:3b"),
                          # Store only scheme/host/port for history comparison; never record URL credentials or query parameters.
                          "llm_endpoint": _safe_endpoint(os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))},
            )
            try:
                answer = chain.invoke({"question": question}, config={"callbacks": [callback], "run_name": "customer-support-rag"})
                print(f"\nAssistant> {answer}\n")
            except Exception as exc:
                # Emit safe, structured context for LLM diagnosis without storing the question,
                # answer, credentials, or exception locals.
                try:
                    callback._event("application.invoke", "error", "application", status="failed",
                        extra={"phase": "error", "exception_type": type(exc).__name__,
                               "question_length": len(question),
                               "question_sha256": sha256(question.encode("utf-8", errors="replace")).hexdigest(),
                               "model": os.getenv("OLLAMA_MODEL", "qwen2.5:3b"),
                               "embedding_model": os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
                               "retrieval_k": int(os.getenv("RETRIEVAL_K", "4"))}, error=exc)
                except Exception:
                    pass
                print(f"\nThe request failed ({type(exc).__name__}). Check service availability and TraceLens events.\n")


if __name__ == "__main__":
    main()
