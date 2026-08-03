-- ============================================================================
-- ECMultiAgents — PostgreSQL 库表初始化 DDL
--
-- 用途：与 src/backend/db/init_data.py 内的 ORM 模型完全对齐。
--       init_data.py 用 metadata.create_all() 动态建表；本脚本用于 DBA /
--       运维在生产/预发布环境手工建表（不走 ORM）的场景。
--
-- 执行顺序：
--   1. CREATE DATABASE cbec;（需在 postgres 库内执行，见下方注释）
--   2. CREATE USER cbec_user;（同上）
--   3. psql -U cbec_user -d cbec -f schema.sql
--
-- 幂等性：所有 CREATE 都带 IF NOT EXISTS；可重复执行。
-- 字符集：UTF8（ORM 端 bcrypt hash / 中文字段都依赖）。
-- 引擎：PostgreSQL 12+（依赖 GENERATED AS IDENTITY 或 SERIAL）。
--
-- 注意：本脚本不创建 DATABASE / USER（DDL 无事务包装，CREATE DATABASE
--       必须在独立事务执行，且当前 user 需 CREATEDB 权限）。
--       如需库本身，请先用 superuser 跑：
--           CREATE USER cbec_user WITH PASSWORD '<your_password>';
--           CREATE DATABASE cbec OWNER cbec_user ENCODING 'UTF8';
-- ============================================================================

-- ── users（用户表，M4.1）──
CREATE TABLE IF NOT EXISTS users (
    id              SERIAL          PRIMARY KEY,
    username        VARCHAR(255)    NOT NULL UNIQUE,
    hashed_password VARCHAR(255)    NOT NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

-- ORM 声明 unique=True + index=True；UNIQUE 约束已隐式建索引，故无需额外 CREATE INDEX。

-- ── product_sales（销售明细表，M4.4）──
CREATE TABLE IF NOT EXISTS product_sales (
    id          SERIAL          PRIMARY KEY,
    platform    VARCHAR(50)     NOT NULL,
    asin        VARCHAR(50)     NOT NULL,
    title       VARCHAR(200)    NOT NULL,
    category    VARCHAR(100)    NOT NULL,
    date        DATE            NOT NULL,
    currency    VARCHAR(10)     NOT NULL,
    sales       DOUBLE PRECISION NOT NULL,
    units       INTEGER         NOT NULL,
    page_views  INTEGER         NOT NULL,
    sessions    INTEGER         NOT NULL
);

-- ORM 显式 index=True 的字段：platform / asin / date
CREATE INDEX IF NOT EXISTS ix_product_sales_platform ON product_sales (platform);
CREATE INDEX IF NOT EXISTS ix_product_sales_asin     ON product_sales (asin);
CREATE INDEX IF NOT EXISTS ix_product_sales_date     ON product_sales (date);

-- ── ad_performance（广告表现表，M4.4）──
CREATE TABLE IF NOT EXISTS ad_performance (
    id           SERIAL          PRIMARY KEY,
    platform     VARCHAR(50)     NOT NULL,
    asin         VARCHAR(50)     NOT NULL,
    campaign     VARCHAR(100)    NOT NULL,
    ad_type      VARCHAR(50)     NOT NULL,
    date         DATE            NOT NULL,
    impressions  INTEGER         NOT NULL,
    clicks       INTEGER         NOT NULL,
    spend        DOUBLE PRECISION NOT NULL,
    ad_sales     DOUBLE PRECISION NOT NULL,
    orders       INTEGER         NOT NULL,
    acos         DOUBLE PRECISION NOT NULL,
    ctr          DOUBLE PRECISION NOT NULL,
    cpc          DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_ad_performance_platform ON ad_performance (platform);
CREATE INDEX IF NOT EXISTS ix_ad_performance_asin     ON ad_performance (asin);
CREATE INDEX IF NOT EXISTS ix_ad_performance_date     ON ad_performance (date);

-- ============================================================================
-- 验证：建表后建议跑
--   \dt                         列出三张表
--   \d users                    查看 users 结构
--   SELECT COUNT(*) FROM users; 应返回 0
-- ============================================================================