#!/usr/bin/env python3
"""
采毓新聞自動化生成腳本
─────────────────────────────────
功能：
  1. 抓取 Google News RSS（體育、活動產業相關）
  2. 用 Claude API 抽取事實 + 寫采毓觀點原創文
  3. 自動分類並寫入 Supabase

執行方式：python news_pipeline.py
排程：由 GitHub Actions 自動觸發（每天 3 次）
"""

import os
import sys
import json
import time
import hashlib
import feedparser
from datetime import datetime, timezone, timedelta
from anthropic import Anthropic
from supabase import create_client

# ═══════════════════════════════════════════════════════════════
# 設定區（可在這裡調整）
# ═══════════════════════════════════════════════════════════════

# Google News RSS 來源（可自由增減關鍵字）
NEWS_SOURCES = [
    {
        "name": "全大運/全中運/全運",
        "rss": "https://news.google.com/rss/search?q=%E5%85%A8%E5%A4%A7%E9%81%8B+OR+%E5%85%A8%E4%B8%AD%E9%81%8B+OR+%E5%85%A8%E9%81%8B&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    },
    {
        "name": "台灣體育",
        "rss": "https://news.google.com/rss/search?q=%E5%8F%B0%E7%81%A3+%E9%AB%94%E8%82%B2&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    },
    {
        "name": "活動行銷產業",
        "rss": "https://news.google.com/rss/search?q=%E6%B4%BB%E5%8B%95%E8%A1%8C%E9%8A%B7+OR+%E9%AB%94%E9%A9%97%E8%A1%8C%E9%8A%B7&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    },
]

# 每次執行抓幾篇（總共，跨來源）
MAX_ARTICLES_PER_RUN = 3

# Claude 模型
CLAUDE_MODEL = "claude-sonnet-4-5"

# 分類選項（必須對應網站的分類）
ALLOWED_CATEGORIES = ["足球", "籃球", "田徑", "網球", "排球", "棒球", "活動產業", "科技展演", "其他"]

# 環境變數讀取（GitHub Actions 會自動注入）
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")  # service key, not anon key

if not all([ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_KEY]):
    print("❌ 缺少環境變數: ANTHROPIC_API_KEY / SUPABASE_URL / SUPABASE_SERVICE_KEY")
    sys.exit(1)

claude = Anthropic(api_key=ANTHROPIC_API_KEY)
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

TW_TZ = timezone(timedelta(hours=8))


# ═══════════════════════════════════════════════════════════════
# Step 1: 抓取 Google News
# ═══════════════════════════════════════════════════════════════

def fetch_news():
    """從多個 RSS 來源抓取新聞，回傳合併後的列表"""
    items = []
    for src in NEWS_SOURCES:
        try:
            print(f"📡 抓取: {src['name']}")
            feed = feedparser.parse(src["rss"])
            for entry in feed.entries[:8]:  # 每個來源取前 8 篇
                items.append({
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "source_name": entry.get("source", {}).get("title") or src["name"],
                    "published": entry.get("published", ""),
                    "summary_raw": entry.get("summary", ""),
                    "_source_set": src["name"],
                })
            print(f"   → 取得 {len(feed.entries[:8])} 則")
        except Exception as e:
            print(f"   ⚠️ 抓取失敗: {e}")

    # 去重（依標題）
    seen = set()
    unique = []
    for it in items:
        key = it["title"][:30]
        if key not in seen:
            seen.add(key)
            unique.append(it)

    print(f"\n📊 共取得 {len(unique)} 則去重後新聞\n")
    return unique


# ═══════════════════════════════════════════════════════════════
# Step 2: 過濾已發布過的（避免重複）
# ═══════════════════════════════════════════════════════════════

def title_hash(title: str) -> str:
    return hashlib.md5(title.encode("utf-8")).hexdigest()[:16]

def filter_new(items):
    """過濾掉資料庫已存在的新聞"""
    if not items:
        return []
    hashes = [title_hash(it["title"]) for it in items]
    try:
        existing = sb.table("articles") \
            .select("source_hash") \
            .in_("source_hash", hashes) \
            .execute()
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
    print(f"🔍 過濾後新文章: {len(new_items)} 則")
    return new_items


# ═══════════════════════════════════════════════════════════════
# Step 3: Claude 改寫（B+C 混合：事實 + 采毓觀點）
# ═══════════════════════════════════════════════════════════════

REWRITE_PROMPT = """你是「采毓活動整合行銷有限公司」旗下「采毓新聞」的資深編輯。
公司專長：體育賽事、活動行銷、體驗經濟。
你要從以下原始新聞素材中，**抽取純事實**，再用采毓的角度寫出一篇原創新聞稿。

═══ 原始素材（僅供參考事實，不得直接複製文字）═══
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
  "content": "正文完整內容（不含采毓觀點，純事實重述）\\n\\n采毓觀點\\n\\n（觀點分析內容）\\n\\n資料整理自：{source_name}",
  "tags": ["標籤1", "標籤2", "標籤3"],
  "featured": false
}}

直接輸出 JSON，不要任何其他文字。"""


def rewrite_with_claude(item):
    """呼叫 Claude API 改寫一則新聞"""
    prompt = REWRITE_PROMPT.format(
        title=item["title"],
        source_name=item.get("source_name", "未知來源"),
        link=item["link"],
        summary_raw=item.get("summary_raw", "")[:500],
        categories="、".join(ALLOWED_CATEGORIES),
    )

    try:
        msg = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        # 移除可能的 markdown 包覆
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        result = json.loads(text)
        return result
    except json.JSONDecodeError as e:
        print(f"   ⚠️ JSON 解析失敗: {e}")
        print(f"   原始輸出: {text[:200]}")
        return None
    except Exception as e:
        print(f"   ⚠️ Claude API 失敗: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# Step 4: 寫入 Supabase
# ═══════════════════════════════════════════════════════════════

def insert_article(item, rewritten):
    """把改寫好的文章寫入 Supabase"""
    now = datetime.now(TW_TZ)
    payload = {
        "title": rewritten["title"],
        "category": rewritten["category"] if rewritten["category"] in ALLOWED_CATEGORIES else "其他",
        "summary": rewritten["summary"],
        "content": rewritten["content"],
        "author": "采毓編輯部（AI 輔助）",
        "tags": rewritten.get("tags", []),
        "featured": rewritten.get("featured", False),
        "image": None,  # 之後可手動補圖
        "source_url": item["link"],
        "source_name": item.get("source_name", ""),
        "source_hash": item["source_hash"],
        "published_at": now.isoformat(),
        "is_ai_generated": True,
        "is_published": True,
    }
    try:
        result = sb.table("articles").insert(payload).execute()
        return True
    except Exception as e:
        print(f"   ⚠️ Supabase 寫入失敗: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def main():
    print("═" * 60)
    print(f"🚀 采毓新聞自動化 — {datetime.now(TW_TZ).strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 60)

    # Step 1: 抓新聞
    items = fetch_news()
    if not items:
        print("❌ 沒抓到任何新聞")
        return

    # Step 2: 過濾重複
    new_items = filter_new(items)
    if not new_items:
        print("✅ 所有新聞都已發布過，本次不更新")
        return

    # Step 3+4: 改寫並寫入（限制數量）
    success = 0
    skipped = 0
    failed = 0

    for i, item in enumerate(new_items[:MAX_ARTICLES_PER_RUN * 2], 1):
        if success >= MAX_ARTICLES_PER_RUN:
            break

        print(f"\n[{i}] 處理: {item['title'][:50]}...")
        rewritten = rewrite_with_claude(item)

        if not rewritten:
            failed += 1
            continue
        if rewritten.get("skip"):
            print(f"   ⏭️ 跳過: {rewritten.get('reason', '素材不足')}")
            skipped += 1
            continue

        if insert_article(item, rewritten):
            print(f"   ✅ 已發布: 「{rewritten['title']}」")
            print(f"      分類: {rewritten['category']}, 標籤: {rewritten.get('tags', [])}")
            success += 1
        else:
            failed += 1

        time.sleep(2)  # 避免 API rate limit

    print("\n" + "═" * 60)
    print(f"📊 完成 — 成功:{success} / 跳過:{skipped} / 失敗:{failed}")
    print("═" * 60)


if __name__ == "__main__":
    main()
