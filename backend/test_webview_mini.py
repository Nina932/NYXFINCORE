import sys
import os
try:
    with open("webview_test.log", "w") as f:
        f.write(f"sys.executable: {sys.executable}\n")
        f.write(f"frozen: {getattr(sys, 'frozen', False)}\n")
        f.write(f"cwd: {os.getcwd()}\n")
        import webview
        f.write("webview imported OK\n")
        window = webview.create_window("Test", "https://www.google.com", width=400, height=300)
        f.write("window created\n")
        webview.start(gui="edgechromium")
        f.write("done\n")
except Exception as e:
    with open("webview_test.log", "a") as f:
        f.write(f"ERROR: {e}\n")
        import traceback
        traceback.print_exc(file=f)
