from flask import Flask, render_template, request, jsonify, redirect, url_for, abort, Response
from functools import wraps
from dotenv import load_dotenv
from recommender import recommend, DB_NAME
from datetime import datetime
import hmac
import os
import sqlite3

load_dotenv()

app = Flask(__name__)

ADMIN_USER     = os.getenv('ADMIN_USER', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')


# ================================================================== #
#  管理者認証（Basic 認証）
# ================================================================== #

def admin_required(view):
    """管理者ページ用デコレータ。.env の ADMIN_USER / ADMIN_PASSWORD で認証する。
    ADMIN_PASSWORD が未設定の場合は常にアクセスを拒否する。"""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not ADMIN_PASSWORD:
            abort(403)

        auth = request.authorization
        if (auth is None
                or not hmac.compare_digest(auth.username or '', ADMIN_USER)
                or not hmac.compare_digest(auth.password or '', ADMIN_PASSWORD)):
            return Response(
                '認証が必要です。', 401,
                {'WWW-Authenticate': 'Basic realm="admin", charset="UTF-8"'}
            )
        return view(*args, **kwargs)
    return wrapper


# ================================================================== #
#  メインルート
# ================================================================== #

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/categories')
def categories():
    return render_template('categories.html', categories=get_categories())


@app.route('/concepts')
def concepts():
    category_id = request.args.get('category_id', type=int)
    if category_id is None:
        abort(404)

    concept_list  = get_concepts(category_id)
    category_name = get_category_name(category_id)

    if category_name is None:
        abort(404)

    return render_template('concepts.html',  concepts=concept_list, category_name=category_name, category_id=category_id)


@app.route('/result')
def result():
    concept = request.args.get('concept', '').strip()
    if not concept:
        return redirect(url_for('index'))

    data = recommend(concept)
    return render_template('result.html', concept=concept, embedding=data['embedding'], llm=data['llm'])


# ================================================================== #
#  アンケート
# ================================================================== #

@app.route('/survey', methods=['GET', 'POST'])
def survey():
    if request.method == 'POST':
        save_survey(request.form)
        return render_template('survey_done.html')

    concept = request.args.get('concept', '').strip()
    return render_template('survey.html', concept=concept)


@app.route('/survey/result')
@admin_required
def survey_result():
    """アンケート集計ページ（隠しページ）"""
    import json
    data = aggregate_survey()
    return render_template('survey_result.html', data=data, data_json=json.dumps(data, ensure_ascii=False) if data else 'null')


@app.route('/survey/result/csv')
@admin_required
def survey_result_csv():
    """全回答を CSV でダウンロードする"""
    import csv, io
    data = aggregate_survey()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['id', 'created_at', 'concept',
                     'q1_relevance', 'q2_ranking',
                     'q3_sbert_satis', 'q4_llm_satis', 'q5_reason_helpful',
                     'q6_prefer', 'q7_comment'])
    if data:
        for i, row in enumerate(data['rows'], 1):
            writer.writerow([i] + list(row))
    return Response(
        buf.getvalue(),
        mimetype='text/csv; charset=utf-8-sig',   # utf-8-sig でExcelが文字化けしない
        headers={'Content-Disposition': 'attachment; filename="survey_responses.csv"'}
    )


# ================================================================== #
#  DB ブラウザ
# ================================================================== #

@app.route('/db')
@admin_required
def db_browser():
    return render_template('db_browser.html')


@app.route('/db/api/prefectures')
@admin_required
def db_api_prefectures():
    conn = sqlite3.connect(DB_NAME)
    cur  = conn.cursor()
    cur.execute('SELECT DISTINCT prefecture FROM areas ORDER BY id')
    rows = cur.fetchall()
    conn.close()
    return jsonify([r[0] for r in rows])


@app.route('/db/api/areas')
@admin_required
def db_api_areas():
    pref = request.args.get('pref', '')
    conn = sqlite3.connect(DB_NAME)
    cur  = conn.cursor()
    cur.execute(
        'SELECT id, area FROM areas WHERE prefecture = ? ORDER BY id',
        (pref,)
    )
    rows = cur.fetchall()
    conn.close()
    return jsonify([{'id': r[0], 'area': r[1]} for r in rows])


@app.route('/db/api/area/<int:area_id>')
@admin_required
def db_api_area(area_id):
    conn = sqlite3.connect(DB_NAME)
    cur  = conn.cursor()
    cur.execute(
        'SELECT prefecture, area, desc FROM areas WHERE id = ?',
        (area_id,)
    )
    row = cur.fetchone()
    if row is None:
        conn.close()
        return jsonify({'error': 'not found'}), 404

    area = {'prefecture': row[0], 'area': row[1], 'desc': row[2]}
    cur.execute(
        'SELECT id, name, desc FROM spots WHERE area_id = ? ORDER BY id',
        (area_id,)
    )
    spots = [{'id': r[0], 'name': r[1], 'desc': r[2]}
             for r in cur.fetchall()]
    conn.close()
    return jsonify({'area': area, 'spots': spots})


# ================================================================== #
#  エラーハンドラ
# ================================================================== #

@app.errorhandler(403)
def forbidden(e):
    return render_template('error.html', code=403, title='アクセスできません', message='このページを表示する権限がありません。'), 403


@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', code=404,  title='ページが見つかりません', message='URLが間違っているか、ページが存在しません。'), 404


@app.errorhandler(500)
def internal_error(e):
    return render_template('error.html', code=500, title='サーバエラー', message='サーバ側で問題が発生しました。しばらく経ってから再度お試しください。'), 500


# ================================================================== #
#  ヘルパー
# ================================================================== #

def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def aggregate_survey():
    """survey_responses テーブルを集計して辞書で返す。
    テーブルがまだ存在しない場合は空の集計結果を返す。"""
    conn = sqlite3.connect(DB_NAME)
    cur  = conn.cursor()

    # テーブルが存在するか確認
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='survey_responses'")
    if cur.fetchone() is None:
        conn.close()
        return None   # まだ一件も回答なし

    cur.execute('SELECT COUNT(*) FROM survey_responses')
    total = cur.fetchone()[0]
    if total == 0:
        conn.close()
        return None

    def count_col(col, options):
        """指定カラムの各選択肢の件数を辞書で返す"""
        cur.execute(f'SELECT {col}, COUNT(*) FROM survey_responses GROUP BY {col}')
        raw = {r[0]: r[1] for r in cur.fetchall()}
        return {k: raw.get(k, 0) for k in options}

    def likert_stats(col):
        """1〜5 のリッカート項目の分布と平均を返す"""
        cur.execute(
            f'SELECT {col}, COUNT(*) FROM survey_responses WHERE {col} IS NOT NULL GROUP BY {col}')
        raw = {r[0]: r[1] for r in cur.fetchall()}
        dist = [raw.get(i, 0) for i in range(1, 6)]   # index 0 = score 1
        answered = sum(dist)
        avg = (sum((i+1)*dist[i] for i in range(5)) / answered) if answered else 0
        return {'dist': dist, 'avg': round(avg, 2), 'answered': answered}

    cur.execute(
        "SELECT q7_comment FROM survey_responses WHERE q7_comment != '' AND q7_comment IS NOT NULL")
    comments = [r[0] for r in cur.fetchall()]

    cur.execute('SELECT created_at, concept, q1_relevance, q2_ranking, '
                'q3_sbert_satis, q4_llm_satis, q5_reason_helpful, q6_prefer, q7_comment '
                'FROM survey_responses ORDER BY id')
    rows = cur.fetchall()

    result = {
        'total':    total,
        'q1':       count_col('q1_relevance', ['embedding', 'llm', 'equal', 'neither']),
        'q2':       count_col('q2_ranking',   ['embedding', 'llm', 'equal']),
        'q3':       likert_stats('q3_sbert_satis'),
        'q4':       likert_stats('q4_llm_satis'),
        'q5':       likert_stats('q5_reason_helpful'),
        'q6':       count_col('q6_prefer', ['embedding', 'llm', 'both', 'neither']),
        'comments': comments,
        'rows':     rows,
    }
    conn.close()
    return result


def save_survey(form):
    conn = sqlite3.connect(DB_NAME)
    cur  = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS survey_responses (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at        TEXT,
            concept           TEXT,
            q1_relevance      TEXT,     -- 推薦がコンセプトに合っていたのはどちらか
            q2_ranking        TEXT,     -- 順位が納得できたのはどちらか
            q3_sbert_satis    INTEGER,  -- 分散表現の満足度 (1-5)
            q4_llm_satis      INTEGER,  -- LLM の満足度 (1-5)
            q5_reason_helpful INTEGER,  -- LLM の理由が参考になったか (1-5)
            q6_prefer         TEXT,     -- 使いたい手法
            q7_comment        TEXT      -- 自由記述
        )
    ''')
    cur.execute('''
        INSERT INTO survey_responses (
            created_at, concept,
            q1_relevance, q2_ranking,
            q3_sbert_satis, q4_llm_satis, q5_reason_helpful,
            q6_prefer, q7_comment
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now().isoformat(timespec='seconds'),
        form.get('concept', ''),
        form.get('q1_relevance'),
        form.get('q2_ranking'),
        _to_int(form.get('q3_sbert')),
        _to_int(form.get('q4_llm')),
        _to_int(form.get('q5_reason')),
        form.get('q6_prefer'),
        (form.get('q7_comment') or '').strip(),
    ))
    conn.commit()
    conn.close()


def get_categories():
    conn = sqlite3.connect(DB_NAME)
    cur  = conn.cursor()
    cur.execute('SELECT id, name FROM categories')
    rows = cur.fetchall()
    conn.close()
    return [{'id': r[0], 'name': r[1]} for r in rows]


def get_category_name(category_id):
    conn = sqlite3.connect(DB_NAME)
    cur  = conn.cursor()
    cur.execute('SELECT name FROM categories WHERE id = ?', (category_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def get_concepts(category_id):
    conn = sqlite3.connect(DB_NAME)
    cur  = conn.cursor()
    cur.execute(
        'SELECT concept_text FROM concepts WHERE category_id = ?',
        (category_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]


if __name__ == '__main__':
    app.run()