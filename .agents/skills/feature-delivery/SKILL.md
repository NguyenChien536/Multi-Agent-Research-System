---
name: feature-delivery
description: Plans, implements, verifies, reviews, and prepares one GitHub Issue as a dedicated branch and pull request using the project's Codex and Antigravity workflow. Use for feature, bug fix, documentation, or chore tasks in this repository.
---

# Feature Delivery (Codex + Antigravity)

Dùng quy trình này cho mỗi GitHub Issue. GitHub Issue là nguồn yêu cầu; Git diff là nguồn sự thật về thay đổi; kết quả lệnh là nguồn sự thật về xác minh.

## Vai trò

- **Người dùng / Nguyễn Đình Chiến:** sở hữu yêu cầu, duyệt thay đổi ảnh hưởng kiến trúc/API/database/bảo mật, xem PR và quyết định merge.
- **Codex:** lập kế hoạch và review độc lập khi khả dụng.
- **Antigravity:** agent triển khai; khi Codex không khả dụng, cũng tự khảo sát, lập kế hoạch và review theo checklist này.

## 1. Nạp bối cảnh và kiểm tra Git

1. Đọc `AGENTS.md`, yêu cầu người dùng, README/SRS liên quan và code hiện có.
2. Với yêu cầu triển khai cụ thể, tìm Issue đang mở có cùng mục tiêu trong repository. Nếu không có, tự tạo Issue qua GitHub connector khi khả dụng, gồm vấn đề, phạm vi, ngoài phạm vi và tiêu chí nghiệm thu suy ra từ yêu cầu. Không tạo Issue cho câu hỏi, review hay tư vấn thuần túy.
3. Nếu GitHub connector không khả dụng, chuẩn bị đầy đủ title/body theo `.github/ISSUE_TEMPLATE/feature.yml`; tiếp tục phần local trong khả năng và nêu rõ Issue chưa được tạo trên GitHub.
4. Kiểm tra `git status`, branch hiện tại và diff. Không ghi đè hoặc xóa thay đổi chưa được lưu.
5. Nếu working tree không sạch, dừng tạo branch mới; báo rõ thay đổi đang có và yêu cầu lưu/hoàn tất chúng trước.
6. Tạo branch riêng cho Issue từ `origin/main` bằng:

   ```powershell
   .\scripts\new-feature-branch.ps1 -Issue 42 -Type feature -Title "Search web sources"
   ```

   Thay ID, loại và tiêu đề theo Issue thực tế. Không dùng lại branch cho Issue khác.

## 2. Lập kế hoạch trước khi sửa

Codex lập plan nếu khả dụng. Nếu không, Antigravity tự lập plan. Plan lưu trong Issue hoặc PR và phải nêu:

- Vấn đề và tiêu chí nghiệm thu.
- File/tầng dự kiến bị ảnh hưởng.
- Hợp đồng API/schema/DB/graph cần giữ tương thích.
- Các bước triển khai và lệnh xác minh.
- Rủi ro, giả định và điều chưa nằm trong phạm vi.

Không tự bịa endpoint, trạng thái hay tính năng chưa có trong code. Thay đổi kiến trúc, API contract, schema dữ liệu, auth/bảo mật hoặc dependency lớn phải được Nguyễn Đình Chiến duyệt trước khi triển khai.

## 3. Triển khai

1. Antigravity triển khai đúng phạm vi Issue và plan.
2. Không chạy song song hai agent ghi vào cùng branch/worktree.
3. Không sửa file ngoài scope nếu chưa giải thích lý do và được chấp thuận.
4. Không tự commit, push, merge hoặc deploy.
5. Nếu phát hiện yêu cầu thiếu hoặc mâu thuẫn với code/SRS, ghi giả định hoặc câu hỏi vào Issue; không che lấp bằng mock/stub.

## 4. Xác minh

- Chạy các kiểm tra phù hợp với phần thay đổi, gồm test/lint/type check/build khi repository có cấu hình tương ứng.
- Với API, đưa lệnh curl mẫu; với graph, nêu state input/output và kết quả invoke; với Docker/DB, ghi lệnh và kết quả chạy thật.
- Phân biệt rõ: **đã chạy thành công**, **đã chạy thất bại**, và **chưa chạy**. Không gọi compile/config parse là kiểm thử end-to-end.
- Không tuyên bố hoàn thành nếu chỉ đọc code mà chưa có bằng chứng cần thiết.

## 5. Review và vòng sửa

1. Nếu Codex khả dụng, yêu cầu Codex xem diff và kết quả xác minh, ưu tiên lỗi correctness, regression, bảo mật, API/schema compatibility và tiêu chí nghiệm thu.
2. Nếu Codex không khả dụng, Antigravity tự review diff theo đúng các mục trên và ghi rõ đây là self-review.
3. Mỗi phát hiện phải có mức độ, file/dòng hoặc tình huống tái hiện, tác động và cách sửa.
4. Antigravity sửa các lỗi được xác nhận; chạy lại các kiểm tra bị ảnh hưởng; review lại diff.
5. Tối đa 3 vòng. Nếu còn lỗi P0/P1, review bất đồng, hoặc cần quyết định thiết kế, dừng và hỏi người dùng.

## 6. Pull Request và hoàn tất

PR về `main` phải:

- Liên kết Issue (`Closes #<id>`).
- Tóm tắt thay đổi và quyết định kỹ thuật.
- Liệt kê lệnh xác minh cùng kết quả thật.
- Nêu phần chưa xác minh, rủi ro và giới hạn.
- Có checklist review hoàn thành trong `.github/PULL_REQUEST_TEMPLATE.md`.

Người dùng review PR và quyết định merge. Sau merge, đóng Issue và xóa branch đã hoàn tất. Không tạo `develop`/`release/*` trừ khi nhóm thống nhất chuyển sang Git Flow đầy đủ.

## Khi Codex hết quota hoặc không khả dụng

Antigravity tiếp tục từ repository, Issue, branch, diff và kết quả kiểm tra; không cần dựa vào cuộc trò chuyện Codex. Tự lập plan nếu chưa có, triển khai, self-review và tạo nội dung PR. Dừng ở bước PR để người dùng duyệt. Không giả vờ rằng self-review là review độc lập của Codex.
