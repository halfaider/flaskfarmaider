import sys
import subprocess

try:
    __import__('google_auth_oauthlib')
except:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', 'google-auth-oauthlib'])
