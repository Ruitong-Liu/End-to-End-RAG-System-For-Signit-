import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path
from collections import defaultdict, OrderedDict
from threading import RLock
from time import monotonic
import jieba
import numpy as np
from rank_bm25 import BM25Okapi
from .ingest import ingest, Chunk

MODES = {"bm25", "dense", "hybrid", "hybrid_rerank"}

def tokenize(text):
    return [t.lower() for t in jieba.lcut(text) if re.search(r"[\w]", t)]

def rrf(rankings, k=60):
    scores = defaultdict(float)
    for ranking in rankings:
        for rank, item in enumerate(dict.fromkeys(ranking), 1):
            scores[item] += 1 / (k + rank)
    return sorted(scores, key=lambda i: (-scores[i], i))

class Retriever:
    def __init__(self, settings, chunks=None, encoder=None, reranker=None):
        self.settings = settings
        self.chunks = chunks if chunks is not None else ingest(Path(settings.corpus_dir))
        if not self.chunks:
            raise ValueError("The knowledge base is empty. Check CORPUS_DIR.")
        if settings.retrieval_mode not in MODES:
            raise ValueError("Unknown retrieval mode")
        self.search_texts = [f"{Path(c.source).stem}\n{c.heading}\n{c.text}" for c in self.chunks]
        self.tokens = [tokenize(text) + tokenize(Path(c.source).stem)*2 for c, text in zip(self.chunks, self.search_texts)]
        self.bm25 = BM25Okapi(self.tokens)
        self.encoder, self.reranker = encoder, reranker
        self.vectors = None
        self.cache = OrderedDict()
        self.lock = RLock()
        self.fingerprint = hashlib.sha256(json.dumps([asdict(c) for c in self.chunks], sort_keys=True).encode()).hexdigest()

    def load_dense(self):
        if self.vectors is not None:
            return
        if self.encoder is None:
            from sentence_transformers import SentenceTransformer
            self.encoder = SentenceTransformer(self.settings.embedding_model, device=self.settings.model_device)
        directory = Path(self.settings.index_dir)
        directory.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256((self.fingerprint + self.settings.embedding_model + "source-heading-v1").encode()).hexdigest()
        path = directory / (key + ".npy")
        if path.exists():
            self.vectors = np.load(path, allow_pickle=False)
        else:
            self.vectors = self.encoder.encode(self.search_texts, normalize_embeddings=True, batch_size=16)
            temporary = directory / (key + ".tmp.npy")
            np.save(temporary, self.vectors)
            temporary.replace(path)
        if len(self.vectors) != len(self.chunks):
            raise ValueError("Index and corpus mismatch")

    def search(self, query, mode=None):
        mode = mode or self.settings.retrieval_mode
        if mode not in MODES:
            raise ValueError("Unknown retrieval mode")
        # One CPU inference at a time: bound memory usage and protect model/cache state.
        with self.lock:
            key = (query, mode, self.settings.retrieval_depth, self.settings.top_k)
            now = monotonic()
            if key in self.cache and now - self.cache[key][0] < self.settings.cache_ttl:
                self.cache.move_to_end(key)
                return [dict(x) for x in self.cache[key][1]]
            depth = self.settings.retrieval_depth
            rankings = []
            if mode != "dense":
                query_tokens = tokenize(query)
                scores = self.bm25.get_scores(query_tokens)
                # BM25 IDF can be zero/negative on tiny corpora; use term overlap for eligibility.
                eligible = [i for i, tokens in enumerate(self.tokens) if set(query_tokens).intersection(tokens)]
                rankings.append(sorted(eligible, key=lambda i: (-scores[i], i))[:depth])
            if mode != "bm25":
                self.load_dense()
                vector = self.encoder.encode(["\u4e3a\u8fd9\u4e2a\u53e5\u5b50\u751f\u6210\u8868\u793a\u4ee5\u7528\u4e8e\u68c0\u7d22\u76f8\u5173\u6587\u7ae0：" + query], normalize_embeddings=True)[0]
                scores = self.vectors @ vector
                rankings.append([int(i) for i in np.argsort(-scores, kind="stable")[:depth]])
            candidates = rrf(rankings)[:depth] if len(rankings) > 1 else rankings[0]
            relevance = {}
            if mode == "hybrid_rerank" and candidates:
                if self.reranker is None:
                    from sentence_transformers import CrossEncoder
                    self.reranker = CrossEncoder(self.settings.reranker_model, device=self.settings.model_device, max_length=512)
                import torch
                values = self.reranker.predict([(query, self.search_texts[i]) for i in candidates], activation_fn=torch.nn.Sigmoid(), batch_size=8)
                relevance = {i: float(v) for i, v in zip(candidates, values)}
                candidates.sort(key=lambda i: -relevance[i])
            result = [{**asdict(self.chunks[i]), "score": relevance.get(i), "rank": rank} for rank, i in enumerate(candidates[:self.settings.top_k], 1)]
            if self.settings.cache_size:
                self.cache[key] = (now, result)
                self.cache.move_to_end(key)
                while len(self.cache) > self.settings.cache_size:
                    self.cache.popitem(last=False)
            return [dict(x) for x in result]
