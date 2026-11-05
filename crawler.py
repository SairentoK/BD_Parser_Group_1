import requests
import sqlite3

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
        response = requests.get(url=self.BASE_URL,headers=self.HEADERS, params=params).json()
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
            query= "INSERT INTO articles(url, title, text, pubdate) VALUES(?,?,?,?)"
            cursor.execute(query, (elem["url"], elem["title"], elem["text"], elem["pubdate"]))
            conn.commit()
            print(f"INSERT URL {elem['url']} SUCCESS")
        cursor.close()
        conn.close()





def main():
    crawler = CrawlerLenta()
    crawler.get_database_keywords()
    for keyword in crawler.keywords:
        crawler.make_request(keyword=keyword)



if __name__ == '__main__':
    main()