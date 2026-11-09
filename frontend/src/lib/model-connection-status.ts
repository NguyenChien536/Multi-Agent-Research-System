/** Public, actionable messages; provider response bodies never enter the UI. */
const messages: Record<string, [string, string]> = {
  ok: ['The model returned valid JSON. A full research run still needs its own checks.', 'Model đã trả JSON hợp lệ. Bài nghiên cứu đầy đủ vẫn cần kiểm tra riêng.'],
  catalog_ok: ['Key and model list verified. Generation has not been tested.', 'Đã kiểm tra key và danh sách model; chưa thử sinh nội dung.'],
  quota_exhausted: ['Free daily allowance exhausted. Wait for reset or use another service; switching models on this account may not help.', 'Đã hết hạn mức miễn phí trong ngày. Chờ cấp lại hoặc dùng dịch vụ khác; đổi model cùng tài khoản có thể không giải quyết được.'],
  rate_limited: ['Too many requests. Wait a moment before trying again.', 'Dịch vụ đang giới hạn lượt gọi. Chờ một lúc rồi thử lại.'],
  auth_failed: ['This service rejected the key. Check the selected service and key permissions.', 'Dịch vụ từ chối key. Kiểm tra đúng dịch vụ và quyền của key.'],
  access_denied: ['This key cannot access the model. Check account permissions.', 'Key chưa có quyền dùng model. Kiểm tra quyền của tài khoản.'],
  model_unavailable: ['Model not available with this key. Load the list and choose another model.', 'Model không khả dụng với key này. Tải danh sách và chọn model khác.'],
  timeout: ['The model did not respond in time. Try again later or choose another model.', 'Model không phản hồi kịp. Thử lại sau hoặc chọn model khác.'],
  unsupported_format: ['The service rejected the request format. Check compatibility in Advanced.', 'Dịch vụ không chấp nhận định dạng yêu cầu. Kiểm tra tương thích trong phần Nâng cao.'],
  invalid_output: ['The model replied, but its structured data was invalid. Try another model.', 'Model có phản hồi nhưng dữ liệu không đúng cấu trúc. Thử model khác.'],
  incomplete_output: ['The test response was cut short. Try a model with better structured output support.', 'Phản hồi thử bị cắt ngắn. Thử model hỗ trợ dữ liệu có cấu trúc tốt hơn.'],
  free_tier_confirmation_required: ['Confirm this project uses a free tier before testing a response.', 'Xác nhận project dùng gói miễn phí trước khi thử phản hồi.'],
  catalog_unavailable: ['Could not load models. Check the service or enter its exact model ID in Advanced.', 'Chưa tải được model. Kiểm tra dịch vụ hoặc nhập tên model chính xác trong phần Nâng cao.'],
  invalid_metadata: ['The service returned an unreadable account status. Try again later.', 'Không đọc được trạng thái tài khoản từ dịch vụ. Thử lại sau.'],
  unavailable: ['The service is temporarily unavailable. Try again later or choose another service.', 'Dịch vụ tạm thời không khả dụng. Thử lại sau hoặc chọn dịch vụ khác.'],
};

export function connectionStatusMessage(status: string, isEn: boolean): string {
  return (messages[status] || messages.unavailable)[isEn ? 0 : 1];
}
