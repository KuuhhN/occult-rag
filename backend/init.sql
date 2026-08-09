-- 启用 pgvector 扩展
-- ponytail: 不建手动 documents 表——LangChain PGVector 首次入库自动建
-- langchain_pg_embedding / langchain_pg_collection；不建 IVFFlat 索引，
-- 万级以下向量全表扫描足够快，数据量大时再加
CREATE EXTENSION IF NOT EXISTS vector;
