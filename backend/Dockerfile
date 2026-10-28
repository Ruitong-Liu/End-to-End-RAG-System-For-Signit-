FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/models TIKTOKEN_CACHE_DIR=/opt/tiktoken
RUN pip install --no-cache-dir "torch==2.14.1+cpu" --index-url https://download.pytorch.org/whl/cpu
COPY pyproject.toml ./
RUN python -c 'import tomllib, subprocess; project = tomllib.load(open("pyproject.toml", "rb"))["project"]; subprocess.check_call(["pip", "install", "--no-cache-dir", *project["dependencies"], *project["optional-dependencies"]["models"]])' \
    && python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')" \
    && chmod -R a+rX /opt/tiktoken
COPY app ./app
RUN pip install --no-cache-dir --no-deps .
RUN useradd --uid 10001 --create-home rag && mkdir /models /index && chown -R rag /models /index
USER rag
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
