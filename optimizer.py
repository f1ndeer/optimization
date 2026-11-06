import sys
import ctypes
from core import is_admin, load_config
from main import OptimizerApp

if __name__ == "__main__":
    if is_admin():
        cfg = load_config()
        app = OptimizerApp(cfg)
        app.mainloop()
    else:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(f'"{a}"' for a in sys.argv), None, 1
        )
