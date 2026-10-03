import os
import re
import subprocess
import tempfile
from typing import Literal
from urllib.parse import urlencode, urljoin

import requests
from bs4 import BeautifulSoup

ParseType = Literal["py_lib", "curl"]


class Parser:

    def __init__(
            self,
            session: requests.Session,
            root: str,
            user_id: str = "c4f6ff551fe6b8e282156c31e9270ab5",
    ):
        self.session = session
        self.root = root.rstrip("/")
        self.user_id = user_id

    def parse(
            self,
            response: requests.Response,
            parse_type: ParseType = "py_lib",
    ) -> requests.Response:

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

            if "имя файла" in th_tags or "filename" in th_tags:
                for filename, content in rows_data.items():
                    files[filename] = (
                        filename,
                        content.encode("utf-8"),
                        "application/octet-stream",
                    )
            elif "ключ" in th_tags and "значение" in th_tags:
                prev_text = ""
                prev_node = table.find_previous(string=True)
                while prev_node:
                    text_strip = prev_node.strip().lower()
                    if any(
                            w in text_strip
                            for w in [
                                "cookie",
                                "куки",
                                "заголовк",
                                "header",
                                "параметр",
                                "param",
                                "форм",
                                "form",
                                "файл",
                                "file",
                            ]
                    ):
                        prev_text = text_strip
                        break
                    prev_node = prev_node.find_previous(string=True)

                if "cookie" in prev_text or "куки" in prev_text:
                    cookies.update(rows_data)
                elif "заголовк" in prev_text or "header" in prev_text:
                    headers.update(rows_data)
                elif "параметр" in prev_text or "param" in prev_text:
                    params.update(rows_data)
                elif "форм" in prev_text or "form" in prev_text:
                    form_data.update(rows_data)

        text_lower = response.text.lower()
        is_post = bool(files or form_data) or bool(
            re.search(r"\bpost[\s\-]*запрос", text_lower)
        )

        if parse_type == "py_lib":
            return self._make_pylib_request(
                url=next_url,
                headers=headers,
                cookies=cookies,
                params=params,
                form_data=form_data,
                files=files,
                is_post=is_post,
            )
        elif parse_type == "curl":
            return self._make_curl_request(
                url=next_url,
                headers=headers,
                cookies=cookies,
                params=params,
                form_data=form_data,
                files=files,
                is_post=is_post,
            )
        raise ValueError(f"Invalid parse_type: {parse_type}")

    def _get_next_url(self, soup: BeautifulSoup, response_text: str) -> str:
        # 1. Поиск конструкции "по адресу <code>...</code>"
        match = re.search(
            r"по\s+адресу\s*<code>([^<]+)</code>", response_text, re.IGNORECASE
        )
        if match:
            url = match.group(1).strip()
        else:
            # 2. Поиск ссылки <a>
            link_tag = soup.find("a")
            if link_tag and link_tag.get("href"):
                url = link_tag["href"]
            else:
                # 3. Первое совпадение <code>
                code_tag = soup.find("code")
                if code_tag:
                    url = code_tag.text.strip()
                else:
                    raise ValueError(
                        f"Can't find url in response:\n{response_text}"
                    )

        return urljoin(self.root + "/", url.lstrip("/"))

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

    def _make_pylib_request(
            self,
            url: str,
            headers: dict = None,
            cookies: dict = None,
            params: dict = None,
            form_data: dict = None,
            files: dict = None,
            is_post: bool = False,
    ):
        # Очищаем сессию от кук прошлых шагов
        self.session.cookies.clear()

        req_cookies = {"user": self.user_id}
        if cookies:
            req_cookies.update(cookies)

        req_headers = {"Connection": "close"}
        if headers:
            req_headers.update(headers)

        kwargs = {
            "headers": req_headers,
            "cookies": req_cookies,
            "timeout": 15,
        }
        if params:
            kwargs["params"] = params

        if is_post:
            if form_data:
                kwargs["data"] = form_data
            if files:
                kwargs["files"] = files
            return self.session.post(url, **kwargs)
        else:
            return self.session.get(url, **kwargs)

    def _make_curl_request(
            self,
            url: str,
            headers: dict = None,
            cookies: dict = None,
            params: dict = None,
            form_data: dict = None,
            files: dict = None,
            is_post: bool = False,
    ) -> requests.Response:
        if params:
            query = urlencode(params)
            url = f"{url}?{query}" if "?" not in url else f"{url}&{query}"

        cmd = ["curl", "-s", "-L"]

        all_cookies = {"user": self.user_id}
        if cookies:
            all_cookies.update(cookies)

        cookie_str = "; ".join([f"{k}={v}" for k, v in all_cookies.items()])
        cmd.extend(["-b", cookie_str])

        req_headers = {"Connection": "close"}
        if headers:
            req_headers.update(headers)

        for k, v in req_headers.items():
            cmd.extend(["-H", f"{k}: {v}"])

        temp_files = []
        try:
            if is_post:
                cmd.extend(["-X", "POST"])
                if files:
                    if form_data:
                        for k, v in form_data.items():
                            cmd.extend(["-F", f"{k}={v}"])
                    for k, file_tuple in files.items():
                        filename = file_tuple[0]
                        content = file_tuple[1]
                        tmp = tempfile.NamedTemporaryFile(delete=False)
                        tmp_write_data = (
                            content
                            if isinstance(content, bytes)
                            else content.encode("utf-8")
                        )
                        tmp.write(tmp_write_data)
                        tmp.close()
                        temp_files.append(tmp.name)
                        cmd.extend(
                            ["-F", f"{k}=@{tmp.name};filename={filename}"]
                        )
                elif form_data:
                    cmd.extend(["-d", urlencode(form_data)])

            cmd.append(url)

            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, timeout=15
            )
            response = requests.Response()
            response.status_code = 200
            response._content = result.stdout.encode("utf-8")
            return response
        finally:
            for path in temp_files:
                if os.path.exists(path):
                    os.remove(path)
