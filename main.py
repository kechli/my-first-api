from fastapi import FastAPI, Depends, HTTPException 
import httpx
from async_lru import alru_cache
from sqlalchemy.orm import Session
import requests
from bs4 import BeautifulSoup
import models
from database import engine, SessionLocal

models.Base.metadata.create_all(bind=engine)
# Header που απαιτεί το Reddit API για να μην μας μπλοκάρει
app = FastAPI(title="Tech News & GitHub Aggregator API")
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def home():
    return {"message": "Welcome to Tech News Aggregator API with PostgreSQL!"}

# Endpoint για Scraping & Αποθήκευση στη Βάση Δεδομένων
@app.get("/scrape")
def scrape_and_save_news(db: Session = Depends(get_db)):
    url = "https://news.ycombinator.com/"
    response = requests.get(url)
    
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to fetch news")
        
    soup = BeautifulSoup(response.text, "html.parser")
    articles_saved = 0

    # Εξαγωγή τίτλων και συνδέσμων
    for item in soup.select(".titleline > a"):
        title = item.get_text()
        link = item.get("href")
        
        # Έλεγχος αν το άρθρο υπάρχει ήδη στη βάση για να αποφύγουμε διπλότυπα
        existing_article = db.query(models.Article).filter(models.Article.link == link).first()
        if not existing_article:
            new_article = models.Article(
                title=title,
                link=link,
                source="Hacker News"
            )
            db.add(new_article)
            articles_saved += 1

    db.commit() # Αποθήκευση αλλαγών στη βάση
    return {"message": f"Scraping completed! Saved {articles_saved} new articles to PostgreSQL."}

# Endpoint για ανάγνωση όλων των αποθηκευμένων άρθρων από τη Βάση
@app.get("/news")
def get_stored_news(db: Session = Depends(get_db)):
    articles = db.query(models.Article).all()
    return {"total": len(articles), "articles": articles}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


# ------------------------------------------------------------------
# Βοηθητικές συναρτήσεις με Caching (TTL = 300 δευτερόλεπτα / 5 λεπτά)
# ------------------------------------------------------------------

@alru_cache(maxsize=32, ttl=300)
async def fetch_reddit_data(subreddit: str, limit: int):
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=HEADERS)
        if response.status_code != 200:
            return None
        
        data = response.json()
        posts = data["data"]["children"]
        results = []
        for post in posts:
            p = post["data"]
            results.append({
                "title": p["title"],
                "url": p["url"],
                "ups": p["ups"],
                "comments": p["num_comments"]
            })
        return results


@alru_cache(maxsize=32, ttl=300)
async def fetch_github_data(language: str, limit: int):
    url = f"https://api.github.com/search/repositories?q=language:{language}&sort=stars&order=desc&per_page={limit}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code != 200:
            return None
        
        data = response.json()
        repos = data.get("items", [])
        results = []
        for repo in repos:
            results.append({
                "name": repo["name"],
                "author": repo["owner"]["login"],
                "stars": repo["stargazers_count"],
                "url": repo["html_url"],
                "description": repo["description"]
            })
        return results


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

# 1. Endpoint για τα Top Posts από το Reddit
@app.get("/news/reddit/{subreddit}")
async def get_reddit_news(subreddit: str, limit: int = 5):
    posts = await fetch_reddit_data(subreddit, limit)
    if posts is None:
        raise HTTPException(status_code=500, detail="Αποτυχία άντλησης δεδομένων από το Reddit.")
    
    return {"subreddit": subreddit, "count": len(posts), "posts": posts}


# 2. Endpoint για τα Trending Repositories του GitHub
@app.get("/github/trending/{language}")
async def get_github_trending(language: str, limit: int = 5):
    repos = await fetch_github_data(language, limit)
    if repos is None:
        raise HTTPException(status_code=500, detail="Αποτυχία άντλησης δεδομένων από το GitHub.")
    
    return {"language": language, "count": len(repos), "repositories": repos}


# 3. Aggregator Endpoint: Συνδυάζει Reddit + GitHub σε ένα feed!
@app.get("/feed")
async def get_combined_feed(topic: str = "python"):
    # Καλούμε παράλληλα τις cached συναρτήσεις
    reddit_posts = await fetch_reddit_data(topic, 3)
    github_repos = await fetch_github_data(topic, 3)

    if reddit_posts is None or github_repos is None:
        raise HTTPException(status_code=500, detail="Αποτυχία άντλησης δεδομένων από τα εξωτερικά APIs.")

    return {
        "topic": topic,
        "cached_info": "Τα δεδομένα αποθηκεύονται στη μνήμη για 5 λεπτά",
        "reddit_discussions": reddit_posts,
        "github_projects": github_repos
    }