#!/usr/bin/env python3
# SwitchBot 温湿度計データ閲覧 Web アプリケーション (sbmview)
# Flask を使用してデータベースのデータをブラウザで表示します。

from flask import Flask, render_template, jsonify
import sqlite3
import os
from datetime import datetime, timedelta
import tomllib
from dateutil.relativedelta import relativedelta
import calendar

app = Flask(__name__)
# データベースの絶対パスを取得
DB_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "sbmview_data.db")
CONFIG_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.toml")

def get_db_connection():
    """データベースへの接続を確立します。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    """メインダッシュボード画面を表示します。"""
    conn = get_db_connection()
    try:
        # 設定ファイルから表示順序を取得
        with open(CONFIG_PATH, "rb") as f:
            config = tomllib.load(f)
            order_ids = config.get("order_device_ids", [])
    except Exception:
        order_ids = []

    if not order_ids:
        conn.close()
        return "Please set order_device_ids in config.toml", 400

    # order_ids に含まれるデバイスの最新データを取得
    placeholders = ','.join(['?'] * len(order_ids))
    latest_data_raw = conn.execute(f'''
        SELECT s1.* 
        FROM sensor_data s1
        INNER JOIN (
            SELECT device_id, MAX(timestamp) as max_ts
            FROM sensor_data
            GROUP BY device_id
        ) s2 ON s1.device_id = s2.device_id AND s1.timestamp = s2.max_ts
        WHERE s1.device_id IN ({placeholders})
    ''', order_ids).fetchall()

    # 設定された順序に従ってデータを並び替え
    device_map = {d['device_id']: d for d in latest_data_raw}
    latest_data = []
    for idx, did in enumerate(order_ids):
        if did in device_map:
            d = dict(device_map[did])
            d['order_index'] = idx + 1
            latest_data.append(d)

    # 各デバイスの過去24時間の履歴データを取得 (インデックス画面のミニグラフ用)
    history = {}
    now = datetime.now()
    start_time = (now - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')

    for device in latest_data:
        did = device['device_id']
        rows = conn.execute('''
            SELECT timestamp, temperature, humidity 
            FROM sensor_data 
            WHERE device_id = ? AND timestamp >= ?
            ORDER BY timestamp ASC
        ''', (did, start_time)).fetchall()
        
        history[did] = {
            'points': [{'x': row['timestamp'], 'y_temp': row['temperature'], 'y_humi': row['humidity']} for row in rows],
            'start': start_time,
            'end': now.strftime('%Y-%m-%d %H:%M:%S')
        }
    
    conn.close()
    return render_template('index.html', devices=latest_data, history=history)

def get_date_range(base_date_str, scale):
    """
    指定された基準日とスケールから、データの取得範囲（開始日時と終了日時）を計算します。
    scale: 1=1日, 2=3日, 3=1週間, 4=1ヶ月, 5=3ヶ月, 6=1年
    """
    base_date = datetime.strptime(base_date_str, '%Y%m%d')
    
    if scale == 1: # 1日分
        start = base_date.replace(hour=0, minute=0, second=0)
        end = start + timedelta(days=1)
    elif scale == 2: # 3日分 (基準日を含む過去3日間)
        start = base_date - timedelta(days=2)
        end = (base_date + timedelta(days=1)).replace(hour=0, minute=0, second=0)
    elif scale == 3: # 1週間分 (基準日を含む過去7日間)
        start = base_date - timedelta(days=6)
        end = (base_date + timedelta(days=1)).replace(hour=0, minute=0, second=0)
    elif scale == 4: # 1ヶ月分 (基準日の月の初めから翌月の初めまで)
        start = base_date.replace(day=1, hour=0, minute=0, second=0)
        end = start + relativedelta(months=1)
    elif scale == 5: # 3ヶ月分 (基準日の2ヶ月前から翌月の初めまで)
        # 基準月の月初から2ヶ月前へ
        current_month_start = base_date.replace(day=1, hour=0, minute=0, second=0)
        start = current_month_start - relativedelta(months=2)
        end = current_month_start + relativedelta(months=1)
    elif scale == 6: # 1年分 (基準日の年の年初から翌年の年初まで)
        start = datetime(base_date.year, 1, 1)
        end = datetime(base_date.year + 1, 1, 1)
    else:
        start = base_date.replace(hour=0, minute=0, second=0)
        end = start + timedelta(days=1)
        
    return start, end

@app.route('/detail')
def detail():
    """詳細グラフ画面を表示します。"""
    from flask import request
    
    # クエリパラメータの取得とバリデーション
    try:
        order_index = int(request.args.get('device', 1))
    except (TypeError, ValueError):
        order_index = 1
    
    scale = int(request.args.get('scale', 1))
    if scale not in range(1, 7): scale = 1
    
    type_id = int(request.args.get('type', 1))
    if type_id not in range(1, 4): type_id = 1
    
    try:
        expanddetail = int(request.args.get('expanddetail', 0))
    except (TypeError, ValueError):
        expanddetail = 0
    
    date_str = request.args.get('date')
    if not date_str:
        date_str = datetime.now().strftime('%Y%m%d')
    
    # 設定ファイルからデバイスIDを特定
    try:
        with open(CONFIG_PATH, "rb") as f:
            config = tomllib.load(f)
            order_ids = config.get("order_device_ids", [])
    except Exception:
        order_ids = []

    if not order_ids or order_index > len(order_ids):
        return "Device not found in order_device_ids", 404
    
    device_id = order_ids[order_index - 1]

    conn = get_db_connection()
    # デバイス名の取得
    device = conn.execute('SELECT device_name FROM sensor_data WHERE device_id = ? ORDER BY timestamp DESC LIMIT 1', (device_id,)).fetchone()
    if not device:
        conn.close()
        return "Device not found in database", 404
    
    # データの存在する期間を確認し、日付選択の範囲を制限する
    limits = conn.execute('SELECT MIN(timestamp), MAX(timestamp) FROM sensor_data').fetchone()
    min_ts = limits[0][:10].replace('-', '') if limits[0] else '20000101'
    max_ts = datetime.now().strftime('%Y%m%d')

    if date_str < min_ts: date_str = min_ts
    if date_str > max_ts: date_str = max_ts

    def fetch_card_data(target_date_str):
        """指定された日付のグラフ用データを取得します。"""
        start, end = get_date_range(target_date_str, scale)
        
        # 短期スケール(1日〜1週間)は生データ、長期スケール(1ヶ月〜1年)は日次平均データを使用
        if scale <= 3:
            rows = conn.execute('''
                SELECT timestamp, temperature, humidity, battery FROM sensor_data 
                WHERE device_id = ? AND timestamp BETWEEN ? AND ? ORDER BY timestamp ASC
            ''', (device_id, start.strftime('%Y-%m-%d %H:%M:%S'), end.strftime('%Y-%m-%d %H:%M:%S'))).fetchall()
            points = [{'x': r['timestamp'], 'y_temp': r['temperature'], 'y_humi': r['humidity'], 'y_batt': r['battery']} for r in rows]
            avg = conn.execute('''
                SELECT AVG(temperature), AVG(humidity) FROM sensor_data 
                WHERE device_id = ? AND timestamp BETWEEN ? AND ?
            ''', (device_id, start.strftime('%Y-%m-%d %H:%M:%S'), end.strftime('%Y-%m-%d %H:%M:%S'))).fetchone()
        else:
            rows = conn.execute('''
                SELECT date, avg_temperature, max_temperature, min_temperature, avg_humidity, battery FROM daily_averages 
                WHERE device_id = ? AND date BETWEEN ? AND ? ORDER BY date ASC
            ''', (device_id, start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))).fetchall()
            points = [{
                'x': r['date'] + ' 00:00:00', 
                'y_avg': r['avg_temperature'], 
                'y_max': r['max_temperature'], 
                'y_min': r['min_temperature'], 
                'y_humi': r['avg_humidity'],
                'y_batt': r['battery']
            } for r in rows]
            avg = conn.execute('''
                SELECT AVG(avg_temperature), AVG(avg_humidity) FROM daily_averages 
                WHERE device_id = ? AND date BETWEEN ? AND ?
            ''', (device_id, start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))).fetchone()
        
        # バッテリー残量の取得
        batt_row = conn.execute('''
            SELECT battery FROM sensor_data WHERE device_id = ? AND timestamp LIKE ? AND battery IS NOT NULL ORDER BY timestamp ASC LIMIT 1
        ''', (device_id, datetime.strptime(target_date_str, '%Y%m%d').strftime('%Y-%m-%d') + '%')).fetchone()
        
        # 表示用の期間ラベル
        start_label = start.strftime('%Y/%m/%d')
        if scale <= 3:
            end_label = (end - timedelta(seconds=1)).strftime('%Y/%m/%d')
        else:
            end_label = (end - timedelta(days=1)).strftime('%Y/%m/%d')

        # 期間中の最小バッテリー残量を計算
        valid_batts = [p['y_batt'] for p in points if p['y_batt'] is not None]
        min_batt = min(valid_batts) if valid_batts else None

        return {
            'date_label': target_date_str,
            'start': start.strftime('%Y-%m-%d %H:%M:%S'),
            'end': end.strftime('%Y-%m-%d %H:%M:%S'),
            'start_label': start_label,
            'end_label': end_label,
            'points': points,
            'avg_temp': round(avg[0], 2) if avg[0] else None,
            'avg_humi': round(avg[1], 2) if avg[1] else None,
            'battery': batt_row[0] if batt_row else None,
            'min_battery': min_batt
        }

    # メインのカードデータ
    cards = [fetch_card_data(date_str)]
    
    # 比較用データの取得
    if type_id == 2: # 前期間と比較
        base_date = datetime.strptime(date_str, '%Y%m%d')
        if scale == 1: prev = base_date - timedelta(days=1)
        elif scale == 2: prev = base_date - timedelta(days=3)
        elif scale == 3: prev = base_date - timedelta(days=7)
        elif scale == 4: prev = base_date - relativedelta(months=1)
        elif scale == 5: prev = base_date - relativedelta(months=3)
        elif scale == 6: prev = base_date - relativedelta(years=1)
        cards.append(fetch_card_data(prev.strftime('%Y%m%d')))
    elif type_id == 3: # 前年と比較
        prev = datetime.strptime(date_str, '%Y%m%d') - relativedelta(years=1)
        cards.append(fetch_card_data(prev.strftime('%Y%m%d')))

    # デバイスの現在の（最新の）バッテリー残量を取得
    current_battery_row = conn.execute('''
        SELECT battery FROM sensor_data 
        WHERE device_id = ? AND battery IS NOT NULL 
        ORDER BY timestamp DESC LIMIT 1
    ''', (device_id,)).fetchone()
    current_battery = current_battery_row[0] if current_battery_row else None

    conn.close()
    return render_template('detail.html', 
                           order_index=order_index,
                           device_id=device_id,
                           device_name=device['device_name'], 
                           scale=scale, 
                           type_id=type_id, 
                           date=date_str,
                           min_date=min_ts,
                           max_date=max_ts,
                           cards=cards,
                           current_battery=current_battery,
                           expanddetail=expanddetail)


@app.route('/sw.js')
def service_worker():
    """サービスワーカーをサイトのルートスコープで配信します。"""
    response = app.send_static_file('sw.js')
    response.headers['Service-Worker-Allowed'] = '/'
    return response

@app.route('/manifest.json')
def manifest():
    """Web App Manifest を配信します。"""
    return app.send_static_file('manifest.json')


if __name__ == '__main__':
    # config.toml からホストとポート番号を読み込む
    try:
        with open(CONFIG_PATH, "rb") as f:
            config = tomllib.load(f)
            host = config.get("host", "127.0.0.1")
            port = config.get("port", 56780)
    except Exception as e:
        print(f"Error loading config.toml: {e}")
        host = "127.0.0.1"
        port = 56780
    
    # Flask アプリケーションの起動
    app.run(host=host, port=port)
