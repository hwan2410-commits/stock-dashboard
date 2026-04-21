import feedparser
import requests
from datetime import datetime


FEEDS = {
    "한국경제": "https://www.hankyung.com/feed/finance",
    "연합뉴스 증권": "https://www.yna.co.kr/rss/economy.xml",
    "Reuters Business": "https://feeds.reuters.com/reuters/businessNews",
    "CNBC Markets": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
}


def fetch_news(max_per_feed: int = 5) -> list:
    articles = []
    for source, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                published = ""
                if hasattr(entry, "published"):
                    published = entry.published[:16]
                articles.append({
                    "출처": source,
                    "제목": entry.title,
                    "링크": entry.link,
                    "날짜": published,
                })
        except:
            continue
    return articles
