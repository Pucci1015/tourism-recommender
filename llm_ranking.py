"""LLMによる観光地ランキングを生成するモジュール"""
import os
import json
from dotenv import load_dotenv
from google import genai

LLM_MODEL = "gemini-3.1-flash-lite"
MAX_SPOTS_PER_AREA = 5      # プロンプトに含めるスポット数の上限
DESC_TRUNCATE = 200         # スポット概要文の文字数上限

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

class LlmResult:
    """LLMが選んだエリア1件分の結果を保持するクラス"""

    def __init__(self, prefecture, area, desc, reason, spots):
        self.prefecture = prefecture
        self.area = area
        self.desc = desc
        self.reason = reason
        self.spots = spots

    def __repr__(self):
        lines = [f"{self.prefecture}, {self.area}  ({self.reason})"]
        for spot in self.spots:
            lines.append(f"  * {spot}")
        return "\n".join(lines)


def rank_by_llm(array, concept, top_k=5):
    """候補エリアの中から，コンセプトとの適合度をLLMに判断させ，上位top_k件のランキングを生成する"""
    area_text_list = []
    for area in array:
        if area.spots:
            spots_text = "\n".join(
                f"    - {s.name}: {s.desc[:DESC_TRUNCATE]}"
                for s in area.top_spots(MAX_SPOTS_PER_AREA)
            )
        else:
            spots_text = "    (スポット情報なし)"

        area_text_list.append(
            f"[id={area.num}] {area.prefecture} {area.area}\n"
            f"  概要: {area.desc}\n"
            f"  スポット:\n{spots_text}"
        )
    areas_block = "\n\n".join(area_text_list)

    prompt = f"""以下は観光地エリアとそのスポット一覧です．
コンセプト「{concept}」に最も合う上位{top_k}件のエリアを選び，
各エリアについて最も合うスポットを最大3件選んでください．

{areas_block}

出力は以下のJSON形式のみで返してください（説明文や```json マークダウンは不要）：
[
  {{
    "id": エリアのid（数値）,
    "prefecture": "都道府県名",
    "area": "エリア名",
    "desc": "エリアの概要",
    "reason": "選んだ理由（30〜50文字程度）",
    "spots": ["スポット名1", "スポット名2", "スポット名3"]
  }}
]
"""

    response = client.models.generate_content(
        model=LLM_MODEL,
        contents=prompt,
    )

    text = response.text
    if text is None:
        return []
    text = text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        ranked = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"[ERROR] LLM出力のJSON解析に失敗: {e}")
        print(text)
        return []

    return [
        LlmResult(item["prefecture"], item["area"], item["desc"], item["reason"], item["spots"])
        for item in ranked[:top_k]
    ]