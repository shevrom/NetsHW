import requests
from parser import Parser, ParseType

BASE_URL = 'http://hw1.alexbers.com'
session = requests.Session()
session.cookies.set("user", "c4f6ff551fe6b8e282156c31e9270ab5")

parser = Parser(session, BASE_URL)
response = session.get(BASE_URL)

steps = 0
while True:
    steps += 1
    if "секрет" in response.text.lower():
        print(response.text)
        break

    response = parser.parse(response, "curl")

    if steps % 1 == 0:
        print(steps) # нужно ~286