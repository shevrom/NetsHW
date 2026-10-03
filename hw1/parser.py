import requests
from bs4 import BeautifulSoup
from typing import Literal

import os
import subprocess
import tempfile
from urllib.parse import urlencode

ParseType = Literal["py_lib", "curl"]


class Parser:

    def __init__(self, session: requests.Session, root: str):
        self.session = session
        self.root = root

    def parse(self, response: requests.Response, parse_type: ParseType = "py_lib") -> requests.Response:
        soup = BeautifulSoup(response.text, "lxml")
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

        is_post = bool(files or form_data) or "post" in response.text.lower()

        if parse_type == "py_lib":
            return self._make_pylib_request(
                url=next_url,
                headers=headers,
                cookies=cookies,
                params=params,
                form_data=form_data,
                files=files,
                is_post=is_post
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
        auth_user = self.session.cookies.get("user", "c4f6ff551fe6b8e282156c31e9270ab5")
        self.session.cookies.clear()

        self.session.cookies.set("user", auth_user)
        if cookies:
            self.session.cookies.update(cookies)

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

            return self.session.post(url, **kwargs)
        else:
            kwargs = {}
            if headers:
                kwargs["headers"] = headers
            if params:
                kwargs["params"] = params

            return self.session.get(url, **kwargs)

    @staticmethod
    def _make_curl_request(
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

        all_cookies = dict(cookies) if cookies else {}
        all_cookies.setdefault("user", "c4f6ff551fe6b8e282156c31e9270ab5")

        cookie_str = "; ".join([f"{k}={v}" for k, v in all_cookies.items()])
        cmd.extend(["-b", cookie_str])

        if headers:
            for k, v in headers.items():
                cmd.extend(["-H", f"{k}: {v}"])

        temp_files = []
        try:
            if is_post:
                cmd.extend(["-X", "POST"])
                if files:
                    if form_data:
                        for k, v in form_data.items():
                            cmd.extend(["-F", f"{k}={v}"])
                    for k, (filename, content) in files.items():
                        tmp = tempfile.NamedTemporaryFile(delete=False)
                        tmp_write_data = (
                            content
                            if isinstance(content, bytes)
                            else content.encode("utf-8")
                        )
                        tmp.write(tmp_write_data)
                        tmp.close()
                        temp_files.append(tmp.name)
                        cmd.extend(["-F", f"{k}=@{tmp.name};filename={filename}"])
                elif form_data:
                    cmd.extend(["-d", urlencode(form_data)])

            cmd.append(url)

            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True
            )
            response = requests.Response()
            response.status_code = 200
            response._content = result.stdout.encode("utf-8")
            return response
        finally:
            for path in temp_files:
                if os.path.exists(path):
                    os.remove(path)