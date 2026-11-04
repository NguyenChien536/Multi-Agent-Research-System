export function researchErrorText(raw: string | null | undefined, isEn: boolean): string {
  const value = (raw || '').toLowerCase();
  const cases: [RegExp, string, string][] = [
    [/insufficient_evidence/, 'Chưa đủ bằng chứng để viết bài. Hãy bổ sung nguồn phù hợp hoặc dữ liệu kết quả; hệ thống không tự tạo luận điểm và số liệu thay thế.', 'There is not enough evidence to write the article. Add relevant sources or recorded results; unsupported findings will not be fabricated.'],
    [/lengthfinishreason|model_output_truncated/, 'Model hết giới hạn token đầu ra trước khi hoàn tất câu trả lời. Lỗi này không phải do API key. Hãy thử lại với model có đủ dung lượng đầu ra.', 'The model reached its output token limit. This is not an API-key error. Retry with sufficient output capacity.'],
    [/401|provider_auth_failed|unauthorized/, 'Dịch vụ từ chối xác thực. Kiểm tra key còn hoạt động và địa chỉ API thuộc đúng dịch vụ cấp key.', 'Provider rejected authentication. Check the key and matching API address.'],
    [/429|quota|rate.limit|provider_rate_limit/, 'Dịch vụ chạm hạn mức hoặc giới hạn lượt gọi. Hãy chờ và kiểm tra hạn mức miễn phí trước khi thử lại.', 'Provider rate limit or quota reached. Wait and check your free allowance.'],
    [/timeout|timed out/, 'Dịch vụ phản hồi quá lâu. Hãy thử lại sau.', 'Provider response timed out. Retry later.'],
    [/budget/, 'Bài chạm giới hạn token, lượt gọi, thời gian hoặc chi phí ước tính. Đổi model không đặt lại ngân sách; hãy tạo bài mới nếu cần một lượt nghiên cứu mới.', 'Research allowance reached. Changing the model does not reset usage; create a new article for a fresh research run.'],
    [/json|outputparser/, 'Model trả dữ liệu sai cấu trúc. Hãy dùng model hỗ trợ JSON.', 'Model returned invalid structured data. Try a JSON-compatible model.'],
  ];
  const match = cases.find(([pattern]) => pattern.test(value));
  return match ? match[isEn ? 2 : 1] : (isEn ? 'Research could not finish. Open Agent Monitor to identify the failed step.' : 'Nghiên cứu chưa hoàn tất. Mở Giám sát Agent để xem bước gặp lỗi.');
}

export function ResearchErrorNotice({ error, isEn }: { error?: string | null; isEn: boolean }) {
  return <div role="alert" className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900 print:hidden">
    <strong>{isEn ? 'Research stopped' : 'Nghiên cứu đã dừng'}</strong>
    <p className="mt-1 leading-relaxed">{researchErrorText(error, isEn)}</p>
  </div>;
}
