@echo off
echo "Installing dependencies..."
pip install -r epiccli_ui/requirements.txt
pip install pyinstaller pillow
echo "Converting icon..."
python -c "from PIL import Image; img = Image.open('epiccli_ui/static/logo2.png'); img.save('icon.ico')"
echo "Building executable..."
pyinstaller --onefile --windowed --name "epiccli-ui" --icon="icon.ico" --add-data "epiccli_ui/templates;templates" --add-data "epiccli_ui/static;static" epiccli/ui.py
