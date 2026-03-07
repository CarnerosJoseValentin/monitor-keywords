import os
import re
import json
import time
import hashlib
import unicodedata
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
import feedparser
import requests
from dateutil import parser as dateparser


STATE_PATH = "state.json"
KEYWORDS_PATH = "keywords.txt"
FEEDS_PATH = "feeds.txt"
MASTODON_INSTANCES_PATH = "mastodon_instances.txt"

DEFAULT_RETENTION_DAYS = 30
DEFAULT_MAX_SNIPPET = 300

TRACKING_PARAMS_PREFIX = ("utm_",)
TRACKING_PARAMS_EXACT = {
    "fbclid", "gclid", "igshid", "mc_cid", "mc_eid", "ref", "ref_src",
    "mkt_tok", "spm", "yclid"
}

UA = "keyword-monitor-bot/1.0 (+GitHub Actions)"


def read_lines(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            out.append(s)
    return out


def strip_quotes(s: str) -> str:
    s = s.strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1].strip()
    return s


def fold_accents(s: str) -> str:
    """
    Convierte a una forma comparable sin acentos/diacríticos.
    Ej: "policía" -> "policia"
    """
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s


def normalize_text_for_match(s: str) -> str:
    s = strip_quotes(s)
    s = s.lower()
    s = fold_accents(s)
    # normalizar espacios
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_url(url: str) -> str:
    try:
        p = urlparse(url.strip())
        fragment = ""
        q = []
        for k, v in parse_qsl(p.query, keep_blank_values=True):
            kl = k.lower()
            if kl in TRACKING_PARAMS_EXACT:
                continue
            if any(kl.startswith(pref) for pref in TRACKING_PARAMS_PREFIX):
                continue
            q.append((k, v))
        query = urlencode(q, doseq=True)
        netloc = p.netloc.lower()
        path = p.path or "/"
        if path != "/" and path.endswith("/"):
            path = path[:-1]
        return urlunparse((p.scheme, netloc, path, p.params, query, fragment))
    except Exception:
        return url.strip()


def stable_id(title: str, url: str, published: str | None) -> str:
    base = (title or "").strip().lower() + "||" + normalize_url(url).lower()
    if published:
        base += "||" + published.strip()
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def load_state() -> dict:
    if not os.path.exists(STATE_PATH):
        return {"version": 1, "seen": {}}
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)


def purge_state(state: dict, retention_days: int) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    seen = state.get("seen", {})
    to_del = []
    for k, v in seen.items():
        try:
            dt = dateparser.parse(v)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt < cutoff:
                to_del.append(k)
        except Exception:
            to_del.append(k)
    for k in to_del:
        del seen[k]
    state["seen"] = seen


def entry_text(entry) -> str:
    parts = []
    for key in ("title", "summary", "description"):
        if key in entry and entry[key]:
            parts.append(str(entry[key]))
    if "content" in entry:
        try:
            for c in entry["content"]:
                if "value" in c and c["value"]:
                    parts.append(str(c["value"]))
        except Exception:
            pass
    text = "\n".join(parts)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compile_keyword_patterns(keywords: list[str]) -> list[tuple[str, re.Pattern]]:
    """
    Devuelve lista de (keyword_original, regex_pattern).
    Reglas:
    - Si keyword es "sigla" (solo letras/números, sin espacios) y <= 6 chars -> match por palabra completa.
    - Si es frase con espacios -> match por substring normalizado (regex simple).
    """
    compiled = []
    for raw in keywords:
        kw = strip_quotes(raw)
        kw_norm = normalize_text_for_match(kw)

        if not kw_norm:
            continue

        # detectar "sigla"
        is_token = bool(re.fullmatch(r"[a-z0-9_]+", kw_norm))
        if is_token and len(kw_norm) <= 6:
            # palabra completa: \b...\b
            pat = re.compile(rf"\b{re.escape(kw_norm)}\b", re.IGNORECASE)
        else:
            # frase / palabra larga: búsqueda flexible en texto normalizado
            pat = re.compile(re.escape(kw_norm), re.IGNORECASE)

        compiled.append((kw, pat))
    return compiled


def match_keywords(text: str, compiled: list[tuple[str, re.Pattern]]) -> list[str]:
    t = normalize_text_for_match(text)
    hits = []
    for kw_original, pat in compiled:
        if pat.search(t):
            hits.append(kw_original)
    return hits


def parse_published(entry) -> str | None:
    for key in ("published", "updated"):
        if key in entry and entry[key]:
            return str(entry[key])
    return None


def fetch_feed(url: str) -> feedparser.FeedParserDict:
    return feedparser.parse(url, agent=UA)


def mastodon_hashtag_feed_urls(instances: list[str], keywords: list[str]) -> list[str]:
    feeds = []
    for inst in instances:
        inst = inst.strip()
        if not inst:
            continue
        base = f"https://{inst}/tags/"
        for raw in keywords:
            kw = strip_quotes(raw).strip()
            # hashtags: solo si no tiene espacios
            if not kw or " " in kw:
                continue
            tag = re.sub(r"[^A-Za-z0-9_]", "", kw)
            if not tag:
                continue
            feeds.append(base + tag + ".rss")
    return feeds


def send_telegram(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": False,
    }
    r = requests.post(url, json=payload, timeout=30)
    if not r.ok:
        raise RuntimeError(f"Telegram sendMessage failed: {r.status_code} {r.text}")


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise SystemExit("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID (set GitHub Secrets).")

    retention_days = int(os.getenv("RETENTION_DAYS", str(DEFAULT_RETENTION_DAYS)))
    max_snippet = int(os.getenv("MAX_SNIPPET_CHARS", str(DEFAULT_MAX_SNIPPET)))

    keywords_raw = read_lines(KEYWORDS_PATH)
    if not keywords_raw:
        raise SystemExit("keywords.txt is empty. Add at least 1 keyword.")

    compiled = compile_keyword_patterns(keywords_raw)

    feeds = read_lines(FEEDS_PATH)
    instances = read_lines(MASTODON_INSTANCES_PATH)
    masto_feeds = mastodon_hashtag_feed_urls(instances, keywords_raw)

    all_feeds = feeds + masto_feeds
    if not all_feeds:
        raise SystemExit("No feeds found. Add RSS URLs to feeds.txt and/or Mastodon instances + hashtag keywords.")

    state = load_state()
    purge_state(state, retention_days)
    seen = state.get("seen", {})

    new_items = []

    for feed_url in all_feeds:
        try:
            parsed = fetch_feed(feed_url)
            for entry in parsed.entries:
                title = getattr(entry, "title", "") or entry.get("title", "") or ""
                link = getattr(entry, "link", "") or entry.get("link", "") or ""
                if not link:
                    continue
                norm = normalize_url(link)

                text = (title + " " + entry_text(entry)).strip()
                hits = match_keywords(text, compiled)
                if not hits:
                    continue

                published = parse_published(entry)
                sid = stable_id(title, norm, published)

                if sid in seen:
                    continue

                snippet_src = entry_text(entry)
                snippet = snippet_src[:max_snippet] + ("…" if len(snippet_src) > max_snippet else "")
                domain = urlparse(norm).netloc

                new_items.append({
                    "keywords": hits,
                    "title": title.strip() or "(sin título)",
                    "url": norm,
                    "domain": domain,
                    "snippet": snippet,
                })

                seen[sid] = datetime.now(timezone.utc).isoformat()

        except Exception as e:
            new_items.append({
                "keywords": ["(error)"],
                "title": f"Error leyendo feed: {feed_url}",
                "url": feed_url,
                "domain": "feed-error",
                "snippet": str(e)[:max_snippet],
            })

    new_items_sorted = sorted(new_items, key=lambda it: (it["domain"], it["title"].lower()))

    if new_items_sorted:
        lines = []
        lines.append(f"🔔 Nuevos hallazgos (última hora): {len(new_items_sorted)}")
        lines.append("")

        for it in new_items_sorted[:50]:
            kws = ", ".join(it["keywords"][:5])
            lines.append(f"• 🧷 {kws}")
            lines.append(f"  📰 {it['title']}")
            lines.append(f"  🌐 {it['domain']}")
            if it["snippet"]:
                lines.append(f"  📝 {it['snippet']}")
            lines.append(f"  🔗 {it['url']}")
            lines.append("")

        msg = "\n".join(lines).strip()
        chunks = []
        while msg:
            chunks.append(msg[:3900])
            msg = msg[3900:]

        for chunk in chunks:
            send_telegram(token, chat_id, chunk)
            time.sleep(1)

    state["seen"] = seen
    save_state(state)


if __name__ == "__main__":
    main()