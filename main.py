from fastapi import FastAPI, HTTPException
import httpx
from async_lru import alru_cache

app = FastAPI(title="Tech News & GitHub Aggregator API")

# Header που απαιτεί το Reddit API για να μην μας μπλοκάρει
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