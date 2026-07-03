#!/usr/bin/env python3
# SwitchBot 公式アプリからエクスポートした CSV データをインポートするスクリプト (import_csv.py)
# 過去のデータを SQLite データベースに一括登録し、日次集計も更新します。
# Copyright 20260526a Hiroaki GOTO as GORRY

import os
import csv
import sqlite3
from datetime import datetime, timedelta
import re

def get_device_name(cursor, device_id):
    """データベースからデバイス名を取得します。"""
    cursor.execute("SELECT DISTINCT device_name FROM sensor_data WHERE device_id=? LIMIT 1", (device_id,))
    row = cursor.fetchone()
    if row:
        return row[0]
    return "Unknown"

def import_csv(db_path, csv_path):
    """
    指定された CSV ファイルを読み込み、データをデータベースにインポートします。
    ファイル名からデバイス ID を抽出し、10分間隔のデータに補完して保存します。
    """
    # ファイル名からデバイス ID を抽出 (例: switchbot_E37BCBC02A86_20250101-20260526.csv)
    match = re.search(r'switchbot_([0-9A-F]+)_', os.path.basename(csv_path))
    if not match:
        print(f"Could not extract device ID from filename: {csv_path}")
        return
    device_id = match.group(1)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 重複登録を防ぐためのユニークインデックス作成
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_sensor_data_unique ON sensor_data (timestamp, device_id)")

    # デバイス名の特定
    device_name = get_device_name(cursor, device_id)
    if device_name == "Unknown":
        device_name = f"Device_{device_id}"
    
    print(f"Importing data for device {device_name} ({device_id}) from {csv_path}")

    # CSV ファイルの読み込み
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("No data in CSV.")
        return

    # データのパース
    parsed_rows = []
    for row in rows:
        try:
            # 形式: 2025-08-24 18:03
            dt = datetime.strptime(row['Date'], '%Y-%m-%d %H:%M')
            temp = float(row['Temperature_Celsius(℃)'])
            humi = int(row['Relative_Humidity(%)'])
            parsed_rows.append({'dt': dt, 'temp': temp, 'humi': humi})
        except (ValueError, KeyError):
            continue

    if not parsed_rows:
        print("No valid data rows found.")
        return

    # 日時順にソート
    parsed_rows.sort(key=lambda x: x['dt'])

    start_time = parsed_rows[0]['dt']
    # 10分単位の開始時刻を計算
    current_target = start_time.replace(minute=(start_time.minute // 10) * 10, second=0, microsecond=0)
    end_time = parsed_rows[-1]['dt']

    data_to_insert = []
    last_val = None
    row_idx = 0

    # 10分間隔のデータを生成（欠落部分は直前の値で補完）
    while current_target <= end_time:
        next_target = current_target + timedelta(minutes=10)
        
        found_row = None
        while row_idx < len(parsed_rows) and parsed_rows[row_idx]['dt'] < current_target:
            row_idx += 1
            
        if row_idx < len(parsed_rows) and parsed_rows[row_idx]['dt'] < next_target:
            found_row = parsed_rows[row_idx]
            last_val = found_row
        else:
            if last_val:
                found_row = last_val

        if found_row:
            data_to_insert.append((
                current_target.strftime('%Y-%m-%d %H:%M:%S'),
                device_id,
                device_name,
                found_row['temp'],
                found_row['humi'],
                None # CSV にはバッテリー情報がないため None
            ))
        
        current_target = next_target

    print(f"Prepared {len(data_to_insert)} records. Inserting into DB...")
    
    # データベースへの一括挿入 (衝突した場合はCSVの実データで上書き、バッテリーは既存値を優先)
    cursor.executemany(
        """
        INSERT INTO sensor_data (timestamp, device_id, device_name, temperature, humidity, battery)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(timestamp, device_id) DO UPDATE SET
            device_name = excluded.device_name,
            temperature = excluded.temperature,
            humidity = excluded.humidity,
            battery = COALESCE(sensor_data.battery, excluded.battery)
        """,
        data_to_insert
    )
    
    conn.commit()

    # インポートした期間の日次集計データを再計算
    dates = sorted(list(set(d[0][:10] for d in data_to_insert)))
    print(f"Updating daily averages for {len(dates)} dates...")
    
    for i, date_str in enumerate(dates):
        if (i + 1) % 50 == 0 or i == len(dates) - 1:
            print(f"Processing date {i+1}/{len(dates)}: {date_str}")
        cursor.execute('''
            INSERT OR REPLACE INTO daily_averages (date, device_id, device_name, avg_temperature, max_temperature, min_temperature, avg_humidity, battery)
            SELECT 
                ? as date,
                device_id,
                device_name,
                ROUND(AVG(temperature), 2),
                ROUND(MAX(temperature), 2),
                ROUND(MIN(temperature), 2),
                ROUND(AVG(humidity), 2),
                (SELECT battery FROM sensor_data s2 
                 WHERE s2.device_id = sensor_data.device_id 
                   AND s2.timestamp >= ? || ' 00:00:00'
                   AND s2.timestamp <= ? || ' 23:59:59'
                   AND s2.battery IS NOT NULL
                 ORDER BY s2.timestamp ASC LIMIT 1) as first_battery
            FROM sensor_data
            WHERE device_id = ? 
              AND timestamp >= ? || ' 00:00:00'
              AND timestamp <= ? || ' 23:59:59'
            GROUP BY device_id
        ''', (date_str, date_str, date_str, device_id, date_str, date_str))
    
    conn.commit()
    conn.close()
    print(f"Finished processing {csv_path}")

def main():
    """CSV ディレクトリ内のすべてのファイルを処理します。"""
    db_path = "sbmview_data.db"
    csv_dir = "csv"
    
    if not os.path.exists(csv_dir):
        print(f"Directory {csv_dir} not found.")
        return

    # csv フォルダ内の .csv ファイルをすべてインポート
    for filename in sorted(os.listdir(csv_dir)):
        if filename.endswith(".csv"):
            import_csv(db_path, os.path.join(csv_dir, filename))

if __name__ == "__main__":
    main()
