-- 新建库时预装 pgvector（迁移 0000_pgvector_extension 也会执行 CREATE EXTENSION，此处为双保险）
CREATE EXTENSION IF NOT EXISTS vector;
