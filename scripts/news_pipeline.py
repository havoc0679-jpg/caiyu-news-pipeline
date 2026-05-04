#!/usr/bin/env python3
"""
采毓新聞自動化 v2
─────────────────────────────────
v2 更新：
  - 9 大運動分類獨立抓取（籃球/排球/棒球/足球/桌球/羽球/網球/匹克球/游泳）
  - 每分類每次抓 2 篇 → 總量上限 30 篇/天
  - 自動抓取首圖（從 RSS / og:image / 圖片 fallback）
  - 加上活動產業、科技展演

排程：每天 3 次（07:00 / 16:30 / 21:30）
"""

import os
import sys
import json
import time
import hashlib
import re
import feedparser
import requests
from datetime import datetime, timezone, timedelta
from anthropic import Anthropic
from supabase import create_client

# ═══════════════════════════════════════════════════════════════
# 設定區
# ═══════════════════════════════════════════════════════════════

# 9 大運動 + 2 大產業，每分類獨立 RSS 來源
NEWS_SOURCES = [
    {"name": "籃球", "category": "籃球",
     "rss": "https://news.google.com/rss/search?q=%E7%B1%83%E7%90%83+%E5%8F%B0%E7%81%A3+OR+P%E8%81%AF%E7%9B%9F+OR+T1%E8%81%AF%E7%9B%9F+OR+SBL&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"},
    {"name": "排球", "category": "排球",
     "rss": "https://news.google.com/rss/search?q=%E6%8E%92%E7%90%83+%E5%8F%B0%E7%81%A3&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"},
    {"name": "棒球", "category": "棒球",
     "rss": "https://news.google.com/rss/search?q=%E6%A3%92%E7%90%83+%E5%8F%B0%E7%81%A3+OR+%E4%B8%AD%E8%81%B7&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"},
    {"name": "足球", "category": "足球",
     "rss": "https://news.google.com/rss/search?q=%E8%B6%B3%E7%90%83+%E5%8F%B0%E7%81%A3+OR+%E5%8F%B0%E7%81%A3%E8%B6%B3%E7%90%83&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"},
    {"name": "桌球", "category": "桌球",
     "rss": "https://news.google.com/rss/search?q=%E6%A1%8C%E7%90%83+%E5%8F%B0%E7%81%A3&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"},
    {"name": "羽球", "category": "羽球",
     "rss": "https://news.google.com/rss/search?q=%E7%BE%BD%E7%90%83+%E5%8F%B0%E7%81%A3+OR+%E5%91%A8%E5%A4%A9%E6%88%90+OR+%E6%88%B4%E8%B3%87%E7%A9%8E&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"},
    {"name": "網球", "category": "網球",
     "rss": "https://news.google.com/rss/search?q=%E7%B6%B2%E7%90%83+%E5%8F%B0%E7%81%A3&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"},
    {"name": "匹克球", "category": "匹克球",
     "rss": "https://news.google.com/rss/search?q=%E5%8C%B9%E5%85%8B%E7%90%83+OR+pickleball&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"},
    {"name": "游泳", "category": "游泳",
     "rss": "https://news.google.com/rss/search?q=%E6%B8%B8%E6%B3%B3+%E5%8F%B0%E7%81%A3&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"},
    {"name": "活動產業", "category": "活動產業",
     "rss": "https://news.google.com/rss/search?q=%E6%B4%BB%E5%8B%95%E8%A1%8C%E9%8A%B7+OR+%E9%AB%94%E9%A9%97%E7%B6%93%E6%BF%9F&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"},
    {"name": "科技展演", "category": "科技展演",
     "rss": "https://news.google.com/rss/search?q=%E7%84%A1%E4%BA%BA%E6%A9%9F%E8%A1%A8%E6%BC%94+OR+%E5%85%89%E9%9B%95%E7%A7%80&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"},
]

# 每分類每次最多取幾篇候選（要從這些中改寫成功才算）
MAX_PER_CATEGORY = 4
# 每分類每次最多發布幾篇
PUBLISH_PER_CATEGORY = 2
# 整次執行的全域上限（防超支）
GLOBAL_MAX_PUBLISH = 12

# 全部允許分類（必須跟前台 / admin 一致）
ALLOWED_CATEGORIES = ["籃球","排球","棒球","足球","桌球","羽球","網球","匹克球","游泳","活動產業","科技展演","其他"]

CLAUDE_MODEL = "claude-sonnet-4-5"

# 環境變數
ANTHROPIC_API_KEY = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").strip().rstrip("/")
SUPABASE_KEY = (os.environ.get("SUPABASE_SERVICE_KEY") or "").strip()

print(f"🔧 SUPABASE_URL = '{SUPABASE_URL}' (長度 {len(SUPABASE_URL)})")

if not all([ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_KEY]):
    print("❌ 缺少環境變數: ANTHROPIC_API_KEY / SUPABASE_URL / SUPABASE_SERVICE_KEY")
    sys.exit(1)

claude = Anthropic(api_key=ANTHROPIC_API_KEY)
sb = create_client(SUPABASE_URL, SUPABASE_KEY)
TW_TZ = timezone(timedelta(hours=8))


# ═══════════════════════════════════════════════════════════════
# Step 1: 抓取 Google News RSS（按分類）
# ═══════════════════════════════════════════════════════════════

def fetch_news_by_category():
    """每個分類獨立抓，回傳 dict: {category: [items...]}"""
    by_cat = {}
    for src in NEWS_SOURCES:
        try:
            print(f"📡 抓取 [{src['name']}]")
            feed = feedparser.parse(src["rss"])
            items = []
            for entry in feed.entries[:MAX_PER_CATEGORY * 3]:
                items.append({
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "source_name": entry.get("source", {}).get("title") or src["name"],
                    "published": entry.get("published", ""),
                    "summary_raw": entry.get("summary", ""),
                    "category_hint": src["category"],
                })
            by_cat[src["category"]] = items
            print(f"   → 取得 {len(items)} 則候選")
        except Exception as e:
            print(f"   ⚠️ 抓取失敗: {e}")
            by_cat[src["category"]] = []
    return by_cat


# ═══════════════════════════════════════════════════════════════
# Step 2: 過濾已發布過的（避免重複）
# ═══════════════════════════════════════════════════════════════

def title_hash(title: str) -> str:
    return hashlib.md5(title.encode("utf-8")).hexdigest()[:16]

def filter_new_in_category(items):
    """過濾掉資料庫已存在的"""
    if not items:
        return []
    hashes = [title_hash(it["title"]) for it in items]
    try:
        existing = sb.table("articles").select("source_hash").in_("source_hash", hashes).execute()
        existing_hashes = {row["source_hash"] for row in existing.data or []}
    except Exception as e:
        print(f"⚠️ 查詢資料庫失敗，假設無重複: {e}")
        existing_hashes = set()

    new_items = []
    for it in items:
        h = title_hash(it["title"])
        if h not in existing_hashes:
            it["source_hash"] = h
            new_items.append(it)
    return new_items


# ═══════════════════════════════════════════════════════════════
# Step 3: 從原文抓首圖
# ═══════════════════════════════════════════════════════════════

# Unsplash 預設圖（按分類）
DEFAULT_IMAGES = {
    "籃球": "https://images.unsplash.com/photo-1546519638-68e109498ffc?w=800&q=80",
    "排球": "https://images.unsplash.com/photo-1612872087720-bb876e2e67d1?w=800&q=80",
    "棒球": "https://images.unsplash.com/photo-1508344928-9af6ad7717ee?w=800&q=80",
    "足球": "https://images.unsplash.com/photo-1431324155629-1a6deb1dec8d?w=800&q=80",
    "桌球": "https://images.unsplash.com/photo-1534158914592-062992fbe900?w=800&q=80",
    "羽球": "https://images.unsplash.com/photo-1626224583764-f87db24ac4ea?w=800&q=80",
    "網球": "https://images.unsplash.com/photo-1622279457486-62dcc4a431d6?w=800&q=80",
    "匹克球": "https://images.unsplash.com/photo-1685897469268-99b884ff8c4f?w=800&q=80",
    "游泳": "https://images.unsplash.com/photo-1530549387789-4c1017266635?w=800&q=80",
    "活動產業": "https://images.unsplash.com/photo-1540575467063-178a50c2df87?w=800&q=80",
    "科技展演": "https://images.unsplash.com/photo-1473968512647-3e447244af8f?w=800&q=80",
    "其他": "https://images.unsplash.com/photo-1495020689067-958852a7765e?w=800&q=80",
}


def extract_image_from_summary(html_summary):
    """從 RSS summary HTML 中找 <img src="..."> """
    if not html_summary:
        return None
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html_summary)
    if m:
        url = m.group(1)
        # 過濾掉太小的 icon
        if "icon" not in url.lower() and "logo" not in url.lower():
            return url
    return None


def fetch_og_image(url):
    """從原文 URL 抓 og:image"""
    if not url:
        return None
    try:
        # Google News 連結會 redirect，直接用 requests follow
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; CaiyuNewsBot/1.0)",
        }
        resp = requests.get(url, headers=headers, timeout=8, allow_redirects=True)
        if resp.status_code != 200:
            return None
        html = resp.text[:50000]  # 只看前段省流量
        # 抓 og:image
        for pattern in [
            r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
            r'<meta\s+content=["\']([^"\']+)["\']\s+property=["\']og:image["\']',
            r'<meta\s+name=["\']twitter:image["\']\s+content=["\']([^"\']+)["\']',
        ]:
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                img = m.group(1).strip()
                if img.startswith("//"):
                    img = "https:" + img
                if img.startswith("http"):
                    return img
        return None
    except Exception as e:
        print(f"   📷 抓圖失敗 (略過): {type(e).__name__}")
        return None


def get_image_for_item(item):
    """三段式取圖：summary HTML → og:image → 預設圖"""
    # 1. 從 RSS summary 找
    img = extract_image_from_summary(item.get("summary_raw"))
    if img:
        return img
    # 2. 從原文抓 og:image
    img = fetch_og_image(item.get("link"))
    if img:
        return img
    # 3. 用預設圖
    return DEFAULT_IMAGES.get(item.get("category_hint"), DEFAULT_IMAGES["其他"])


# ═══════════════════════════════════════════════════════════════
# Step 4: Claude 改寫
# ═══════════════════════════════════════════════════════════════

REWRITE_PROMPT = """你是「采毓活動整合行銷有限公司」旗下「采毓新聞」的資深編輯。
公司專長：體育賽事、活動行銷、體驗經濟。
你要從以下原始新聞素材中，**抽取純事實**，再用采毓的角度寫出一篇原創新聞稿。

═══ 原始素材（僅供參考事實，不得直接複製文字）═══
分類提示：{category_hint}
標題：{title}
來源媒體：{source_name}
原文連結：{link}
原文摘要：{summary_raw}
═══════════════════════════════════════════

【寫作規則 — 嚴格遵守】

1. **完全自己重寫文字**：不可複製或近似改寫原文句子，只能使用原文中的「事實」（人名、日期、地點、數據、結果）
2. **加上采毓觀點**：在文末加一段「采毓觀點」，從活動行銷 / 體驗經濟 / 賽事產業的角度做分析或延伸
3. **誠實揭示**：在文末附「資料整理自：[來源媒體]」
4. **長度**：正文 200-350 字，采毓觀點 80-150 字
5. **語氣**：專業、客觀，但有采毓特色（不八卦、不誇張）
6. **若素材太薄弱（沒有具體事實/數據）**：回傳 {{"skip": true, "reason": "原因"}}

【輸出格式 — 嚴格 JSON，不要 markdown 包覆】

{{
  "skip": false,
  "title": "采毓自己的標題（不抄原文，可帶引言或角度）",
  "category": "從這幾項選一個：{categories}",
  "summary": "60-80 字摘要",
  "content": "正文完整內容\\n\\n采毓觀點\\n\\n（觀點分析內容）\\n\\n資料整理自：{source_name}",
  "tags": ["標籤1", "標籤2", "標籤3"],
  "featured": false
}}

直接輸出 JSON，不要任何其他文字。"""


def rewrite_with_claude(item):
    prompt = REWRITE_PROMPT.format(
        category_hint=item.get("category_hint", "其他"),
        title=item["title"],
        source_name=item.get("source_name", "未知來源"),
        link=item["link"],
        summary_raw=re.sub(r'<[^>]+>', '', item.get("summary_raw", ""))[:500],  # 移除 HTML tags
        categories="、".join(ALLOWED_CATEGORIES),
    )
    try:
        msg = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"   ⚠️ JSON 解析失敗: {e}")
        return None
    except Exception as e:
        print(f"   ⚠️ Claude API 失敗: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# Step 5: 寫入 Supabase
# ═══════════════════════════════════════════════════════════════

def insert_article(item, rewritten, image_url):
    now = datetime.now(TW_TZ)
    payload = {
        "title": rewritten["title"],
        "category": rewritten["category"] if rewritten["category"] in ALLOWED_CATEGORIES else item.get("category_hint", "其他"),
        "summary": rewritten["summary"],
        "content": rewritten["content"],
        "author": "采毓編輯部（AI 輔助）",
        "tags": rewritten.get("tags", []),
        "featured": rewritten.get("featured", False),
        "image": image_url,
        "source_url": item["link"],
        "source_name": item.get("source_name", ""),
        "source_hash": item["source_hash"],
        "published_at": now.isoformat(),
        "is_ai_generated": True,
        "is_published": True,
    }
    try:
        sb.table("articles").insert(payload).execute()
        return True
    except Exception as e:
        print(f"   ⚠️ Supabase 寫入失敗: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# Main — 按分類處理
# ═══════════════════════════════════════════════════════════════

def main():
    print("═" * 60)
    print(f"🚀 采毓新聞自動化 v2 — {datetime.now(TW_TZ).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   設定：每類 {PUBLISH_PER_CATEGORY} 篇，全域上限 {GLOBAL_MAX_PUBLISH} 篇")
    print("═" * 60)

    by_cat = fetch_news_by_category()

    total_success = 0
    total_skipped = 0
    total_failed = 0
    by_cat_stats = {}

    for category, items in by_cat.items():
        if total_success >= GLOBAL_MAX_PUBLISH:
            print(f"\n⛔ 已達全域上限 {GLOBAL_MAX_PUBLISH} 篇，停止")
            break

        print(f"\n──── 處理分類：{category} ────")
        new_items = filter_new_in_category(items)
        print(f"   過濾後新文章：{len(new_items)} 則")

        cat_success = 0
        for item in new_items:
            if cat_success >= PUBLISH_PER_CATEGORY:
                break
            if total_success >= GLOBAL_MAX_PUBLISH:
                break

            print(f"\n  [{category}] 處理：{item['title'][:45]}...")
            rewritten = rewrite_with_claude(item)
            if not rewritten:
                total_failed += 1
                continue
            if rewritten.get("skip"):
                print(f"     ⏭️ 跳過：{rewritten.get('reason', '素材不足')}")
                total_skipped += 1
                continue

            # 抓圖
            image_url = get_image_for_item(item)
            print(f"     📷 圖片：{image_url[:60]}...")

            if insert_article(item, rewritten, image_url):
                print(f"     ✅ 已發布：「{rewritten['title']}」")
                cat_success += 1
                total_success += 1
            else:
                total_failed += 1

            time.sleep(2)

        by_cat_stats[category] = cat_success

    print("\n" + "═" * 60)
    print(f"📊 完成 — 總成功:{total_success} / 跳過:{total_skipped} / 失敗:{total_failed}")
    print("各分類發布統計：")
    for c, n in by_cat_stats.items():
        print(f"   {c}: {n} 篇")
    print("═" * 60)


if __name__ == "__main__":
    main()
