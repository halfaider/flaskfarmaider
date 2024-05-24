import sys
import subprocess

try:
    import watchdog
except:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-U', 'watchdog'])