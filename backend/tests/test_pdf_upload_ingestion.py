import io
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from pypdf import PdfWriter
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.report import ExportArtifact
from app.models.source import DocumentChunk, ResearchSource
from app.services.artifact_store import ArtifactStore
from app.services.pdf_parser import (
    extract_text_from_pdf,
    validate_pdf_bytes,
    PdfOcrRequiredError,
    PdfPageLimitError,
    PdfSizeLimitError,
    PdfValidationError,
)
from app.tools.embedder import EmbedderTool


def make_valid_pdf_bytes(text: str = "Research on multi-agent systems and large language models for scientific automation.") -> bytes:
    """Tạo tệp PDF chuẩn có nội dung văn bản hợp lệ bằng cú pháp PDF tiêu chuẩn."""
    text_escaped = text.replace("(", r"\(").replace(")", r"\)")
    stream_content = f"BT\n/F1 12 Tf\n72 712 Td\n({text_escaped}) Tj\nET\n".encode("utf-8")
    stream_len = len(stream_content)

    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
        b"4 0 obj << /Length " + str(stream_len).encode("ascii") + b" >> stream\n"
        + stream_content +
        b"endstream\nendobj\n"
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
        b"xref\n"
        b"0 6\n"
        b"0000000000 65535 f \n"
        b"trailer << /Size 6 /Root 1 0 R >>\n"
        b"startxref\n"
        b"450\n"
        b"%%EOF\n"
    )
    return pdf


def make_blank_pdf_bytes(pages: int = 1) -> bytes:
    """Tạo file PDF trắng không có text (mô phỏng file scan hoặc tài liệu rỗng)."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=300, height=300)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_artifact_store_operations(tmp_path):
    """Kiểm tra lưu trữ, mã băm SHA256 và chống path traversal của ArtifactStore."""
    store = ArtifactStore(base_dir=str(tmp_path))
    task_id = uuid.uuid4()

    # 1. Lưu file an toàn
    content = b"sample pdf content for unit test"
    res = store.save_artifact(task_id, "test document.pdf", content)
    assert res["file_name"] == "test_document.pdf"
    assert res["file_size_bytes"] == len(content)
    assert len(res["sha256_hash"]) == 64

    # 2. Đọc file
    path = store.get_artifact_path(task_id, "test_document.pdf")
    assert path is not None
    assert path.read_bytes() == content

    # 3. Path traversal attack phải được xử lý an toàn
    evil_res = store.save_artifact(task_id, "../../etc/passwd.pdf", content)
    assert evil_res["file_name"] == "passwd.pdf"
    assert store.base_dir in store.get_artifact_path(task_id, "passwd.pdf").parents

    # 4. Xóa toàn bộ artifacts của task
    count = store.delete_task_artifacts(task_id)
    assert count == 2
    assert store.get_artifact_path(task_id, "test_document.pdf") is None


@pytest.mark.asyncio
async def test_pdf_parser_validation():
    """Kiểm tra validation định dạng, dung lượng, số trang và OCR limit."""
    # 1. Non-PDF magic header
    with pytest.raises(PdfValidationError, match="Định dạng file không hợp lệ"):
        validate_pdf_bytes(b"NOT_A_PDF_CONTENT")

    # 2. File size limit
    fake_huge = b"%PDF-" + b"0" * (settings.MAX_UPLOAD_SIZE_BYTES + 10)
    with pytest.raises(PdfSizeLimitError, match="Dung lượng file vượt quá giới hạn"):
        validate_pdf_bytes(fake_huge)

    # 3. Valid text extraction
    valid_pdf = make_valid_pdf_bytes("Deep learning models for scientific discovery and advanced research systems.")
    parsed = extract_text_from_pdf(valid_pdf)
    assert parsed["page_count"] == 1
    assert "scientific discovery" in parsed["text"]
    assert parsed["char_count"] > 30

    # 4. Scanned / image-only / textless PDF (Không hỗ trợ OCR)
    blank_pdf = make_blank_pdf_bytes(pages=1)
    with pytest.raises(PdfOcrRequiredError, match="không hỗ trợ OCR"):
        extract_text_from_pdf(blank_pdf)

    # 5. Page count limit (> 100 trang)
    writer = PdfWriter()
    for _ in range(105):
        writer.add_blank_page(width=100, height=100)
    buf = io.BytesIO()
    writer.write(buf)
    overpage_pdf = buf.getvalue()

    with pytest.raises(PdfPageLimitError, match="vượt quá giới hạn số trang cho phép"):
        extract_text_from_pdf(overpage_pdf)


@pytest.mark.asyncio
async def test_pdf_upload_api_and_ownership():
    """Kiểm tra endpoint upload PDF, phân quyền, trích xuất text và lưu DocumentChunks."""
    suffix = uuid.uuid4().hex[:10]
    user1_data = {"username": f"uploader_{suffix}", "email": f"uploader_{suffix}@example.com", "password": "SecurePass123!"}
    user2_data = {"username": f"outsider_{suffix}", "email": f"outsider_{suffix}@example.com", "password": "SecurePass123!"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Đăng ký và đăng nhập 2 người dùng
        await client.post("/api/v1/auth/register", json=user1_data)
        login1 = await client.post("/api/v1/auth/login", json={"email": user1_data["email"], "password": user1_data["password"]})
        token1 = login1.json()["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        await client.post("/api/v1/auth/register", json=user2_data)
        login2 = await client.post("/api/v1/auth/login", json={"email": user2_data["email"], "password": user2_data["password"]})
        token2 = login2.json()["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        # 1. Tạo task của User 1
        create_res = await client.post(
            "/api/v1/research",
            json={"title": "PDF Ingestion Task", "research_question": "Phân tích tài liệu PDF nội bộ"},
            headers=headers1,
        )
        assert create_res.status_code == 201
        task_id = create_res.json()["id"]

        pdf_bytes = make_valid_pdf_bytes()

        # 2. Không có token -> 401
        unauth_res = await client.post(
            f"/api/v1/research/{task_id}/upload",
            files={"file": ("paper.pdf", pdf_bytes, "application/pdf")},
        )
        assert unauth_res.status_code == 401

        # 3. User 2 tải lên vào task của User 1 -> 404 (Owner isolation)
        cross_res = await client.post(
            f"/api/v1/research/{task_id}/upload",
            files={"file": ("paper.pdf", pdf_bytes, "application/pdf")},
            headers=headers2,
        )
        assert cross_res.status_code == 404

        # 4. Tải file không phải PDF -> 400
        invalid_res = await client.post(
            f"/api/v1/research/{task_id}/upload",
            files={"file": ("document.txt", b"plain text content", "text/plain")},
            headers=headers1,
        )
        assert invalid_res.status_code == 400
        assert "Định dạng file không hợp lệ" in invalid_res.json()["detail"]

        # 5. Tải file PDF trắng (không có text) -> 422 (OCR required guidance)
        blank_pdf = make_blank_pdf_bytes(pages=1)
        blank_res = await client.post(
            f"/api/v1/research/{task_id}/upload",
            files={"file": ("scanned.pdf", blank_pdf, "application/pdf")},
            headers=headers1,
        )
        assert blank_res.status_code == 422
        assert "không hỗ trợ OCR" in blank_res.json()["detail"]

        # 6. Tải file PDF hợp lệ của User 1 -> 201 Created
        upload_res = await client.post(
            f"/api/v1/research/{task_id}/upload",
            files={"file": ("autonomous_agents.pdf", pdf_bytes, "application/pdf")},
            headers=headers1,
        )
        assert upload_res.status_code == 201
        upload_data = upload_res.json()
        assert upload_data["source_tag"] == "src_01"
        assert upload_data["file_name"] == "autonomous_agents.pdf"
        assert upload_data["page_count"] == 1
        assert upload_data["chunks_count"] > 0
        assert len(upload_data["sha256_hash"]) == 64

        # 7. Kiểm tra cơ sở dữ liệu đã lưu ResearchSource, ExportArtifact và DocumentChunk
        async with AsyncSessionLocal() as session:
            src = await session.scalar(
                select(ResearchSource).where(ResearchSource.id == uuid.UUID(upload_data["source_id"]))
            )
            assert src is not None
            assert src.source_type == "PDF"
            assert src.source_tag == "src_01"

            art = await session.scalar(
                select(ExportArtifact).where(ExportArtifact.id == uuid.UUID(upload_data["artifact_id"]))
            )
            assert art is not None
            assert art.export_type == "PDF_UPLOAD"
            assert str(art.id) in art.download_url

            chunks = (
                await session.scalars(
                    select(DocumentChunk).where(DocumentChunk.source_id == src.id)
                )
            ).all()
            assert len(chunks) == upload_data["chunks_count"]
            assert any("multi-agent" in c.content for c in chunks)

        # 8. Xem danh sách artifacts (GET /artifacts)
        art_list_res = await client.get(
            f"/api/v1/research/{task_id}/artifacts",
            headers=headers1,
        )
        assert art_list_res.status_code == 200
        artifacts = art_list_res.json()
        assert len(artifacts) == 1
        assert artifacts[0]["id"] == upload_data["artifact_id"]

        # User 2 không xem được artifacts của User 1 -> 404
        art_list_cross = await client.get(
            f"/api/v1/research/{task_id}/artifacts",
            headers=headers2,
        )
        assert art_list_cross.status_code == 404

        # 9. Tải xuống file (GET /artifacts/{artifact_id}/download)
        art_id = upload_data["artifact_id"]
        download_res = await client.get(
            f"/api/v1/research/{task_id}/artifacts/{art_id}/download",
            headers=headers1,
        )
        assert download_res.status_code == 200
        assert download_res.headers["content-type"] == "application/pdf"
        assert download_res.content == pdf_bytes

        # User 2 không tải xuống được file của User 1 -> 404
        download_cross = await client.get(
            f"/api/v1/research/{task_id}/artifacts/{art_id}/download",
            headers=headers2,
        )
        assert download_cross.status_code == 404

        # 10. Chunks tìm kiếm được qua EmbedderTool
        embedder = EmbedderTool()
        async with AsyncSessionLocal() as session:
            similar = await embedder.search_similar_chunks(
                db=session,
                task_id=uuid.UUID(task_id),
                query="language models",
                limit=3,
            )
            assert len(similar) > 0
            retrieved_chunk = similar[0][0]
            assert "multi-agent" in retrieved_chunk.content

        # 11. Xóa task -> artifacts bị xóa và file trên đĩa được dọn dẹp
        del_res = await client.delete(
            f"/api/v1/research/{task_id}",
            headers=headers1,
        )
        assert del_res.status_code == 200
