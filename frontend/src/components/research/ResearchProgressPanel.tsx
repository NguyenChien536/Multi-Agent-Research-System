import Link from "next/link";
import {
  Activity,
  Download,
  FileText,
  Layers,
  Play,
  RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { researchErrorText } from "@/components/ResearchErrorNotice";
import type { ResearchTaskResponse } from "@/types";

interface ResearchProgressPanelProps {
  task: ResearchTaskResponse;
  isEn: boolean;
  language: "en" | "vi";
  isWorking: boolean;
  isStarting: boolean;
  sourceCount: number;
  citationCount: number;
  runCount: number;
  onStartTask: () => Promise<void>;
  onRefresh: () => void;
  statusLabel: (status: string, language: "en" | "vi") => string;
  stepLabel: (step: string, language: "en" | "vi") => string;
}

export function ResearchProgressPanel({
  task,
  isEn,
  language,
  isWorking,
  isStarting,
  sourceCount,
  citationCount,
  runCount,
  onStartTask,
  onRefresh,
  statusLabel,
  stepLabel,
}: ResearchProgressPanelProps) {
  return (
    <div className="w-full max-w-5xl mx-auto space-y-6">
      {/* Live Execution Status Hero */}
      <div
        className={`p-6 sm:p-8 rounded-2xl border transition-all ${
          task.status === "QUEUED"
            ? "bg-gradient-to-b from-zinc-50 to-white border-zinc-300 shadow-sm"
            : task.status === "PLANNING"
              ? "bg-gradient-to-b from-blue-50/70 to-white border-blue-200 shadow-sm"
              : isWorking
                ? "bg-gradient-to-b from-blue-50/60 to-white border-blue-200 shadow-sm"
                : task.status === "FAILED"
                  ? "bg-gradient-to-b from-red-50/60 to-white border-red-200"
                  : "bg-white border-zinc-200 shadow-sm"
        }`}
      >
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-5">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              {task.status === "QUEUED" ? (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-zinc-200/80 text-zinc-800 text-xs font-bold uppercase tracking-wider">
                  <span className="w-2 h-2 rounded-full bg-zinc-500 animate-pulse" />
                  {isEn ? "Task Queued" : "Đang chờ xếp hàng"}
                </span>
              ) : task.status === "PLANNING" ? (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-100 text-blue-900 text-xs font-bold uppercase tracking-wider">
                  <span className="w-2 h-2 rounded-full bg-blue-600 animate-pulse" />
                  {isEn ? "Planning Phase" : "Giai đoạn lập kế hoạch"}
                </span>
              ) : isWorking ? (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-100 text-blue-900 text-xs font-bold uppercase tracking-wider">
                  <span className="w-2 h-2 rounded-full bg-blue-600 animate-pulse" />
                  {statusLabel(task.status, language)}
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-zinc-100 text-zinc-800 text-xs font-bold uppercase tracking-wider">
                  {statusLabel(task.status, language)}
                </span>
              )}

              {task.current_step && isWorking && (
                <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-800 border border-blue-200">
                  {stepLabel(task.current_step, language)}
                </span>
              )}
            </div>

            <h2 className="text-xl sm:text-2xl font-bold text-zinc-900 tracking-tight">
              {task.provider_wait && task.status === "QUEUED"
                ? isEn
                  ? "Waiting for the AI service"
                  : "Tạm chờ dịch vụ AI"
                : task.status === "QUEUED"
                  ? isEn
                    ? "Research task is queued for processing"
                    : "Bài nghiên cứu đang trong hàng đợi chuẩn bị xử lý"
                  : task.status === "PLANNING"
                    ? isEn
                      ? "Supervisor Agent is planning research strategy & queries"
                      : "Supervisor Agent đang phân tích đề tài & thiết lập từ khóa"
                    : isWorking
                      ? isEn
                        ? "Autonomous agents are gathering and synthesizing evidence"
                        : "Các tác tử tự trị đang thu thập và phân tích dữ liệu"
                      : task.status === "FAILED"
                        ? isEn
                          ? "Research stopped due to an execution error"
                          : "Bài nghiên cứu đã dừng do phát sinh lỗi"
                        : task.status === "WAITING_USER_DATA"
                          ? isEn
                            ? "Waiting for your data"
                            : "Đang chờ dữ liệu của bạn"
                          : task.status === "WAITING_APPROVAL"
                            ? isEn
                              ? "Review the research plan above"
                              : "Duyệt kế hoạch nghiên cứu ở trên"
                            : task.status === "CANCELLED"
                              ? isEn
                                ? "Research task was cancelled"
                                : "Bài nghiên cứu đã được hủy"
                              : isEn
                                ? "Research task is ready to begin"
                                : "Bài nghiên cứu sẵn sàng bắt đầu"}
            </h2>

            {(() => {
              const desc =
                task.provider_wait && task.status === "QUEUED"
                  ? isEn
                    ? "Saved progress will resume automatically after the provider cooldown."
                    : "Tiến độ đã lưu sẽ tự tiếp tục khi hết thời gian chờ dịch vụ."
                  : task.status === "QUEUED"
                    ? isEn
                      ? "Your research question has been registered. The system is preparing to initiate literature discovery. Updates automatically."
                      : "Đề tài nghiên cứu đã được ghi nhận. Hệ thống đang chuẩn bị bắt đầu tìm kiếm và tổng hợp tài liệu. Giao diện tự động cập nhật."
                    : isWorking
                      ? null
                      : task.status === "FAILED"
                        ? isEn
                          ? researchErrorText(task.latest_error, true)
                          : researchErrorText(task.latest_error, false)
                        : task.status === "WAITING_USER_DATA"
                          ? isEn
                            ? "Your progress is saved. Upload the requested data above to continue this article."
                            : "Tiến độ đã được lưu. Tải dữ liệu ở ô phía trên để tiếp tục bài này."
                          : task.status === "WAITING_APPROVAL"
                            ? isEn
                              ? "Approve or revise the proposed plan before research continues."
                              : "Duyệt hoặc yêu cầu sửa kế hoạch trước khi tiếp tục nghiên cứu."
                            : task.status === "CANCELLED"
                              ? isEn
                                ? "Execution was manually cancelled. You can restart the pipeline at any time with the button below."
                                : "Tiến trình đã được dừng theo lệnh người dùng. Bạn có thể bấm khởi động lại bất cứ lúc nào."
                              : isEn
                                ? "Click 'Start Research Now' to deploy the multi-agent pipeline."
                                : "Nhấn 'Bắt đầu nghiên cứu ngay' để khởi chạy chuỗi tác tử.";
              return desc ? (
                <p className="text-sm text-zinc-600 leading-relaxed max-w-2xl">
                  {desc}
                </p>
              ) : null;
            })()}
          </div>

          {/* Real-time stats / action buttons */}
          <div className="flex flex-col sm:flex-row md:flex-col gap-2.5 shrink-0 self-start md:self-center">
            {(task.status === "PENDING" || task.status === "CANCELLED") && (
              <Button
                variant="primary"
                onClick={() => void onStartTask()}
                isLoading={isStarting}
                className="h-10 px-5 text-sm font-semibold bg-zinc-900 hover:bg-zinc-800 text-white shadow-sm"
              >
                <Play size={16} className="mr-2" />
                {task.status === "CANCELLED"
                  ? isEn
                    ? "Rerun Research"
                    : "Chạy lại nghiên cứu"
                  : isEn
                    ? "Start Research Now"
                    : "Bắt đầu nghiên cứu ngay"}
              </Button>
            )}

            <Link
              href={`/research/${task.id}/monitor`}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 text-xs sm:text-sm font-semibold text-white hover:bg-blue-700 transition-colors shadow-sm"
            >
              <Activity size={16} />
              <span>
                {isEn ? "Open Live Monitor" : "Mở màn hình giám sát trực tiếp"}
              </span>
            </Link>

            <Button
              variant="outline"
              onClick={() => onRefresh()}
              className="h-9 px-3 text-xs border-zinc-200 text-zinc-700 hover:bg-zinc-100"
            >
              <RefreshCw size={13} className="mr-1.5" />
              <span>{isEn ? "Refresh Status" : "Làm mới trạng thái"}</span>
            </Button>
          </div>
        </div>

        {/* Live counters if active */}
        {(isWorking || sourceCount > 0 || runCount > 0) && (
          <div className="mt-5 pt-4 border-t border-zinc-200/80 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div className="bg-white/80 p-3 rounded-xl border border-zinc-200">
              <span className="text-zinc-500 font-medium block">
                {isEn ? "Sources Found" : "Nguồn thu thập"}
              </span>
              <span className="text-lg font-bold text-zinc-900">
                {sourceCount}
              </span>
            </div>
            <div className="bg-white/80 p-3 rounded-xl border border-zinc-200">
              <span className="text-zinc-500 font-medium block">
                {isEn ? "Source-linked Claims" : "Luận điểm có nguồn"}
              </span>
              <span className="text-lg font-bold text-zinc-900">
                {citationCount}
              </span>
            </div>
            <div className="bg-white/80 p-3 rounded-xl border border-zinc-200">
              <span className="text-zinc-500 font-medium block">
                {isEn ? "Tokens Consumed" : "Tokens tiêu thụ"}
              </span>
              <span className="text-lg font-bold text-zinc-900 font-mono">
                {task.total_tokens_used.toLocaleString()}
              </span>
            </div>
            <div className="bg-white/80 p-3 rounded-xl border border-zinc-200">
              <span className="text-zinc-500 font-medium block">
                {isEn ? "Estimated Cost" : "Chi phí ước tính"}
              </span>
              <span className="text-lg font-bold text-emerald-700 font-mono">
                ${Number(task.total_cost_usd).toFixed(4)}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Keep the next action visible; supporting deliverables are optional detail. */}
      {task.status !== "FAILED" && task.current_step !== "BUDGET_LIMIT" && (
        <details className="rounded-xl border border-zinc-200 bg-white">
          <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-zinc-800">
            {isEn
              ? "What this run may produce"
              : "Lượt chạy này có thể tạo gì?"}
          </summary>
          <div className="space-y-3 px-4 pb-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-bold text-base sm:text-lg text-zinc-900">
                  {isEn
                    ? "Expected Research Deliverables"
                    : "Các sản phẩm hệ thống sẽ bàn giao"}
                </h3>
                <p className="text-xs text-zinc-600 mt-0.5">
                  {isEn
                    ? "A run may produce a draft and supporting records for the selected study type. Outputs can be incomplete and require human review."
                    : "Sau một lượt chạy, hệ thống có thể tạo bản thảo và hồ sơ hỗ trợ phù hợp với loại nghiên cứu đã chọn. Kết quả có thể chưa hoàn chỉnh và cần con người rà soát."}
                </p>
              </div>
              <span className="text-xs font-medium px-2.5 py-1 rounded-md bg-zinc-100 text-zinc-700 border border-zinc-200 hidden sm:inline-block">
                {task.citation_style} • {task.research_type}
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Deliverable 1: Academic Paper */}
              <div className="p-4 sm:p-5 rounded-xl bg-white border border-zinc-200 hover:border-zinc-300 transition-colors shadow-2xs space-y-2">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-lg bg-blue-50 text-blue-700 border border-blue-100 shrink-0">
                    <FileText size={18} />
                  </div>
                  <div>
                    <h4 className="font-bold text-sm text-zinc-900">
                      {isEn
                        ? "1. AI-Assisted Research Draft"
                        : "1. Bản thảo nghiên cứu có AI hỗ trợ"}
                    </h4>
                    <span className="text-[11px] text-zinc-600 font-medium">
                      {isEn
                        ? "Structured for the selected study type"
                        : "Bố cục theo loại nghiên cứu đã chọn"}
                    </span>
                  </div>
                </div>
                <p className="text-xs sm:text-[13px] text-zinc-600 leading-relaxed">
                  {isEn
                    ? "The draft may contain sections relevant to the selected method. It is not peer-reviewed or publication-ready; incomplete outputs remain marked for review."
                    : "Bản thảo có thể gồm các mục phù hợp với phương pháp đã chọn. Bài chưa qua phản biện học thuật hay sẵn sàng xuất bản; kết quả chưa hoàn chỉnh sẽ được đánh dấu cần rà soát."}
                </p>
              </div>

              {/* Deliverable 2: Multi-format Exports */}
              <div className="p-4 sm:p-5 rounded-xl bg-white border border-zinc-200 hover:border-zinc-300 transition-colors shadow-2xs space-y-2">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-100 shrink-0">
                    <Download size={18} />
                  </div>
                  <div>
                    <h4 className="font-bold text-sm text-zinc-900">
                      {isEn
                        ? "2. Downloadable Files"
                        : "2. Tệp có thể tải xuống"}
                    </h4>
                    <span className="text-[11px] text-zinc-600 font-medium">
                      {isEn
                        ? "Formats available for this run"
                        : "Định dạng khả dụng cho lượt chạy này"}
                    </span>
                  </div>
                </div>
                <p className="text-xs sm:text-[13px] text-zinc-600 leading-relaxed">
                  {isEn
                    ? "Download supported formats such as Word, Markdown, or research packages when available. Export formatting does not establish venue compliance or publication readiness."
                    : "Tải các định dạng được hỗ trợ như Word, Markdown hoặc gói nghiên cứu khi có. Định dạng tệp không chứng minh bài đã đúng yêu cầu hội thảo/tạp chí hay sẵn sàng xuất bản."}
                </p>
              </div>

              {/* Deliverable 3: Grounded Evidence & Citations */}
              <div className="p-4 sm:p-5 rounded-xl bg-white border border-zinc-200 hover:border-zinc-300 transition-colors shadow-2xs space-y-2">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-lg bg-purple-50 text-purple-700 border border-purple-100 shrink-0">
                    <Layers size={18} />
                  </div>
                  <div>
                    <h4 className="font-bold text-sm text-zinc-900">
                      {isEn
                        ? "3. Traceable Evidence & Citations"
                        : "3. Bằng chứng trích dẫn có thể truy vết"}
                    </h4>
                    <span className="text-[11px] text-zinc-600 font-medium">
                      {isEn
                        ? "Source links where evidence is available"
                        : "Liên kết nguồn khi có bằng chứng"}
                    </span>
                  </div>
                </div>
                <p className="text-xs sm:text-[13px] text-zinc-600 leading-relaxed">
                  {isEn
                    ? "Claims can be traced to stored sources and passages where available. A citation does not prove that a source entails the claim, that coverage is complete, or that the draft is error-free."
                    : "Có thể truy vết luận điểm về nguồn và đoạn trích đã lưu khi dữ liệu sẵn có. Việc có trích dẫn không chứng minh nguồn hỗ trợ đầy đủ luận điểm, phạm vi tài liệu đã đầy đủ hay bản thảo không còn lỗi."}
                </p>
              </div>

              {/* Deliverable 4: Protocol or Empirical Data */}
              <div className="p-4 sm:p-5 rounded-xl bg-white border border-zinc-200 hover:border-zinc-300 transition-colors shadow-2xs space-y-2">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-lg bg-amber-50 text-amber-700 border border-amber-100 shrink-0">
                    <Activity size={18} />
                  </div>
                  <div>
                    <h4 className="font-bold text-sm text-zinc-900">
                      {isEn
                        ? "4. Recorded Execution & Experiment Data"
                        : "4. Dữ liệu thực thi và thực nghiệm đã ghi nhận"}
                    </h4>
                    <span className="text-[11px] text-zinc-600 font-medium">
                      {isEn
                        ? "Progress and artifacts where recorded"
                        : "Tiến độ và hiện vật khi được ghi nhận"}
                    </span>
                  </div>
                </div>
                <p className="text-xs sm:text-[13px] text-zinc-600 leading-relaxed">
                  {isEn
                    ? "View recorded progress, usage, metrics, and artifacts where available. Reproducing a result depends on preserved inputs, code, configuration, and execution environment."
                    : "Xem tiến độ, mức sử dụng, chỉ số và hiện vật đã được ghi nhận khi có. Tái lập kết quả còn phụ thuộc vào việc lưu đủ dữ liệu đầu vào, mã, cấu hình và môi trường thực thi."}
                </p>
              </div>
            </div>
          </div>
        </details>
      )}
    </div>
  );
}
