import requests
import time
from parser import Parser

BASE_URL = 'http://hw1.alexbers.com'
session = requests.Session()
session.cookies.set("user", "c4f6ff551fe6b8e282156c31e9270ab5")

parser = Parser(session, BASE_URL)
response = session.get(BASE_URL)

while True:
    print(f"Текущий статус: {response.status_code}")
    if "секрет" in response.text.lower() or "secret" in response.text.lower():
        print("Финальный результат:")
        print(response.text)
        break

    response = parser.parse(response)