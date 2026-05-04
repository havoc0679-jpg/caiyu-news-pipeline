-- ═══════════════════════════════════════════════════════════
-- 采毓新聞 Supabase 資料庫 Schema
-- 在 Supabase SQL Editor 貼上此檔執行即可
-- ═══════════════════════════════════════════════════════════

-- 文章表
CREATE TABLE IF NOT EXISTS articles (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    summary TEXT,
    content TEXT NOT NULL,
    author TEXT DEFAULT '采毓編輯部',
    tags TEXT[] DEFAULT '{}',
    featured BOOLEAN DEFAULT FALSE,
    image TEXT,
    
    -- 自動化相關欄位
    source_url TEXT,
    source_name TEXT,
    source_hash TEXT UNIQUE,           -- 防止重複抓取的指紋
    is_ai_generated BOOLEAN DEFAULT FALSE,
    is_published BOOLEAN DEFAULT TRUE,
    
    -- 時間戳記
    published_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 索引：加快查詢速度
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);
CREATE INDEX IF NOT EXISTS idx_articles_featured ON articles(featured) WHERE featured = TRUE;
CREATE INDEX IF NOT EXISTS idx_articles_source_hash ON articles(source_hash);

-- 自動更新 updated_at 欄位
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_articles_updated_at ON articles;
CREATE TRIGGER update_articles_updated_at
    BEFORE UPDATE ON articles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ═══════════════════════════════════════════════════════════
-- Row Level Security (RLS) 設定
-- 公開讀取，僅 service_key 能寫入
-- ═══════════════════════════════════════════════════════════

ALTER TABLE articles ENABLE ROW LEVEL SECURITY;

-- 任何人（含未登入訪客）都能讀已發布的文章
DROP POLICY IF EXISTS "Public can read published articles" ON articles;
CREATE POLICY "Public can read published articles"
    ON articles FOR SELECT
    USING (is_published = TRUE);

-- 寫入需要 service_key（GitHub Actions 用）
-- 預設不開放 anon 寫入，符合安全性要求
