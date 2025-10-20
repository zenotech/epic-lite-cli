#!/bin/bash
echo "Installing dependencies..."
pip install -r epiccli_ui/requirements.txt
pip install pyinstaller
echo "Building executable..."
pyinstaller --onefile --windowed --name "epiccli-ui" --icon="epiccli_ui/static/logo2.png" --add-data "epiccli_ui/templates:templates" --add-data "epiccli_ui/static:static" epiccli/ui.py
