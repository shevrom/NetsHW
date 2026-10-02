import requests
from bs4 import BeautifulSoup


class Parser:

    def __init__(self, session: requests.Session, root: str):
        self.session = session
        self.root = root

    def parse(self, response: requests.Response) -> requests.Response | None:
        print("\n" + "=" * 60)
        print(f"[ВХОДЯЩИЙ ОТВЕТ] URL: {response.url} | Status: {response.status_code}")
        print("=" * 60)

        if response.status_code != 200:
            raise RuntimeError(
                f"Сервер вернул ошибку {response.status_code}!\n"
                f"URL: {response.url}\n"
                f"Тело ответа:\n{response.text}"
            )

        soup = BeautifulSoup(response.text, "html.parser")

        try:
            next_url = self._get_next_url(soup, response.text)
        except ValueError as e:
            if "секрет" in response.text.lower() or "secret" in response.text.lower():
                print("🎉 ПОЛУЧЕН ФИНАЛЬНЫЙ ОТВЕТ:")
                print(response.text)
                return None
            raise e

        cookies = {}
        headers = {}
        params = {}
        form_data = {}
        files = {}

        tables = soup.find_all("table")
        for table in tables:
            th_tags = [th.text.strip().lower() for th in table.find_all("th")]
            rows_data = self._parse_table(table)

            if "имя файла" in th_tags or "filename" in th_tags:
                for filename, content in rows_data.items():
                    files[filename] = (filename, content.encode("utf-8"))
            elif "ключ" in th_tags and "значение" in th_tags:
                prev_text = ""
                prev_node = table.find_previous(string=True)
                while prev_node:
                    text_strip = prev_node.strip().lower()
                    if text_strip:
                        prev_text = text_strip
                        break
                    prev_node = prev_node.find_previous(string=True)

                if "cookie" in prev_text:
                    cookies.update(rows_data)
                elif "заголовки" in prev_text or "headers" in prev_text:
                    headers.update(rows_data)
                elif "параметры" in prev_text or "params" in prev_text:
                    params.update(rows_data)
                elif "формы" in prev_text or "form" in prev_text:
                    form_data.update(rows_data)

        # Сохраняем главный токен авторизации
        auth_user = self.session.cookies.get("user", "c4f6ff551fe6b8e282156c31e9270ab5")

        # Очищаем временные куки прошлых шагов
        self.session.cookies.clear()

        # Восстанавливаем токен авторизации и добавляем куки текущего шага
        self.session.cookies.set("user", auth_user)
        if cookies:
            self.session.cookies.update(cookies)

        is_post = bool(files or form_data) or "post" in response.text.lower()

        try:
            if is_post:
                kwargs = {}
                if headers:
                    kwargs["headers"] = headers
                if form_data:
                    kwargs["data"] = form_data
                if files:
                    kwargs["files"] = files
                if params:
                    kwargs["params"] = params

                print(f"[ОТПРАВКА POST] -> {next_url}")
                print(f"Headers: {headers}")
                print(f"Data: {form_data}")
                print(f"Params: {params}")
                print(f"Files: {list(files.keys())}")
                print("-" * 60)

                return self.session.post(next_url, **kwargs)
            else:
                kwargs = {}
                if headers:
                    kwargs["headers"] = headers
                if params:
                    kwargs["params"] = params

                print(f"[ОТПРАВКА GET] -> {next_url}")
                print(f"Headers: {headers}")
                print(f"Params: {params}")
                print("-" * 60)

                return self.session.get(next_url, **kwargs)

        except requests.RequestException as req_err:
            raise RuntimeError(f"Ошибка при отправке запроса на {next_url}: {req_err}") from req_err

    def _get_next_url(self, soup: BeautifulSoup, response_text: str) -> str:
        link_tag = soup.find("a")
        code_tag = soup.find("code")

        if link_tag and link_tag.get("href"):
            url = link_tag["href"]
        elif code_tag:
            url = code_tag.text.strip()
        else:
            raise ValueError(f"Не удалось найти URL/ссылку в ответе:\n{response_text}")

        return f"{self.root}{url}"

    @staticmethod
    def _parse_table(table) -> dict:
        data = {}
        rows = table.find_all("tr")[1:]
        for row in rows:
            cols = row.find_all("td")
            if len(cols) == 2:
                key = cols[0].text.strip()
                value = cols[1].text.strip()
                data[key] = value
        return data