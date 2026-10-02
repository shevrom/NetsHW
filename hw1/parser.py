import requests
from bs4 import BeautifulSoup


class Parser:

    def __init__(self, session: requests.Session, root: str):
        self.session = session
        self.root = root

    def parse(self, response: requests.Response) -> requests.Response:
        soup = BeautifulSoup(response.text, "html.parser")
        next_url = self._get_next_url(soup, response.text)

        cookies = {}
        headers = {}
        params = {}
        form_data = {}
        files = {}

        tables = soup.find_all("table")
        for table in tables:
            th_tags = [th.text.strip().lower() for th in table.find_all("th")]
            rows_data = self._parse_table(table)

            if "имя файла" in th_tags:
                for filename, content in rows_data.items():
                    files[filename] = (filename, content.encode("utf-8"))
            elif "ключ" in th_tags and "значение" in th_tags:
                prev_node = table.find_previous(string=True)
                prev_text = prev_node.strip()

                if "cookie" in prev_text:
                    cookies.update(rows_data)
                elif "заголовки" in prev_text or "headers" in prev_text:
                    headers.update(rows_data)
                elif "параметры" in prev_text or "params" in prev_text:
                    params.update(rows_data)
                elif "формы" in prev_text or "form" in prev_text:
                    form_data.update(rows_data)

        auth_user = self.session.cookies.get("user", "c4f6ff551fe6b8e282156c31e9270ab5")
        self.session.cookies.clear()

        self.session.cookies.set("user", auth_user)
        if cookies:
            self.session.cookies.update(cookies)

        is_post = bool(files or form_data) or "post" in response.text.lower()

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

            return self.session.post(next_url, **kwargs)
        else:
            kwargs = {}
            if headers:
                kwargs["headers"] = headers
            if params:
                kwargs["params"] = params

            return self.session.get(next_url, **kwargs)

    def _get_next_url(self, soup: BeautifulSoup, response_text: str) -> str:
        link_tag = soup.find("a")
        code_tag = soup.find("code")

        if link_tag and link_tag.get("href"):
            url = link_tag["href"]
        elif code_tag:
            url = code_tag.text.strip()
        else:
            raise ValueError(f"Can't find url in response:\n{response_text}")

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
