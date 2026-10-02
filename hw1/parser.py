import requests
from bs4 import BeautifulSoup


class Parser:
    def __init__(self, session: requests.Session, root: str):
        self.session = session
        self.root = root

    def parse(self, response: requests.Response) -> requests.Response | None:
        soup = BeautifulSoup(response.text, 'html.parser')
        next_url = self._get_next_url(soup, response)

        cookies = {}
        headers = {}
        params = {}
        form_data = {}
        files = {}

        tables = soup.find_all('table')
        for table in tables:
            header_node = table.find_previous(string=True)
            header = header_node.strip().lower() if header_node else ""
            data = self._parse_table(table)

            if "cookie" in header:
                cookies.update(data)
            elif "заголовки" in header:
                headers.update(data)
            elif "параметры запроса" in header:
                params.update(data)
            elif "данные формы" in header:
                form_data.update(data)
            elif "загрузите файлы" in header or "содержимое" in header:
                for filename, content in data.items():
                    files[filename] = (filename, content.encode("utf-8"))

        if cookies:
            self.session.cookies.update(cookies)

        is_post = "POST" in response.text or "загрузите файлы" in response.text.lower()
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

    def _get_next_url(self, soup: BeautifulSoup, response: requests.Response) -> str:
        link_tag = soup.find("a")
        code_tag = soup.find("code")

        if link_tag and link_tag.get('href'):
            url = link_tag['href']
        elif code_tag:
            url = code_tag.text.strip()
        else:
            raise ValueError(f"Can't find url in response:\n{response.text}")

        return f"{self.root}{url}"

    @staticmethod
    def _parse_table(table) -> dict:
        data = {}
        rows = table.find_all('tr')[1:]
        for row in rows:
            cols = row.find_all('td')
            if len(cols) == 2:
                key = cols[0].text.strip()
                value = cols[1].text.strip()
                data[key] = value
        return data
