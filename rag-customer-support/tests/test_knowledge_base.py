from pathlib import Path

KB = Path(__file__).resolve().parents[1] / "knowledge_base"


def test_knowledge_base_contains_real_operational_topics():
    articles = sorted(KB.glob("*.md"))
    assert len(articles) >= 4
    content = {path.name: path.read_text(encoding="utf-8") for path in articles}
    assert "billing_and_subscriptions.md" in content
    assert "incidents_and_availability.md" in content
    assert "data_and_privacy.md" in content
    assert "failed payment" in content["billing_and_subscriptions.md"].lower()


def test_articles_include_sourceable_content():
    for path in KB.glob("*.md"):
        text = path.read_text(encoding="utf-8").strip()
        assert text.startswith("# ")
        assert len(text) > 100
