import requests
from parser import Parser
import re
import time

BASE_URL = 'http://hw1.alexbers.com'
session = requests.Session()
session.cookies.set("user", "c4f6ff551fe6b8e282156c31e9270ab5")

parser = Parser(session, BASE_URL)
response = session.get(BASE_URL)
prev_resp = response.text

steps = 0
while True:
    try:
        time.sleep(0.1)
        steps += 1

        response = parser.parse(response, "curl")
        if "секрет" in response.text.lower():
            print(response.text)
            break

        start = response.text.find('Ш')
        step_text = response.text[start:start + 10]
        number = int(re.findall(r'\d+', step_text)[0])
        print(f"Шаг: {number}")

        if steps + 1 != number:
            print(prev_resp)
            print(response.text)
            break

        prev_resp = response.text

    except Exception as e:
        print(e)
        print(prev_resp)
        print(response.text)
