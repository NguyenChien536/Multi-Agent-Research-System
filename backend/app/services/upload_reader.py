"""Bounded asynchronous reads for user-uploaded files."""


class UploadSizeLimitExceeded(Exception):
    """Raised as soon as a streamed upload exceeds its configured limit."""


async def read_upload_with_limit(upload_file, max_size_bytes: int, chunk_size: int = 64 * 1024) -> bytes:
    """Read an upload in bounded chunks and stop after observing limit + 1 bytes."""
    if max_size_bytes < 0 or chunk_size <= 0:
        raise ValueError("Upload limits must be positive")

    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = await upload_file.read(min(chunk_size, max_size_bytes - size + 1))
        if not chunk:
            break
        size += len(chunk)
        if size > max_size_bytes:
            raise UploadSizeLimitExceeded
        chunks.append(chunk)
    return b"".join(chunks)
