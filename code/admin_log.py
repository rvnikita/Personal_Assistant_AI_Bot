import os
import configparser
import requests


config = configparser.SafeConfigParser(os.environ)
config_path = os.path.dirname(__file__) + '/../config/' #we need this trick to get path to config folder
config.read(config_path + 'settings.ini')

def admin_log(text):
    URL = f"https://api.telegram.org/bot{config['BOT']['KEY']}/sendMessage?chat_id={config['BOT']['ADMIN_ID']}&text={text}"

    r = requests.get(url = URL)
    data = r.json()