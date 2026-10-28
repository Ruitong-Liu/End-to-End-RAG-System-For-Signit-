"""Deterministic, local-only Markdown/TXT ingestion; no credentials required."""
import argparse
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, asdict
from pathlib import Path
import tiktoken

ENC = tiktoken.get_encoding("cl100k_base")

@dataclass
class Chunk:
    id: str
    text: str
    source: str
    heading: str
    token_count: int
    aliases: list[str]

def normalize(text):
    return re.sub(r"[ \t]+", " ", unicodedata.normalize("NFKC", text)).strip()

def sections(text):
    heading = ""
    lines = []
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        match = None if fenced else re.match(r"^#{1,6}\s+(.+)", line)
        if match:
            if lines:
                yield heading, "\n".join(lines)
            heading, lines = match[1], []
        else:
            lines.append(line)
    if lines:
        yield heading, "\n".join(lines)

def ingest(directory: Path, size=512, overlap=64):
    if not 0 <= overlap < size:
        raise ValueError("overlap must be smaller than chunk size")
    unique = {}
    files = sorted(p for p in directory.rglob("*") if p.is_file() and not p.is_symlink() and p.suffix.lower() in {".md", ".txt"})
    for path in files:
        source = path.relative_to(directory).as_posix()
        for heading, body in sections(normalize(path.read_text(encoding="utf-8-sig"))):
            # Include heading in the 512-token budget; preserve exact UTF-8 boundaries.
            prefix = ENC.encode(heading + "\n")[: min(80, size // 4)] if heading else []
            ids = ENC.encode(body.strip())
            budget = size - len(prefix)
            start = 0
            while start < len(ids):
                end = min(start + budget, len(ids))
                while end > start:
                    try:
                        text = ENC.decode_bytes(prefix + ids[start:end]).decode("utf-8")
                        break
                    except UnicodeDecodeError:
                        end -= 1
                if end <= start:
                    raise ValueError("cannot split UTF-8 token sequence")
                key = hashlib.sha256(normalize(text).encode()).hexdigest()
                if key in unique:
                    if source != unique[key].source and source not in unique[key].aliases:
                        unique[key].aliases.append(source)
                else:
                    unique[key] = Chunk(key, text, source, heading, len(ENC.encode(text)), [])
                if end == len(ids):
                    break
                start = max(start + 1, end - min(overlap, budget - 1))
                while start < end:
                    try:
                        ENC.decode_bytes(ids[start:end]).decode("utf-8")
                        break
                    except UnicodeDecodeError:
                        start += 1
    return list(unique.values())

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    chunks = ingest(args.corpus)
    if not chunks:
        raise SystemExit("No Markdown/TXT documents found")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps([asdict(c) for c in chunks], ensure_ascii=False, indent=2))
    print(json.dumps({"chunks": len(chunks), "output": str(args.output)}))

if __name__ == "__main__":
    main()
