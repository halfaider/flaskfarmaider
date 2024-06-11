import sys
import subprocess

try:
    __import__('watchdog')
except:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-U', 'watchdog'])
