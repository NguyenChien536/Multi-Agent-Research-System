export function formatVersionLabel(version: number | undefined, status: string | undefined, isEn: boolean): string {
  const versionLabel = typeof version === 'number' && Number.isSafeInteger(version) && version > 0
    ? `${isEn ? 'Version' : 'Phiên bản'} v${version}`
    : (isEn ? 'Version unavailable' : 'Chưa có số phiên bản');
  const statusLabel = formatReviewStatus(status, isEn);
  return `${versionLabel} · ${statusLabel}`;
}
export function formatReviewStatus(status: string | undefined, isEn: boolean): string {
  const labels: Record<string, [string, string]> = {
    PASSED: ['Automated checks passed', 'Đã qua kiểm tra tự động'],
    NEEDS_REVIEW: ['Review needed', 'Cần kiểm tra'],
    PARTIAL: ['Incomplete draft', 'Bản thảo chưa đầy đủ'],
  };
  return labels[status?.trim() || '']?.[isEn ? 0 : 1]
    || (isEn ? 'Review status unavailable' : 'Chưa có kết quả kiểm tra');
}
