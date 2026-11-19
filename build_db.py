"""観光エリア・スポット情報を収集してベクトル化し，areas / spots テーブルを作成するスクリプト"""
import requests
from bs4 import BeautifulSoup
import time
import sqlite3
import numpy as np
import re
from sbert_model import model

DB_PATH = "tourism.sqlite"

# データベースへの接続
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 既存テーブルの削除
cursor.execute('DROP TABLE IF EXISTS areas')
cursor.execute('DROP TABLE IF EXISTS spots')

# テーブルの作成
# エリアのテーブル
cursor.execute('''
CREATE TABLE IF NOT EXISTS areas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prefecture TEXT NOT NULL,
    area TEXT NOT NULL,
    desc TEXT,
    embedding BLOB
)
''')

# スポットのテーブル
cursor.execute('''
CREATE TABLE IF NOT EXISTS spots (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    area_id   INTEGER NOT NULL,
    name      TEXT NOT NULL,
    desc      TEXT,
    embedding BLOB,
    FOREIGN KEY (area_id) REFERENCES areas(id)
)
''')

# サイトにアクセスする関数
def access_the_site(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        return BeautifulSoup(response.content, "html.parser")
    except requests.RequestException as e:
        print(f"[ERROR] {url}: {e}")
        return 0

for i in range(47):
    # 各都道府県ページのurl
    url = f"https://www.jalan.net/travel/{(i+1):02}0000/"

    # サイトにアクセス
    soup = access_the_site(url)
    if not soup:
        continue

    # 都道府県名
    title_tag = soup.find("title")
    if not title_tag:
        print(f"[SKIP] タイトルが見つかりません: {url}")
        continue
    prefecture = title_tag.text.removesuffix("の旅行ガイド - じゃらんnet")

    # 各エリアの概要を取得
    for item in soup.find_all("div", class_="item-listContents"):
        # 各要素の存在確認
        area_tag = item.find("h3", class_="item-name")
        desc_tag = item.find("p", class_="item_desc")
        if not area_tag or not desc_tag:
            continue

        area_a_tag = area_tag.find("a")
        if not area_a_tag:
            continue

        area = area_a_tag.text          # エリア名
        area_url = area_a_tag["href"]   # エリアページのurl
        desc = desc_tag.text            # エリアの概要

        # 文ごとに分割
        sentences = [s for s in desc.split('。') if s.strip()]

        # 空文のフェイルセーフ
        if not sentences:
            blob = None
        else:
            # 分割した各文をまとめてベクトル化
            embeddings = model.encode(sentences)
            blob = embeddings.astype(np.float32).tobytes()

        # エリアテーブルにデータを挿入
        cursor.execute('''
        INSERT INTO areas (prefecture, area, desc, embedding)
        VALUES (?, ?, ?, ?)
        ''', (prefecture, area, desc, blob))

        area_id = cursor.lastrowid

        # エリア個別ページにアクセス
        area_soup = access_the_site("https://www.jalan.net" + area_url)
        if not area_soup:
            continue

        # 観光スポットのurlを取得
        area_a = area_soup.select_one("#listTabs > li:nth-of-type(2) > a")
        if not area_a or not area_a.has_attr('href'):
            continue
        spots_url = area_a["href"]

        # 観光スポットのページにアクセス
        spots_soup = access_the_site("https:" + spots_url)
        if not spots_soup:
            continue

        # 観光スポットの要素を配列で取得
        spots = spots_soup.find_all("div", class_="item-info")

        # 各観光スポットの処理
        for spot in spots:
            spot_a = spot.select_one(".item-name > a")
            if not spot_a or not spot_a.has_attr('href'):
                continue
            spot_url = spot_a["href"]

            # 各観光スポットのページにアクセス
            spot_soup = access_the_site("https:" + spot_url)
            if not spot_soup:
                continue

            # 観光スポット名を取得
            spot_name = spot_soup.find("h1", class_="detailTitle").text

            # 観光スポットの概要文を取得
            about_div = spot_soup.find("div", id="aboutArea")
            if not about_div:
                continue

            desc_parts = []
            for p in about_div.find_all("p"):
                text = p.get_text(strip=True)

                if text.startswith("※掲載されている情報や写真については"):
                    break

                desc_parts.append(text)

            if not desc_parts:
                time.sleep(1)   # 待機
                continue

            spot_desc = [re.sub(r'^[●・▲■◆○〇\-\*]+', '', t).strip() for t in desc_parts]

            # 概要文を1つの文字列に結合
            spot_desc_text = ''.join(spot_desc)

            # 文ごとに分割
            spot_sentences = [s for s in spot_desc_text.split('。') if s.strip()]

            # 空文のフェイルセーフ
            if not spot_sentences:
                continue

            # ベクトル化してBLOBに変換
            spot_embeddings = model.encode(spot_sentences)
            spot_blob = spot_embeddings.astype(np.float32).tobytes()

            # spotsテーブルに挿入
            cursor.execute('''
            INSERT INTO spots (area_id, name, desc, embedding)
            VALUES (?, ?, ?, ?)
            ''', (area_id, spot_name, spot_desc_text, spot_blob))

            print(prefecture, area, "-", spot_name)

            time.sleep(1)   # 待機

    conn.commit()   # 都道府県ごとにコミット

# データベースの接続を閉じる
conn.close()
print("finish")