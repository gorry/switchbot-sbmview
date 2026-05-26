#!/bin/sh

# SwitchBot Meter View (sbmview) セットアップスクリプト
# FreeBSD と Linux の両方に対応しています。

set -e

echo "Starting sbmview setup..."

# 1. 仮想環境 (venv) の構築
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
else
    echo "Virtual environment already exists."
fi

# 2. 依存ライブラリのインストール
echo "Installing requirements..."
./venv/bin/pip install -r requirements.txt

# 3. 設定ファイルの準備
if [ ! -f "config.toml" ]; then
    echo "Creating config.toml from example..."
    cp config.toml.example config.toml
    echo "Done. Please edit config.toml with your device IDs later."
fi

# 4. OS判別とサービス設定ファイルの生成
OS=$(uname -s)
INSTALL_DIR=$(pwd)
CURRENT_USER=$(whoami)

echo "Detected OS: $OS"
echo "Install directory: $INSTALL_DIR"
echo "Running as user: $CURRENT_USER"

case "$OS" in
    FreeBSD)
        echo "Generating FreeBSD rc.d script..."
        sed -e "s|{{INSTALL_DIR}}|$INSTALL_DIR|g" \
            -e "s|{{USER}}|$CURRENT_USER|g" \
            scripts/sbmview.rc.template > sbmview.rc
        chmod +x sbmview.rc
        echo "--------------------------------------------------------"
        echo "Generated FreeBSD startup script: 'sbmview.rc'"
        echo "To install, run the following commands:"
        echo "  sudo cp sbmview.rc /usr/local/etc/rc.d/sbmview"
        echo "  sudo sysrc sbmview_enable=YES"
        echo "  sudo service sbmview start"
        echo "--------------------------------------------------------"
        ;;
    Linux)
        echo "Generating Linux systemd service file..."
        sed -e "s|{{INSTALL_DIR}}|$INSTALL_DIR|g" \
            -e "s|{{USER}}|$CURRENT_USER|g" \
            scripts/sbmview.service.template > sbmview.service
        echo "--------------------------------------------------------"
        echo "Generated Linux service file: 'sbmview.service'"
        echo "To install, run the following commands:"
        echo "  sudo cp sbmview.service /etc/systemd/system/"
        echo "  sudo systemctl daemon-reload"
        echo "  sudo systemctl enable --now sbmview"
        echo "--------------------------------------------------------"
        ;;
    *)
        echo "Unsupported OS: $OS"
        echo "Manual setup is required."
        ;;
esac

echo "Setup process completed."
