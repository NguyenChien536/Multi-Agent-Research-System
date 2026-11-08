export function researchErrorText(raw: string | null | undefined, isEn: boolean): string {
  const value = (raw || '').toLowerCase();
  const cases: [RegExp, string, string][] = [
    [/manuscript_incomplete/, 'Model chưa viết đủ một phần bắt buộc. Các phần đã lưu vẫn được giữ; bấm Tiếp tục từ bước lỗi để hoàn thiện.', 'A required writing section is incomplete. Saved sections are retained; continue from the failed step.'],
    [/provider_daily_limit/, 'Dịch vụ đã hết hạn mức lượt gọi trong ngày. Chờ dịch vụ đặt lại hạn mức hoặc chọn kết nối khác trong Settings.', 'The provider daily request allowance is exhausted. Wait for its reset or choose another service in Settings.'],
    [/workflow_resume_conflict|invalid_concurrent_graph_update/, 'Không thể tiếp tục bước đã lưu do xung đột trạng thái. Nguồn và kết quả trước đó vẫn được giữ. Làm mới trang và thử lại sau khi hệ thống được cập nhật.', 'The saved workflow could not resume safely. Existing sources and results are retained. Refresh and retry after the workflow fix is deployed.'],
    [/insufficient_evidence/, 'Chưa đủ bằng chứng để viết bài. Hãy bổ sung nguồn phù hợp hoặc dữ liệu kết quả; hệ thống không tự tạo luận điểm và số liệu thay thế.', 'There is not enough evidence to write the article. Add relevant sources or recorded results; unsupported findings will not be fabricated.'],
    [/lengthfinishreason|model_output_truncated/, 'Model hết giới hạn token đầu ra trước khi hoàn tất câu trả lời. Lỗi này không phải do API key. Hãy thử lại với model có đủ dung lượng đầu ra.', 'The model reached its output token limit. This is not an API-key error. Retry with sufficient output capacity.'],
    [/401|provider_auth_failed|unauthorized/, 'Dịch vụ từ chối xác thực. Kiểm tra key còn hoạt động và địa chỉ API thuộc đúng dịch vụ cấp key.', 'Provider rejected authentication. Check the key and matching API address.'],
    [/404|provider_model_not_found|model.*not found/, 'Model không khả dụng với kết nối này. Mở API & model, tải danh sách và chọn model có quyền truy cập.', 'This model is unavailable for your connection. Open API & model, reload the model list and choose an accessible model.'],
    [/503|502|504|provider_unavailable|unavailable|overloaded|high demand/, 'Dịch vụ AI đang quá tải hoặc tạm ngừng (503). Key không nhất thiết bị sai. Chờ một lúc rồi bấm Chạy lại; nguồn và kết quả đã lưu vẫn được giữ.', 'The AI service is temporarily overloaded or unavailable (503). This does not mean your key is invalid. Wait briefly, then retry; saved sources and results are retained.'],
    [/429|quota|rate.limit|request queue|provider_rate_limit/, 'Dịch vụ chạm hạn mức hoặc giới hạn lượt gọi. Hãy chờ và kiểm tra hạn mức miễn phí trước khi thử lại.', 'Provider rate limit or quota reached. Wait and check your free allowance.'],
    [/timeout|timed out/, 'Dịch vụ phản hồi quá lâu. Hãy thử lại sau.', 'Provider response timed out. Retry later.'],
    [/budget/, 'Bài chạm giới hạn token, lượt gọi, thời gian hoặc chi phí ước tính. Xem tùy chọn tăng token và tiếp tục nếu còn lượt gọi, thời gian và chi phí. Đổi model không đặt lại lượng đã dùng.', 'Research allowance reached. Review token extension if cost, call and time allowance remains. Changing the model does not reset usage.'],
    [/json|outputparser/, 'Model trả dữ liệu sai cấu trúc. Hãy dùng model hỗ trợ JSON.', 'Model returned invalid structured data. Try a JSON-compatible model.'],
  ];
  const match = cases.find(([pattern]) => pattern.test(value));
  return match ? match[isEn ? 2 : 1] : (isEn ? 'Research could not finish. Open Agent Monitor to identify the failed step.' : 'Nghiên cứu chưa hoàn tất. Mở Giám sát Agent để xem bước gặp lỗi.');
}

export function ResearchErrorNotice({ error, isEn, step }: { error?: string | null; isEn: boolean; step?: string | null }) {
  return <div id="research-error" role="alert" className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900 print:hidden">
    <strong>{isEn ? 'Research stopped' : 'Nghiên cứu đã dừng'}{step ? ` · ${step}` : ''}</strong>
    <p className="mt-1 leading-relaxed">{researchErrorText(error, isEn)}</p>
  </div>;
}
