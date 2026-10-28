from pathlib import Path
import pytest
from app.ingest import ingest, ENC

def test_heading_budget_overlap_dedup(tmp_path):
    body = "# \u63a5\u53e3\n" + "\u5ba2\u6237\u9700\u8981\u901a\u8fc7\u6ce8\u518c\u90ae\u7bb1Reset password。" * 160
    (tmp_path/"a.md").write_text(body)
    (tmp_path/"b.txt").write_text(body)
    (tmp_path/"excluded.pdf").write_text("private")
    chunks = ingest(tmp_path)
    assert len(chunks) > 1
    assert all(c.token_count <= 512 and "�" not in c.text for c in chunks)
    assert all(c.heading == "\u63a5\u53e3" and c.source == "a.md" and "b.txt" in c.aliases for c in chunks)
    assert all(c.id == ingest(tmp_path)[i].id for i,c in enumerate(chunks))
    assert all(c.token_count == len(ENC.encode(c.text)) for c in chunks)

def test_invalid_overlap(tmp_path):
    with pytest.raises(ValueError):
        ingest(tmp_path, size=64, overlap=64)

def test_empty(tmp_path):
    assert ingest(tmp_path) == []
