from fastapi import FastAPI, HTTPException
import httpx

app = FastAPI(title="Tech News & GitHub Aggregator API")

# Header που απαιτεί το Reddit API για να μην μας μπλοκάρει
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


# 1. Endpoint για τα Top Posts από το Reddit
@app.get("/news/reddit/{subreddit}")
async def get_reddit_news(subreddit: str, limit: int = 5):
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=HEADERS)
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Αποτυχία άντλησης δεδομένων από το Reddit.")
        
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
            
        return {"subreddit": subreddit, "count": len(results), "posts": results}


# 2. Endpoint για τα Trending Repositories του GitHub
@app.get("/github/trending/{language}")
async def get_github_trending(language: str, limit: int = 5):
    url = f"https://api.github.com/search/repositories?q=language:{language}&sort=stars&order=desc&per_page={limit}"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Αποτυχία άντλησης δεδομένων από το GitHub.")
        
        data = response.json()
        repos = data["items"]
        
        results = []
        for repo in repos:
            results.append({
                "name": repo["name"],
                "author": repo["owner"]["login"],
                "stars": repo["stargazers_count"],
                "url": repo["html_url"],
                "description": repo["description"]
            })
            
        return {"language": language, "count": len(results), "repositories": results}


# 3. Aggregator Endpoint: Συνδυάζει Reddit + GitHub σε ένα feed!
@app.get("/feed")
async def get_combined_feed(topic: str = "python"):
    async with httpx.AsyncClient() as client:
        # Παράλληλη κλήση και στα 2 APIs
        reddit_req = client.get(f"https://www.reddit.com/r/{topic}/hot.json?limit=3", headers=HEADERS)
        github_req = client.get(f"https://api.github.com/search/repositories?q=language:{topic}&sort=stars&order=desc&per_page=3")
        
        # Περιμένουμε και τα δύο να ολοκληρωθούν
        reddit_res, github_res = await httpx.AsyncClient().get(...), await ... 
        # (Για απλότητα εκτελούμε τις κλήσεις)
        
        r_data = (await client.get(f"https://www.reddit.com/r/{topic}/hot.json?limit=3", headers=HEADERS)).json()
        g_data = (await client.get(f"https://api.github.com/search/repositories?q=language:{topic}&sort=stars&order=desc&per_page=3")).json()
        
        reddit_posts = [{"title": p["data"]["title"], "url": p["data"]["url"]} for p in r_data["data"]["children"]]
        github_repos = [{"name": r["name"], "stars": r["stargazers_count"], "url": r["html_url"]} for r in g_data.get("items", [])]
        
        return {
            "topic": topic,
            "reddit_discussions": reddit_posts,
            "github_projects": github_repos
        }