"""分散表現による類似度ランキングを計算するモジュール"""
from sbert_model import model

def rank_by_sbert(array, concept, top_k=5):
    """コンセプトとの類似度が高い順に、上位top_k件のエリアを返す"""
    concept_vec = model.encode(concept)

    for item in array:
        item.compute_similarity(concept_vec)

    array.sort(reverse=True)

    return array[:top_k]