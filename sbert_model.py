"""SBERTモデルの共通設定・読み込み"""
from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBED_DIM = 384

# 日本語を扱えるSBERTモデルをロード
model = SentenceTransformer(MODEL_NAME)