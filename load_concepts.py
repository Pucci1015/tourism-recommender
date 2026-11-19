"""concepts.json からカテゴリとコンセプトを読み込み，categories / concepts テーブルを作成するスクリプト"""
import sqlite3
import json

DB_PATH = "tourism.sqlite"
JSON_PATH = "concepts.json"

def setup_concept_tables():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # テーブルの初期化
    cursor.execute('DROP TABLE IF EXISTS concepts')
    cursor.execute('DROP TABLE IF EXISTS categories')

    # カテゴリテーブル
    cursor.execute('''
    CREATE TABLE categories (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL
    )
    ''')

    # コンセプト詳細テーブル
    cursor.execute('''
    CREATE TABLE concepts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL,
        concept_text TEXT NOT NULL,
        FOREIGN KEY (category_id) REFERENCES categories(id)
    )
    ''')

    # JSONファイルの読み込み
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # データベースへの登録
    for item in data:
        # カテゴリの登録
        cursor.execute('''
        INSERT INTO categories (id, name) VALUES (?, ?)
        ''', (item["category_id"], item["category_name"]))

        # そのカテゴリに属するコンセプトの登録
        for text in item["concepts"]:
            cursor.execute('''
            INSERT INTO concepts (category_id, concept_text) VALUES (?, ?)
            ''', (item["category_id"], text))

    conn.commit()
    conn.close()
    print("finish")

if __name__ == "__main__":
    setup_concept_tables()