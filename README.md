# 采毓新聞自動化系統

> 每天自動抓取 Google News，用 Claude AI 寫成采毓觀點原創文，自動發布到網站。

## 📦 檔案結構

```
caiyu-news/
├── scripts/
│   ├── news_pipeline.py        # 主要自動化腳本
│   └── requirements.txt        # Python 依賴
├── .github/workflows/
│   └── auto-update.yml         # GitHub Actions 排程設定
├── supabase/
│   └── schema.sql              # 資料庫建表 SQL
├── SETUP_GUIDE.md              # ⭐ 完整設定指南（先看這個）
└── README.md                   # 本檔
```

## 🚀 快速開始

**完整步驟看 [SETUP_GUIDE.md](./SETUP_GUIDE.md)**

簡要流程：
1. 開三個帳號：GitHub / Supabase / Anthropic
2. 在 Supabase 跑 `supabase/schema.sql` 建表
3. 拿到 Claude API Key
4. 把整個資料夾內容上傳到 GitHub Repo
5. 設定 GitHub Secrets（API Keys）
6. 手動測試 → 自動排程

## 📅 排程

每天三次自動執行（台灣時間）：
- 07:00 — 晨間新聞
- 16:30 — 午後新聞
- 21:30 — 晚間新聞

每次發 3 篇 → 每日 9 篇 → 每月約 270 篇

## 🎯 寫作策略：B+C 混合

- **B (事實重寫)**：只用原文中的事實（人名、日期、數據），文字完全自己重寫
- **C (采毓觀點)**：每篇文末加上采毓的活動行銷/體驗經濟觀點

✅ 法律風險低
✅ 內容有差異化
✅ 完全自動化
✅ 仍建議每日 5-10 分鐘人工複審

## 💰 成本

每月約 NT$100-200（主要是 Claude API 費用）

## 🛠 技術棧

- **語言**：Python 3.11
- **AI**：Claude Sonnet 4.5
- **資料庫**：Supabase (PostgreSQL)
- **排程**：GitHub Actions
- **新聞來源**：Google News RSS

## 📞 設定有問題？

把錯誤訊息丟回 Claude 對話，我幫你解。
