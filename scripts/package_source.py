"""Package public source files; never include local corpora or credentials."""
import argparse
from pathlib import Path
import zipfile

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
files = ["README.md", ".env.example", ".gitignore", ".dockerignore", ".editorconfig", "compose.yaml",
         "backend/pyproject.toml", "backend/requirements-tested.txt", "backend/Dockerfile", "backend/.dockerignore",
         "frontend/package.json", "frontend/package-lock.json", "frontend/tsconfig.json", "frontend/vite.config.ts",
         "frontend/index.html", "frontend/Dockerfile", "frontend/nginx.conf", "frontend/.dockerignore",
         "evaluation/demo.jsonl", "evaluation/README.md", "scripts/package_source.py", "scripts/verify_deepseek.py"]
for directory in ("backend/app", "backend/tests", "frontend/src", "frontend/tests", "docs", ".github"):
    files.extend(str(p.relative_to(root)) for p in (root / directory).rglob("*")
                 if p.is_file() and p.suffix in {".py", ".ts", ".tsx", ".css", ".mjs", ".md", ".yml", ".yaml"}
                 and "__pycache__" not in p.parts)
files.append("data/demo/guide.md")
args.output.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as archive:
    for name in sorted(set(files)):
        source = root / name
        if source.is_symlink():
            raise SystemExit(f"Refusing symlink: {name}")
        archive.write(source, "intelligent-customer-support-assistant/" + name)
print(f"Packaged {len(set(files))} public source files.")
