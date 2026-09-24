"""Nightly collector: RSS -> filter -> Claude extraction -> data/*.json"""
import json, os, re, datetime, urllib.parse
import feedparser, requests
from anthropic import Anthropic

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda f: os.path.join(ROOT, f)
MODEL = "claude-haiku-4-5-20251001"
MAX_PER_RUN = 40          # cost cap per night
AUTO_PUBLISH = 0.85       # confidence needed to skip the review queue
AI = re.compile(r"\b(AI|artificial intelligence|generative|ChatGPT|Copilot|Gemini|Claude|LLM|chatbot|machine learning)\b", re.I)
NFP = re.compile(r"\b(charity|charities|not-for-profit|nonprofit|non-profit|NFP|foundation|NGO|community organisation)\b", re.I)

def load(f, d):
    try: return json.load(open(P(f)))
    except Exception: return d
def save(f, o): json.dump(o, open(P(f), "w"), indent=2, ensure_ascii=False)

def real_url(u):  # unwrap Google Alerts redirect links
    q = urllib.parse.parse_qs(urllib.parse.urlparse(u).query)
    return q.get("url", [u])[0]

def sector_feeds():
    one = os.environ.get("SECTOR", "").strip()
    one = re.sub(r"^sector request:\s*", "", one, flags=re.I)[:60]
    lines = [one] if one else [l.strip() for l in open(P("sectors.txt")) if l.strip() and not l.startswith("#")]
    for sec in lines:
        q = f'"{sec}" (charity OR "not-for-profit" OR nonprofit) (AI OR "artificial intelligence" OR ChatGPT OR Copilot) Australia'
        yield sec, "https://news.google.com/rss/search?q=" + urllib.parse.quote(q) + "&hl=en-AU&gl=AU&ceid=AU:en"

def general_feeds():
    if os.environ.get("SECTOR", "").strip(): return  # on-demand run: sector search only
    for line in open(P("feeds.txt")):
        line = line.strip()
        if line and not line.startswith("#"): yield None, line

def collect(seen):
    out, urls = [], set()
    for hint, feed in list(general_feeds()) + list(sector_feeds()):
        for e in feedparser.parse(feed).entries[:10]:
            url = real_url(e.get("link", ""))
            blob = f"{e.get('title','')} {e.get('summary','')}"
            if not url or url in seen or url in urls: continue
            if hint is None and not (AI.search(blob) and NFP.search(blob)): continue
            urls.add(url)
            out.append({"url": url, "sector_hint": hint, "title": re.sub("<[^>]+>", "", e.get("title", ""))})
    return out

def page_text(url):
    try:
        h = requests.get(url, timeout=20, headers={"User-Agent": "nfp-ai-tracker/1.0"}).text
        h = re.sub(r"(?s)<(script|style|nav|footer)[^>]*>.*?</\1>", " ", h)
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))[:6000]
    except Exception:
        return ""

PROMPT = """You analyse web articles for a tracker of AI use by Australian not-for-profits.
Decide whether the article describes a SPECIFIC AI initiative run or used by an Australian not-for-profit/charity/community organisation.
Return ONLY JSON:
{"relevant":bool,"organisation":"","initiative":"","description":"one factual sentence, no hype","state":"National|NSW|VIC|QLD|WA|SA|TAS|ACT|NT","sector":"","tool":"","use":"","status":"Exploring|Pilot|Live|Scaled","evidence":"Low|Medium|High","confidence":0.0}
Use only facts stated in the article. If unsure, set relevant=false. evidence=High only for outcomes/data reported by the organisation.

TITLE: %s
URL: %s
TEXT: %s"""

def extract(client, item, text):
    r = client.messages.create(model=MODEL, max_tokens=500,
        messages=[{"role": "user", "content": PROMPT % (item["title"], item["url"], text)}])
    m = re.search(r"\{.*\}", r.content[0].text, re.S)
    return json.loads(m.group(0)) if m else None

def main():
    client = Anthropic()  # reads ANTHROPIC_API_KEY
    seen = set(load("data/seen.json", []))
    pub, rev = load("data/initiatives.json", {"items": []}), load("data/review.json", {"items": []})
    keys = {(i["organisation"].lower(), i["initiative"].lower()) for i in pub["items"] + rev["items"]}
    today = datetime.date.today().isoformat()
    for item in collect(seen)[:MAX_PER_RUN]:
        seen.add(item["url"])
        try: r = extract(client, item, page_text(item["url"]) or item["title"])
        except Exception as ex: print("skip", item["url"], ex); continue
        if not r or not r.get("relevant") or not r.get("organisation"): continue
        k = (r["organisation"].lower(), r.get("initiative", "").lower())
        if k in keys: continue
        keys.add(k)
        r["sector"] = r.get("sector") or item["sector_hint"] or ""
        r.update(source=item["url"], added=today, verified=False)
        r.pop("relevant", None)
        (pub if r.get("confidence", 0) >= AUTO_PUBLISH else rev)["items"].append(r)
    for d, f in ((pub, "data/initiatives.json"), (rev, "data/review.json")):
        d["updated"] = today; save(f, d)
    save("data/seen.json", sorted(seen)[-5000:])

if __name__ == "__main__":
    main()
