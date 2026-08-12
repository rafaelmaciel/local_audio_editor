#!/bin/bash

sudo apt install -y ffmpeg python3-venv

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

python app.py &
APP_PID=$!

echo "Iniciando Audio Editor..."

until curl -s http://127.0.0.1:5000 >/dev/null 2>&1
do
    sleep 1
done

echo "Aplicação disponível em http://127.0.0.1:5000"

xdg-open http://127.0.0.1:5000

wait $APP_PID