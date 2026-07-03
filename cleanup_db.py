#!/usr/bin/env python3
# SwitchBot データベース重複クリーンアップスクリプト (cleanup_db.py)
# データベース内の重複する10分枠データを統合し、マージします。
# Copyright 20260704 Hiroaki GOTO as GORRY

import sqlite3
import shutil
import os
from datetime import datetime

def main():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    db_path = os.path.join(dir_path, "sbmview_data.db")
    backup_path = os.path.join(dir_path, "sbmview_data.db.bak")

    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        return

    # 1. バックアップの作成
    print(f"Creating backup of {db_path} to {backup_path}...")
    try:
        shutil.copy2(db_path, backup_path)
    except Exception as e:
        print(f"Failed to create backup: {e}")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 2. 全データの取得
    print("Fetching all sensor data...")
    try:
        cur.execute("SELECT timestamp, device_id, device_name, temperature, humidity, battery FROM sensor_data")
        rows = cur.fetchall()
    except sqlite3.OperationalError as e:
        print(f"Failed to read from database: {e}")
        conn.close()
        return
        
    print(f"Fetched {len(rows)} records.")

    # 3. データのマージ
    merged = {}
    for timestamp_str, device_id, device_name, temp, humi, batt in rows:
        try:
            dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M')
            except ValueError:
                print(f"Skipping record with invalid timestamp: {timestamp_str}")
                continue
                
        # 10分単位に丸める
        rounded_minute = (dt.minute // 10) * 10
        dt_rounded = dt.replace(minute=rounded_minute, second=0, microsecond=0)
        time10 = dt_rounded.strftime('%Y-%m-%d %H:%M:%S')
        
        key = (time10, device_id)
        is_csv_data = (dt.second == 0) # 秒が00のものはCSVからインポートした実データとみなす
        
        if key not in merged:
            merged[key] = {
                'device_name': device_name,
                'temp': temp,
                'humi': humi,
                'batt': batt,
                'is_csv': is_csv_data
            }
        else:
            existing = merged[key]
            # バッテリー情報のマージ (非NULLな方を優先)
            if existing['batt'] is None and batt is not None:
                existing['batt'] = batt
                
            # 温度・湿度のマージ (秒数が00のCSV実データを優先)
            if not existing['is_csv'] and is_csv_data:
                existing['temp'] = temp
                existing['humi'] = humi
                existing['device_name'] = device_name
                existing['is_csv'] = True

    print(f"Merged into {len(merged)} unique 10-minute records (reduced from {len(rows)}).")

    # 4. データベースの更新 (トランザクション内)
    try:
        print("Writing merged data back to database...")
        # テーブルクリア
        cur.execute("DELETE FROM sensor_data")
        
        # 挿入データ準備
        data_to_insert = [
            (time10, device_id, info['device_name'], info['temp'], info['humi'], info['batt'])
            for (time10, device_id), info in merged.items()
        ]
        
        cur.executemany(
            "INSERT INTO sensor_data (timestamp, device_id, device_name, temperature, humidity, battery) VALUES (?, ?, ?, ?, ?, ?)",
            data_to_insert
        )
        
        # daily_averages の再計算と更新
        print("Recalculating daily averages...")
        cur.execute("DELETE FROM daily_averages")
        cur.execute('''
            INSERT INTO daily_averages (date, device_id, device_name, avg_temperature, max_temperature, min_temperature, avg_humidity, battery)
            SELECT 
                strftime('%Y-%m-%d', timestamp) as date,
                device_id,
                device_name,
                ROUND(AVG(temperature), 2),
                ROUND(MAX(temperature), 2),
                ROUND(MIN(temperature), 2),
                ROUND(AVG(humidity), 2),
                (SELECT battery FROM sensor_data s2 
                 WHERE s2.device_id = sensor_data.device_id 
                   AND strftime('%Y-%m-%d', s2.timestamp) = strftime('%Y-%m-%d', sensor_data.timestamp)
                   AND s2.battery IS NOT NULL
                 ORDER BY s2.timestamp ASC LIMIT 1) as first_battery
            FROM sensor_data
            GROUP BY date, device_id
        ''')
        
        conn.commit()
        print("Migration completed successfully!")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        print("Restoring database from backup...")
        try:
            shutil.copy2(backup_path, db_path)
            print("Restore completed.")
        except Exception as re:
            print(f"Failed to restore: {re}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
