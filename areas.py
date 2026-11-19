"""データベースからエリア・スポット情報を取得し，類似度計算を行うクラス群"""
import sqlite3
import numpy as np
from sbert_model import model, EMBED_DIM

ALPHA = 0.4         # エリアスコアにおけるエリア概要文の重み
TOP_K_SPOTS = 3     # エリアスコア計算・表示に使う上位スポット数

class SpotData():
    """観光スポット1件分の情報と，コンセプトとの類似度を保持するクラス"""
    similarity = 0

    def __init__(self, spot_id, area_id, name, desc, blob):
        self.spot_id = spot_id
        self.area_id = area_id
        self.name = name
        self.desc = desc
        self.blob = blob

    def compute_similarity(self, concept_vec):
        """概要文とコンセプトの類似度を計算する"""
        if not self.blob:
            self.similarity = 0.0
            return

        embeddings = np.frombuffer(self.blob, dtype=np.float32).reshape(-1, EMBED_DIM)
        similarities = model.similarity(concept_vec, embeddings)
        self.similarity = similarities.max().item()

    def __repr__(self):
        return f"{self.name} ({self.similarity:.3f})"


class AreaData():
    """観光エリア1件分の情報と，配下スポット一覧を保持するクラス"""
    similarity = 0

    def __init__(self, num, prefecture, area, desc, blob):
        self.num = num
        self.prefecture = prefecture
        self.area = area
        self.desc = desc
        self.blob = blob
        self.spots = []

    def compute_similarity(self, concept_vec):
        """エリア概要文と配下スポットの類似度から，エリア全体のスコアを計算する"""
        if not self.blob:
            area_desc_sim = 0.0
        else:
            embeddings = np.frombuffer(self.blob, dtype=np.float32).reshape(-1, EMBED_DIM)
            area_desc_sim = model.similarity(concept_vec, embeddings).max().item()

        # 各スポットの類似度を計算
        for spot in self.spots:
            spot.compute_similarity(concept_vec)

        # 上位TOP_K_SPOTS件のスポット類似度の平均
        if self.spots:
            top_sims = sorted([s.similarity for s in self.spots], reverse=True)[:TOP_K_SPOTS]
            spot_avg = sum(top_sims) / len(top_sims)
        else:
            spot_avg = 0.0

        # エリアとスポットの重み付け平均をエリア全体のスコアとする
        self.similarity = ALPHA * area_desc_sim + (1 - ALPHA) * spot_avg

    def top_spots(self, n=TOP_K_SPOTS):
        """類似度が高い順にスポットを返す"""
        return sorted(self.spots, key=lambda s: s.similarity, reverse=True)[:n]

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.similarity == other.similarity

    def __lt__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.similarity < other.similarity

    def __repr__(self):
        lines = [f"{self.prefecture}, {self.area} ({self.similarity:.3f})"]
        for spot in self.top_spots():
            lines.append(f"  * {spot}")
        return "\n".join(lines)


def load_db(db_name):
    """指定したデータベースからエリアとスポットを取得し，AreaDataのリストとして返す"""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # areasとspotsをLEFT JOINして一度に取得
    cursor.execute('''
        SELECT a.id, a.prefecture, a.area, a.desc, a.embedding,
               s.id, s.name, s.desc, s.embedding
        FROM areas a
        LEFT JOIN spots s ON s.area_id = a.id
        ORDER BY a.id
    ''')
    results = cursor.fetchall()
    conn.close()

    area_map = {}
    for row in results:
        a_id, prefecture, area, a_desc, a_blob = row[0], row[1], row[2], row[3], row[4]
        s_id, s_name, s_desc, s_blob = row[5], row[6], row[7], row[8]

        if a_id not in area_map:
            area_map[a_id] = AreaData(a_id, prefecture, area, a_desc, a_blob)

        if s_id is not None:
            spot = SpotData(s_id, a_id, s_name, s_desc, s_blob)
            area_map[a_id].spots.append(spot)

    return list(area_map.values())