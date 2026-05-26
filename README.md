# sbmview
SwitchBot Meter View `sbmview`

## これはなに？

`sbmview`は、SwitchBot温湿度計のデータを取得・蓄積するサービスと、それをブラウザで閲覧するためのWebアプリケーションのパッケージです。

## 特徴

- Android/iOS用SwitchBot公式アプリとの連携。
- SwitchBot APIを使用したデータの自動取得と、SQLiteによるデータ蓄積。
- 24時間/3日/1週間/1ヶ月/3ヶ月/1年のグラフ表示。

## 動作環境

- FreeBSD または Linux
- Python 3.11 以上
- SQLite
- SwitchBot温湿度計 （SwitchBot Hub経由でクラウド連携が必要）
- SwitchBot API 認証情報 (Token, Secret)




## 各スクリプトの役割

- `sbmview.py`: Webサーバー本体
- `monitor.py`: SwitchBot APIから最新データを取得しDBに保存
- `import_csv.py`: 公式アプリからエクスポートしたCSVデータのインポート
- `get_devices.py`: アカウントに紐付けられたデバイスID一覧の取得




## セットアップ手順

### SwitchBot API キーの取得

Android/iOS用SwitchBot公式アプリの「設定」>「アプリバージョン」を 10 回タップして「開発者向けオプション」を出し、Token と Secret を取得してください。




### インストール

```bash
./setup.sh
```

`./setup.sh` を実行すると、以下の処理が行われます：

- Python 仮想環境 (`venv`) の作成
- 依存ライブラリ (`requirements.txt`) のインストール
- `config.toml` の生成
- OS に合わせた起動設定ファイル (`sbmview.rc` または `sbmview.service`) の生成




### 設定

#### API 認証情報
`.env` ファイルを作成し、取得した API キーを記述します。

```env
SWITCHBOT_TOKEN=your_token_here
SWITCHBOT_SECRET=your_secret_here
```

#### デバイス一覧の取得
`get_devices.py` を実行して、お使いのSwitchBot公式アプリに登録されているデバイス一覧を取得します。
`Type: Meter`となっている機器が、本アプリの対象機器となります。

```bash
> ./venv/bin/python3 get_devices.py
Device List:
Name: 自宅居間, ID: XXXXXXXXXXXX, Type: Meter
Name: 自室, ID: XXXXXXXXXXXX, Type: Meter
Name: 自宅外, ID: XXXXXXXXXXXX, Type: Meter
Name: Hub Mini 自宅, ID: XXXXXXXXXXXX, Type: Hub Mini
```

#### アプリケーション設定
`config.toml` を編集して、表示したいデバイスの ID や待ち受けポートを設定します。

```toml
host = "127.0.0.1"  # 外部から直接アクセスする場合は "0.0.0.0"
port = 56780

order_device_ids = [
    "XXXXXXXXXXXX", # 表示したいデバイスのIDを順に記述
]
```




### データ取得と蓄積の設定

`monitor.py`を実行することで、1回分のデータ取得と蓄積が行われます。cronで、10分おきに起動するよう設定することを推奨します。

```crontab
*/10 * * * * cd /sbmview_path/ && ./venv/bin/python3 ./monitor.py
```




### サービスの起動設定

以下の設定を行うことで、Webアプリケーションの起動が行われます。

#### FreeBSD の場合
```bash
sudo cp sbmview.rc /usr/local/etc/rc.d/sbmview
sudo sysrc sbmview_enable=YES
sudo service sbmview start
```

#### Linux の場合
```bash
sudo cp sbmview.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sbmview
```

リバースプロキシが使用できる場合は、`http://127.0.0.1:56780/` を対象にしておくと便利です。apacheでの設定を例に示します。

```apache
<Location />
  ProxyPass http://127.0.0.1:56780/
  ProxyPassReverse http://127.0.0.1:56780/
</Location>
```


## Webアプリケーションの使用方法

Webブラウザを起動し、URLとして以下を入力します。

```www
http://your_server_address:56780/
```

メイン画面（ダッシュボード）が表示され、登録したデバイスの数だけカードが表示され、それぞれに現在状況が表示されます。

### ダッシュボードのカード

ダッシュボードのカードには、以下の情報が表示されます。

- デバイス名。クリックすると、デバイスの詳細が表示されます。
- バッテリー量。20%以下になると赤く表示されます。
- 温度。現在の気温です。
- 湿度。現在の湿度です。
- グラフ。過去24時間の推移などが表示されます。
  - 温度。赤線で表示されます。
  - 湿度。青い破線で表示されます。
  - 期間内の最高・最低温度。グラフの右上隅と右下隅に表示されます。
  - 期間内の最高・最低湿度。グラフの左上隅と左下隅に表示されます。

カードのデバイスをタップすると、そのデバイスの詳細な情報が表示されます。

### 詳細画面

ダッシュボードのカードのデバイス名をタップすると、そのデバイスの詳細な情報が表示されます。

- [戻る]ボタン。ダッシュボードに戻ります。
- デバイス名。デバイスIDとともに表示されます。
- 現在のバッテリー量。20%以下になると赤く表示されます。
- 日付。`[<]`または`[>]`ボタンでページ移動が可能です。またカレンダーで直接日付を指定することもできます。
- 期間ボタン。「1日間/3日間/1週間/1ヶ月/3ヶ月/1年」から選ぶことができます。「1ヶ月未満」と「1ヶ月以上」で、グラフの内容が変化します。
- カード表示ボタン。「当日のみ」はカードが1枚だけ表示されます。「前期と比較/前年と比較」はカードが2枚表示され、比較することができます。

### 詳細画面のカード（1ヶ月未満）

詳細画面（1ヶ月未満）のカードには、以下の情報が表示されます。

- 表示期間。グラフの左端と右端の期間が2日以上ある場合、その期間が表示されます。
- 最小バッテリー量。期間内でのバッテリー量の最小値が表示されます。
- グラフ。指定期間の推移などが表示されます。
  - 温度。赤線で表示されます。
  - 湿度。青い破線で表示されます。
  - 平均気温。期間内の平均気温がグレーの点線で表示されます。
  - 期間内のバッテリー量。緑の点線で表示されます。
  - 最高・最低温度。グラフの右上隅と右下隅に表示されます。
  - 最高・最低湿度。グラフの左上隅と左下隅に表示されます。

### 詳細画面のカード（1ヶ月以上）

詳細画面（1ヶ月以上）のカードには、以下の情報が表示されます。

- 表示期間。グラフの左端と右端の期間が2日以上ある場合、その期間が表示されます。
- 最小バッテリー量。期間内でのバッテリー量の最小値が表示されます。
- グラフ。指定期間の推移などが表示されます。
  - 温度。その日の最高気温が赤線で、最低気温が青線で、平均気温がグレーの点線で表示されます。
  - 湿度。青い破線で表示されます。
  - 期間内のバッテリー量。緑の点線で表示されます。
  - 期間内の最高・最低温度。グラフの右上隅と右下隅に表示されます。
  - 期間内の最高・最低湿度。グラフの左上隅と左下隅に表示されます。




## ライセンス

Copyright 20260526a Hiroaki GOTO as GORRY

本プログラムはMIT Licenseに沿って利用・改変・再配布を行うことができます。
本プログラムの実行結果について、作者は一切の責任を負いません。

## 連絡先

バグ報告や改善提案は、このリポジトリのIssuesまでお願いします。

[https://github.com/gorry/switchbot-sbmview](https://github.com/gorry/switchbot-sbmview)
