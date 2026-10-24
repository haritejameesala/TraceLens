from app.main import chunk_text, redact, retrieve_lexical

def test_chunking_preserves_tail():
    chunks = chunk_text(("trace failure and retrieval evidence " * 100).strip(), size=180, overlap=20)
    assert len(chunks) > 1 and chunks[-1]

def test_retriever_ranks_relevant_document():
    docs = [{"chunk_id":"1","title":"Database timeout","text":"Database connection timeout and pool exhaustion."},
            {"chunk_id":"2","title":"Frontend colors","text":"CSS spacing and typography rules."}]
    result = retrieve_lexical("database connection timeout", docs, top_k=2)
    assert result[0]["chunk_id"] == "1" and result[0]["score"] > 0

def test_sensitive_fields_are_redacted_recursively():
    value = redact({"api_key":"secret","nested":{"password":"nope","ok":3}})
    assert value["api_key"] == "[REDACTED]" and value["nested"]["password"] == "[REDACTED]"
    assert value["nested"]["ok"] == 3


def test_redaction_preserves_datetime_objects():
    from datetime import datetime, timezone
    stamp = datetime.now(timezone.utc)
    assert redact({"timestamp": stamp})["timestamp"] == stamp
