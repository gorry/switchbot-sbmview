#!/usr/bin/env python3
# SwitchBot API からデバイス一覧を取得するスクリプト (get_devices.py)
# 自分のアカウントに登録されているデバイスの名前、ID、タイプを確認するために使用します。
# Copyright 20260526a Hiroaki GOTO as GORRY

import time
import hashlib
import hmac
import base64
import uuid
import tomllib
import requests
import os
from dotenv import load_dotenv

def get_auth_headers(token, secret):
    """SwitchBot API v1.1 の認証ヘッダーを生成します。"""
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

def main():
    """メイン処理: API を叩いてデバイス情報を表示します。"""
    # .env ファイルから環境変数をロード
    load_dotenv()

    # 設定ファイルの読み込み
    dir_path = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(dir_path, "config.toml")
    try:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
    except FileNotFoundError:
        config = {}

    # 認証情報の取得 (環境変数を優先)
    token = os.getenv("SWITCHBOT_TOKEN") or config.get("token")
    secret = os.getenv("SWITCHBOT_SECRET") or config.get("secret")

    if not token or not secret or "YOUR_" in str(token) or "YOUR_" in str(secret):
        print("Error: SWITCHBOT_TOKEN and SWITCHBOT_SECRET must be set in .env or config.toml")
        return

    # API エンドポイント
    url = "https://api.switch-bot.com/v1.1/devices"
    headers = get_auth_headers(token, secret)

    # リクエストの送信
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"HTTP Request failed: {e}")
        return

    data = response.json()
    if data.get("statusCode") == 100:
        print("--- Registered Devices ---")
        # デバイスリストの表示
        for device in data["body"]["deviceList"]:
            print(f"Name: {device['deviceName']}")
            print(f"  ID:   {device['deviceId']}")
            print(f"  Type: {device['deviceType']}")
            print("-" * 20)
            
        # 赤外線リモコンデバイスの表示
        remote_list = data["body"].get("infraredRemoteList", [])
        if remote_list:
            print("--- Remote Devices ---")
            for remote in remote_list:
                print(f"Name: {remote['deviceName']}")
                print(f"  ID:   {remote['deviceId']}")
                print(f"  Type: {remote['remoteType']}")
                print("-" * 20)
    else:
        print(f"API Error: {data.get('message')}")

if __name__ == "__main__":
    main()
