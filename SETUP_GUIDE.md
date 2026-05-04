# 采毓新聞自動化 — 完整設定指南

預估完成時間：**40-60 分鐘**（不含等待時間）

> 你需要的所有東西都是免費的：GitHub、Supabase、Anthropic API（每月成本約 NT$150-300）

---

## 📋 流程總覽

```
1. 開三個帳號 ← 5 分鐘
2. 建 Supabase 資料庫 ← 10 分鐘
3. 拿 Claude API Key ← 5 分鐘
4. 建 GitHub Repo + 上傳檔案 ← 15 分鐘
5. 設定 GitHub Secrets ← 5 分鐘
6. 手動測試一次 ← 5 分鐘
7. 改造 HTML 讀 Supabase ← 之後再做
```

---

## Step 1：開三個帳號（都免費）

### 1-1. GitHub
- 前往 https://github.com/signup
- 用 Email 註冊，免費版即可

### 1-2. Supabase
- 前往 https://supabase.com
- 用 GitHub 帳號登入即可（最方便）
- 免費 500MB 資料庫空間，對你絕對夠用

### 1-3. Anthropic Console（Claude API）
- 前往 https://console.anthropic.com
- 註冊後到「Billing」儲值最少 USD $5
- 一個月跑下來大概用 USD $3-5（每天 9 篇 × 30 天 ≈ 270 篇）

---

## Step 2：建 Supabase 資料庫

### 2-1. 建立新專案
1. 登入 Supabase Dashboard
2. 點 **「New project」**
3. 填寫：
   - Name: `caiyu-news`
   - Database Password: **記下來**（之後不會再顯示）
   - Region: 選 `Northeast Asia (Tokyo)` 或 `Singapore`（離台灣最近）
4. 等待約 2 分鐘建立完成

### 2-2. 建立資料表
1. 左側選單點 **「SQL Editor」**
2. 點 **「+ New query」**
3. 把 `supabase/schema.sql` 的內容整個貼上去
4. 按 **「Run」**（右下角）
5. 看到綠色 `Success. No rows returned` 就完成了

### 2-3. 取得連線資訊
1. 左側選單點 ⚙️ **「Project Settings」** → **「API」**
2. 記下這兩個值（之後 GitHub Secrets 會用）：
   - **Project URL**：`https://xxxxxx.supabase.co`
   - **service_role key**（⚠️ 不是 anon key）：`eyJhbGciOi...` 很長的字串

> 🔒 **service_role key 千萬不要外洩**，等於資料庫密碼

---

## Step 3：拿 Claude API Key

1. 登入 https://console.anthropic.com
2. 左側 **「API Keys」** → **「Create Key」**
3. 取個名字（例如 `caiyu-news-bot`）
4. **複製 key 並存好**（只會顯示這一次）
5. 確認 Billing 至少有 USD $5 餘額

---

## Step 4：建 GitHub Repo + 上傳檔案

### 4-1. 建 Repo
1. 登入 GitHub，右上角 **「+」** → **「New repository」**
2. 填寫：
   - Repository name: `caiyu-news-pipeline`
   - **Private**（不要 Public，避免別人看到你的設定）
3. 點 **「Create repository」**

### 4-2. 上傳檔案
**最簡單的方法：用網頁直接拖曳**

1. 在新的 repo 頁面，點 **「uploading an existing file」**
2. 把整個 `caiyu-news` 資料夾的內容拖進去
   - 必須包含：
     - `scripts/news_pipeline.py`
     - `scripts/requirements.txt`
     - `.github/workflows/auto-update.yml`
     - `supabase/schema.sql`（保留參考用）
3. 下方填：`Initial commit`
4. 點 **「Commit changes」**

> 如果你會用 git 指令，當然 git push 也行

---

## Step 5：設定 GitHub Secrets（環境變數）

這步很重要 — 把敏感金鑰存到 GitHub，腳本才能用。

1. 在 repo 頁面點 **「Settings」**（不是個人 Settings，是 repo 的）
2. 左側 **「Secrets and variables」** → **「Actions」**
3. 點 **「New repository secret」**，**依序新增三個**：

| Name | Value |
|------|-------|
| `ANTHROPIC_API_KEY` | 你的 Claude API key（`sk-ant-...`） |
| `SUPABASE_URL` | Supabase 的 Project URL |
| `SUPABASE_SERVICE_KEY` | Supabase 的 service_role key |

> 名稱必須**完全一樣**（大小寫、底線都不能錯）

---

## Step 6：手動測試一次

確認設定都對。

1. 在 repo 頁面點 **「Actions」**
2. 左側選 **「采毓新聞自動更新」**
3. 右側點 **「Run workflow」** → 再點一次 **「Run workflow」**
4. 等 1-2 分鐘，重新整理看執行結果

### 成功的樣子
- 看到綠色 ✅ 勾勾
- 點進去 → **「執行新聞自動化腳本」** 步驟可以看到 log
- 應該會有「✅ 已發布: ...」這類訊息
- 到 Supabase **「Table Editor」** → `articles` 表，看到新增了 3 筆資料

### 失敗排查
- ❌ `缺少環境變數` → Step 5 的 Secrets 名稱寫錯
- ❌ `Supabase 寫入失敗` → service_key 用錯了（拿成 anon key）
- ❌ `Claude API 失敗` → API key 錯誤或 Billing 沒儲值

---

## Step 7：之後再做 — 改造 HTML 讀 Supabase

目前的 `news-website.html` 是用 localStorage 儲存。要讓它讀 Supabase 的自動文章，需要改造：

> 這部分等你把 Step 1-6 跑通後，跟我說「來改 HTML」，我再幫你改。

---

## 🎯 完成後你會擁有什麼

| 時間 | 自動行為 |
|------|----------|
| 每天 07:00 | 抓晨間新聞，發 3 篇 |
| 每天 16:30 | 抓下午新聞，發 3 篇 |
| 每天 21:30 | 抓晚間新聞，發 3 篇 |
| **總計** | **每天 9 篇 / 每月 270 篇采毓觀點原創文** |

---

## 💰 月成本預估

| 服務 | 用量 | 費用 |
|------|------|------|
| GitHub Actions | 約 30 分鐘/月 | 免費（每月 2000 分鐘額度） |
| Supabase | < 50 MB | 免費 |
| Claude API | 約 270 篇 × ~3000 token | **約 USD $3-5** |
| **總計** | — | **約 NT$100-200/月** |

---

## ⚠️ 法律小提醒

腳本已經設計成「事實重寫 + 采毓觀點」的安全模式，但仍建議：

1. **每天花 5-10 分鐘人工複審** — 在 Supabase Table Editor 看一下當天文章
2. **發現有問題的文章就刪掉** — 直接在 Supabase 刪
3. **內文已自動標註「資料整理自：xxx」** — 保持誠信

如果未來商業規模變大，建議找智財權律師花 NT$3,000-5,000 做一次諮詢。

---

## ❓ 有問題隨時問我

設定過程任何一步卡住，把錯誤訊息丟給我，我幫你解。
