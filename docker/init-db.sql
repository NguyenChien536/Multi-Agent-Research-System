-- Khởi tạo extensions cần thiết cho PostgreSQL
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Đảm bảo quyền truy cập cho user
GRANT ALL PRIVILEGES ON DATABASE ati_research_db TO ati_user;
