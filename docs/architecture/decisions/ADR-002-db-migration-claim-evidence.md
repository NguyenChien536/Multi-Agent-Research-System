# ADR-002: Database Migration — ClaimEvidence Junction Table & Citation.chunk_id FK

| Thuộc tính | Giá trị |
|:---|:---|
| **ID** | ADR-002 |
| **Ngày** | 2026-10-01 |
| **Trạng thái** | ✅ Accepted về thiết kế; implementation/runtime chưa xác minh |
| **Migration file** | `backend/alembic/versions/a1b2c3d4e5f6_add_claim_evidence_junction_and_citation_chunk_fk.py` |
| **Revision** | `a1b2c3d4e5f6` (revises `5ee074153cf3`) |

---

## Trạng thái implementation và vấn đề dữ liệu

Đọc source 08/10: ClaimEvidence, Citation.chunk_id nullable và migration đã được commit tại `ebb525a`. Đây là source inventory, không phải bằng chứng migration đã chạy. Baseline DB gần nhất vẫn ghi revision 5ee074153cf3; cần kiểm tra DB rỗng trước khi áp dụng.

## Vấn đề (Tech Debt)

Ở database baseline revision 5ee074153cf3, schema còn 2 vấn đề ảnh hưởng tính traceability. Model/migration đã commit có thay đổi tương ứng nhưng chưa được xác minh trên database:

### 1. `ResearchClaim.evidence_ids` — UUID Array
```sql
-- Hiện tại (tech debt):
evidence_ids UUID[]   -- không có FK cho từng phần tử; không lưu relevance theo từng quan hệ
```
**Hệ quả:** Có thể JOIN bằng `ANY` hoặc `unnest`, nhưng database không tự bảo đảm từng UUID tham chiếu Evidence hợp lệ. Junction table hỗ trợ FK và metadata theo quan hệ; kiểm cùng task và semantic support vẫn là các bước riêng.

### 2. `Citation.chunk_reference` — String thay vì FK
```sql
-- Hiện tại (tech debt):
chunk_reference VARCHAR(100)  -- chỉ là text label, không ràng buộc với DocumentChunk
```
**Hệ quả:** Không thể JOIN để xác minh chunk tồn tại và thuộc đúng source/task.

---

## Giải pháp

### Schema minh họa sau migration

Đây là trích lược cấu trúc, không thay script Alembic có index/backfill. Source hiện tại backfill `citations.research_task_id` từ report rồi đặt NOT NULL ngay trong cùng migration; `chunk_id` vẫn nullable và `chunk_reference` được giữ làm fallback. Các constraint cùng task của thiết kế mới còn cần triển khai ở P2.

```sql
-- Bảng mới: junction table thay thế UUID array
CREATE TABLE claim_evidences (
    claim_id    UUID REFERENCES research_claims(id) ON DELETE CASCADE,
    evidence_id UUID REFERENCES evidences(id)       ON DELETE CASCADE,
    relevance_score FLOAT,
    PRIMARY KEY (claim_id, evidence_id)
);

-- Cột bỏ:
ALTER TABLE research_claims DROP COLUMN evidence_ids;

-- Cột thêm vào citations:
ALTER TABLE citations ADD COLUMN chunk_id UUID REFERENCES document_chunks(id) ON DELETE SET NULL;
ALTER TABLE citations ADD COLUMN research_task_id UUID REFERENCES research_tasks(id) ON DELETE CASCADE;
ALTER TABLE citations ADD COLUMN citation_number INT;

-- Cột thêm vào research_sources (ADR-001 image support):
ALTER TABLE research_sources ADD COLUMN attribution VARCHAR(500);
ALTER TABLE research_sources ADD COLUMN provider_name VARCHAR(100);
ALTER TABLE research_sources ADD COLUMN license_name VARCHAR(200);
ALTER TABLE research_sources ADD COLUMN source_page_url TEXT;
```

---

## Cách chạy migration

### Yêu cầu
- Docker Compose đang chạy (`docker compose up -d`)
- Database đang ở revision `5ee074153cf3` (kiểm tra: `docker compose exec -T backend alembic current`)

### Chạy upgrade

```bash
# 1. Kiểm tra revision hiện tại
docker compose exec -T backend alembic current

# 2. Chạy migration mới
docker compose exec -T backend alembic upgrade head

# 3. Xác minh
docker compose exec -T backend alembic current
# Kết quả mong đợi: a1b2c3d4e5f6 (head)

# 4. Kiểm tra bảng mới đã tồn tại
docker compose exec -T postgres psql -U research_user -d research_db -c "\dt claim_evidences"
docker compose exec -T postgres psql -U research_user -d research_db -c "\d citations"
```

### Rollback nếu cần

```bash
docker compose exec -T backend alembic downgrade 5ee074153cf3
```

> ⚠️ **Lưu ý rollback:** Downgrade sẽ cố gắng khôi phục `evidence_ids` từ junction table. Nếu DB production có dữ liệu thật, phải backup trước khi downgrade.

---

## Các bước tiếp theo sau migration

| Bước | Mô tả | Ai làm |
|:---|:---|:---|
| **1** | Cập nhật Analyst agent: lưu `ClaimEvidence` thay vì append vào `evidence_ids` | Chiến |
| **2** | Cập nhật Writer agent: populate `Citation.chunk_id` khi tạo citation | Chiến |
| **3** | Cập nhật Citation Validator: dùng JOIN thay vì `ANY(evidence_ids)` | Chiến |
| **4** | Sau khi Writer đã populate `chunk_id` đầy đủ: tạo migration mới drop `chunk_reference` | Chiến |
| **5** | Xác minh backfill và NOT NULL của `research_task_id` trong migration hiện có; bổ sung constraints cùng task ở P2, không tạo migration tighten trùng | Chiến |
| **6** | Kiểm thử: Vũ rà scenario thủ công theo checklist; Chiến viết/chạy automated tests cho lineage claim → evidence → chunk → source | Chiến (automated), Vũ (manual) |

---

## Xem thêm

- [grounding.py](../../../backend/app/models/grounding.py) — SQLAlchemy models đã cập nhật
- [source.py](../../../backend/app/models/source.py) — ResearchSource với attribution fields
- [ADR-001](./ADR-001-image-search-provider.md) — Image Discovery and optional Serper.dev provider
- [system-design.md — Diagram 5 Core ERD](../system-design.md)
