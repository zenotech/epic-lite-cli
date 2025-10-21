import os
import sys
import webview
import threading
import requests
import argparse
from epiccli_ui.app import app

class Api:
    def __init__(self, window):
        self.window = window

    def save_file_dialog(self, filename):
        return self.window.create_file_dialog(webview.FileDialog.SAVE, save_filename=filename)

    def download_file(self, url, path):
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            with open(path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return {"status": "success", "path": path}
        except Exception as e:
            print(f"Download failed: {e}")
            return {"status": "error", "message": str(e)}

def main():
    parser = argparse.ArgumentParser(description='EPIC-UI')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode.')
    args = parser.parse_args()

    # When running as a bundled executable, the paths to templates and static folders need to be adjusted.
    if getattr(sys, 'frozen', False):
        template_folder = os.path.join(sys._MEIPASS, 'templates')
        static_folder = os.path.join(sys._MEIPASS, 'static')
        app.template_folder = template_folder
        app.static_folder = static_folder

    t = threading.Thread(target=app.run, kwargs={'host': '127.0.0.1', 'port': 2395})
    t.daemon = True
    t.start()

    window = webview.create_window('EPIC-UI', 'http://127.0.0.1:2395', width=1200, height=800, text_select=True)
    api = Api(window)
    window.expose(api.save_file_dialog)
    window.expose(api.download_file)
    webview.start(debug=args.debug)

if __name__ == '__main__':
    main()
