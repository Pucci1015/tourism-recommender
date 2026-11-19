"""観光地ランキングの比較"""
from areas import load_db
from sbert_ranking import rank_by_sbert
from llm_ranking import rank_by_llm

TOP_K_AREAS = 5                         # 最終的に表示する件数
CANDIDATE_K = 20                        # LLMに渡す候補エリア数
DB_NAME = "tourism.sqlite"

def print_results(results):
    """ランキング結果を順位付きで表示する"""
    for rank, result in enumerate(results, 1):
        print(f"{rank}位 {result}")
        print()

areas = load_db(DB_NAME)

def recommend(concept):
    if concept != "":
        # 分散表現で上位候補を抽出
        candidates = rank_by_sbert(areas, concept, CANDIDATE_K)

        # 分散表現のみによるランキング
        embedding_results = candidates[:TOP_K_AREAS]
        # print("=== 分散表現 ===")
        # print_results(embedding_results)

        # 分散表現で絞り込んだ候補から，LLMが最終ランキングを生成
        llm_results = rank_by_llm(candidates, concept, TOP_K_AREAS)
        # print("=== LLM ===")
        # print_results(llm_results)

    else:
        embedding_results = []
        llm_results = []

    return {
        'embedding': embedding_results,
        'llm': llm_results,
    }
