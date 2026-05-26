#!/usr/bin/env python3
# SwitchBot API から最新データを取得し、データベースを更新するスクリプト (monitor.py)
# cron 等で定期実行（例：5分おき）されることを想定しています。
# Copyright 20260526a Hiroaki GOTO as GORRY

import time
import hashlib
import hmac
import base64
import uuid
import tomllib
import requests
import sqlite3
import os
from dotenv import load_dotenv

# 温湿度データを持つ SwitchBot デバイスタイプのリスト
SENSOR_DEVICE_TYPES = [
    "Meter", 
    "MeterPlus", 
    "WoIOSensor", 
    "Hub 2", 
    "MeterPro(CO2)", 
    "WoMeSensor"
]

def get_auth_headers(token, secret):
    """
    SwitchBot API v1.1 で必要な認証ヘッダーを生成します。
    Token と Secret を使用して HMAC-SHA256 署名を作成します。
    """
    nonce = str(uuid.uuid4())
    t = str(int(round(time.time() * 1000)))
    string_to_sign = f"{token}{t}{nonce}"

    sign = base64.b64encode(hmac.new(
        secret.encode('utf-8'),
        msg=string_to_sign.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest()).decode('utf-8').upper()

    return {
        "Authorization": token,
        "sign": sign,
        "nonce": nonce,
        "t": t,
        "Content-Type": "application/json; charset=utf8"
    }

def init_db(db_path):
    """
    データベースの初期化とテーブル作成を行います。
    テーブルが存在しない場合は作成し、古いバージョンからのアップグレード（カラム追加）も行います。
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 生データ保存用テーブル
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT (DATETIME('now', 'localtime')),
            device_id TEXT,
            device_name TEXT,
            temperature REAL,
            humidity INTEGER,
            battery INTEGER
        )
    ''')
    
    # 日次集計データ用テーブル (グラフの長期表示を高速化するため)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_averages (
            date TEXT,
            device_id TEXT,
            device_name TEXT,
            avg_temperature REAL,
            max_temperature REAL,
            min_temperature REAL,
            avg_humidity REAL,
            battery INTEGER,
            PRIMARY KEY (date, device_id)
        )
    ''')
    
    # 既存の古いテーブルに battery カラム等がない場合の補填
    try:
        cursor.execute("ALTER TABLE sensor_data ADD COLUMN battery INTEGER")
    except sqlite3.OperationalError:
        pass
        
    for col in ["battery", "max_temperature", "min_temperature"]:
        try:
            cursor.execute(f"ALTER TABLE daily_averages ADD COLUMN {col} REAL")
        except sqlite3.OperationalError:
            pass
            
    conn.commit()
    return conn

def main():
    """メイン処理: デバイス一覧取得 -> 各デバイスのステータス取得 -> DB保存"""
    # .env ファイルから環境変数をロード
    load_dotenv()

    dir_path = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(dir_path, "config.toml")
    db_path = os.path.join(dir_path, "sbmview_data.db")

    # 設定ファイルの読み込み
    try:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
    except FileNotFoundError:
        config = {}

    # 認証情報の取得 (環境変数を優先)
    token = os.getenv("SWITCHBOT_TOKEN") or config.get("token")
    secret = os.getenv("SWITCHBOT_SECRET") or config.get("secret")
    exclude_ids = config.get("exclude_device_ids", [])
    order_ids = config.get("order_device_ids", [])

    if not token or not secret or "YOUR_" in str(token) or "YOUR_" in str(secret):
        print("Error: SWITCHBOT_TOKEN and SWITCHBOT_SECRET must be set in .env or config.toml")
        return

    headers = get_auth_headers(token, secret)
    
    # 1. デバイス一覧を取得して対象センサーを特定
    devices_url = "https://api.switch-bot.com/v1.1/devices"
    try:
        res = requests.get(devices_url, headers=headers, timeout=10)
        res.raise_for_status()
    except Exception as e:
        print(f"Failed to get devices: {e}")
        return
    
    device_list = res.json().get("body", {}).get("deviceList", [])
    # 対象: 温湿度計タイプかつ、order_ids に含まれており、exclude_ids に含まれていないもの
    sensors = [
        d for d in device_list 
        if d.get("deviceType") in SENSOR_DEVICE_TYPES 
        and d["deviceId"] in order_ids 
        and d["deviceId"] not in exclude_ids
    ]

    if not sensors:
        print("No target sensor devices found in order_device_ids.")
        return

    # 設定された順序 (order_ids) に基づいてソート
    sensors.sort(key=lambda d: order_ids.index(d["deviceId"]))

    # 2. データベース接続
    conn = init_db(db_path)
    cursor = conn.cursor()

    # 3. 各センサーの現在のステータスを取得して保存
    for sensor in sensors:
        device_id = sensor["deviceId"]
        device_name = sensor["deviceName"]
        
        status_url = f"https://api.switch-bot.com/v1.1/devices/{device_id}/status"
        try:
            s_res = requests.get(status_url, headers=headers, timeout=10)
            s_res.raise_for_status()
        except Exception as e:
            print(f"Failed to get status for {device_name}: {e}")
            continue
            
        body = s_res.json().get("body", {})
        temp = body.get("temperature")
        humi = body.get("humidity")
        batt = body.get("battery")

        # 正常なデータ（湿度が 0 より大きい）場合のみ保存
        if temp is not None and humi is not None and humi > 0:
            # 生データの挿入
            cursor.execute(
                "INSERT INTO sensor_data (device_id, device_name, temperature, humidity, battery) VALUES (?, ?, ?, ?, ?)",
                (device_id, device_name, temp, humi, batt)
            )
            
            # 日次集計テーブルの更新 (当日の平均・最大・最小を再計算)
            # バッテリーは「その日の最初に見つかった値」をその日の代表値とする
            cursor.execute('''
                INSERT OR REPLACE INTO daily_averages (date, device_id, device_name, avg_temperature, max_temperature, min_temperature, avg_humidity, battery)
                SELECT 
                    strftime('%Y-%m-%d', 'now', 'localtime') as date,
                    device_id,
                    device_name,
                    ROUND(AVG(temperature), 2),
                    ROUND(MAX(temperature), 2),
                    ROUND(MIN(temperature), 2),
                    ROUND(AVG(humidity), 2),
                    (SELECT battery FROM sensor_data s2 
                     WHERE s2.device_id = sensor_data.device_id 
                       AND s2.timestamp >= datetime('now', 'start of day', 'localtime')
                       AND s2.battery IS NOT NULL
                     ORDER BY s2.timestamp ASC LIMIT 1) as first_battery
                FROM sensor_data
                WHERE device_id = ? 
                  AND timestamp >= datetime('now', 'start of day', 'localtime')
                GROUP BY device_id
            ''', (device_id,))
            
            print(f"Logged: {device_name} -> Temp: {temp}, Humidity: {humi}, Battery: {batt}%")
        else:
            reason = "Humidity is 0" if humi == 0 else "No data available"
            print(f"Skipped: {device_name} ({reason})")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    main()
