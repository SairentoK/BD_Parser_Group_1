import requests
import sqlite3
import json
import re
from datetime import datetime
from urllib.parse import urljoin
from html import unescape


class CrawlerLenta:
    BASE_URL = 'https://lenta.ru/search/v2/process'

    HEADERS = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://lenta.ru/search?query=%D0%BF%D1%83%D0%BB%D0%BA%D0%BE%D0%B2%D0%BE',
        'sec-ch-ua': '"Google Chrome";v="155", "Chromium";v="155", "Not(A:Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36',
    }

    PARAMS = {
        'query': 'пулково',
        'from': '0',
        'size': '100',
        'sort': '2',
        'title_only': '0',
        'domain': '1',
        'modified,format': 'yyyy-MM-dd',
    }

    def __init__(self):
        self.keywords = []
        self.data = []
        self.total_article = 0

    def extract(self, data: dict):
        try:
            for elem in data["matches"]:
                self.data.append({"url": elem["url"],
                                  "title": elem["title"],
                                  "text": elem["text"],
                                  "pubdate": elem["pubdate"]})
        except KeyError:
            print(data)

    def make_request(self, keyword: str):
        params = self.PARAMS.copy()
        params["query"] = keyword
        response = requests.get(url=self.BASE_URL, headers=self.HEADERS, params=params).json()
        self.total_article = response["total"]
        self.extract(response)
        while len(self.data) < int(self.total_article):
            params = self.PARAMS.copy()
            params["query"] = keyword
            params["from"] = str(len(self.data))
            response = requests.get(url=self.BASE_URL, headers=self.HEADERS, params=params).json()
            self.extract(response)
        self.insert_data(self.data)
        self.data = []

    def get_database_keywords(self):
        conn = sqlite3.connect('db.sqlite3')
        cursor = conn.cursor()
        query = "SELECT keyword FROM keywords"
        cursor.execute(query)
        keywords = cursor.fetchall()
        for keyword in keywords:
            self.keywords.append(keyword[0])
        cursor.close()
        conn.close()

    def insert_data(self, data: list):
        conn = sqlite3.connect('db.sqlite3')
        cursor = conn.cursor()
        for elem in data:
            query = "INSERT INTO articles(url, title, text, pubdate) VALUES(?,?,?,?)"
            cursor.execute(query, (elem["url"], elem["title"], elem["text"], elem["pubdate"]))
            conn.commit()
            print(f"INSERT URL {elem['url']} SUCCESS")
        cursor.close()
        conn.close()


class CrawlerFontanka(CrawlerLenta):
    BASE_URL = "https://www.fontanka.ru/search/"

    def __init__(self):
        super().__init__()
        self.session = requests.Session()

    def search_urls(self, keyword: str):
        url = self.BASE_URL
        params = {"keywords": keyword}
        visited = set()

        while url and url not in visited:
            visited.add(url)
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            html = response.content.decode("utf-8")

            marker = re.search(r"\bwindow\.initialState\s*=\s*", html)
            if not marker:
                raise ValueError("На странице поиска не найден window.initialState")

            state, _ = json.JSONDecoder().raw_decode(html, marker.end())
            page = state["searchPage"]

            for card in page["announcements"]:
                yield urljoin(url, card["header"]["url"]).split("?", 1)[0]

            pagination = page["meta"]["pagination"]
            if not pagination["hasNextPage"] or not pagination["nextPageUrl"]:
                break

            url = urljoin(url, pagination["nextPageUrl"])
            params = None  # В ссылке на следующую страницу уже есть ключевое слово

    def read_article(self, url: str):
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        html = response.content.decode("utf-8")

        # В этом блоке «Фонтанка» хранит полный текст и дату статьи.
        blocks = re.findall(
            r"""<script\b[^>]*\btype=["']application/ld\+json["'][^>]*>(.*?)</script\s*>""",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )

        for block in blocks:
            document = json.loads(block)
            if isinstance(document, list):
                nodes = document
            else:
                nodes = document.get("@graph", [document])

            for node in nodes:
                if node.get("articleBody") and node.get("datePublished"):
                    published = datetime.fromisoformat(node["datePublished"])
                    return {
                        "url": url,
                        "title": node["headline"],
                        "text": unescape(node["articleBody"]),
                        "pubdate": int(published.timestamp()),
                    }

        raise ValueError("В статье не найден полный текст или дата")

    def make_request(self, keyword: str):
        conn = sqlite3.connect("db.sqlite3")
        try:
            known_urls = {
                row[0] for row in conn.execute(
                    "SELECT url FROM articles WHERE url LIKE '%fontanka.ru/%'"
                )
            }
        finally:
            conn.close()

        for url in self.search_urls(keyword):
            if url in known_urls:
                continue

            try:
                article = self.read_article(url)
            except (KeyError, ValueError) as error:
                print(f"Пропущена статья {url}: {error}")
                continue

            self.insert_data([article])
            known_urls.add(url)


def main():
    lenta = CrawlerLenta()
    fontanka = CrawlerFontanka()

    lenta.get_database_keywords()
    for keyword in lenta.keywords:
        lenta.make_request(keyword=keyword)
        fontanka.make_request(keyword=keyword)


if __name__ == '__main__':
    main()
