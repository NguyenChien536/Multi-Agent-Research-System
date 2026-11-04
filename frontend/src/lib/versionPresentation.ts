export function formatVersionLabel(version: number | undefined, status: string | undefined, isEn: boolean): string {
  const versionLabel = typeof version === 'number' && Number.isSafeInteger(version) && version > 0
    ? `${isEn ? 'Version' : 'Phiên bản'} v${version}`
    : (isEn ? 'Version unavailable' : 'Chưa có số phiên bản');
  const statusLabel = status?.trim() || (isEn ? 'status unavailable' : 'chưa có trạng thái');
  return `${versionLabel} · ${statusLabel}`;
}
