import sys
import subprocess

try:
    __import__('watchdog')
except:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-U', 'watchdog'])

try:
    __import__('yaml')
except:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-U', 'pyyaml'])

try:
    __import__('requests')
except:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-U', 'requests'])
