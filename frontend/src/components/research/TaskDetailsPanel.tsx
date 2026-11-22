import { useState } from "react";
import Link from "next/link";
import { FlaskConical, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Components";
import { ModelConnectionSummary } from "@/components/ModelConnectionSummary";
import type { ResearchTaskResponse } from "@/types";

interface TaskDetailsPanelProps {
  task: ResearchTaskResponse;
  isEn: boolean;
  language: "en" | "vi";
  isDeleting: boolean;
  onDeleteTask: () => Promise<void>;
  formatDate: (value: string, language: "en" | "vi") => string;
}

export function TaskDetailsPanel({
  task,
  isEn,
  language,
  isDeleting,
  onDeleteTask,
  formatDate,
}: TaskDetailsPanelProps) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  return (
    <div className="w-full max-w-7xl mx-auto space-y-6">
      <Card className="p-6 space-y-5">
        <h2 className="text-lg font-bold text-zinc-900 border-b border-zinc-200 pb-3">
          {isEn
            ? "Task Configuration & Metadata"
            : "Cấu hình & Chi tiết nhiệm vụ"}
        </h2>
        <ModelConnectionSummary key={task.id} task={task} isEn={isEn} />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          <div>
            <span className="font-semibold text-zinc-700">
              {isEn ? "Research Question:" : "Câu hỏi nghiên cứu:"}
            </span>
            <p className="text-zinc-900 mt-1 leading-relaxed bg-zinc-50 p-3 rounded-xl border border-zinc-200">
              {task.research_question}
            </p>
          </div>

          <div>
            <span className="font-semibold text-zinc-700">
              {isEn ? "Additional Description:" : "Mô tả bổ sung:"}
            </span>
            <p className="text-zinc-600 mt-1 leading-relaxed bg-zinc-50 p-3 rounded-xl border border-zinc-200">
              {task.description ||
                (isEn
                  ? "No additional description provided"
                  : "Không có mô tả bổ sung")}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm border-t border-zinc-100 pt-4">
          <div>
            <span className="text-xs text-zinc-500">
              {isEn ? "Research Type" : "Loại nghiên cứu"}
            </span>
            <div className="font-semibold text-zinc-800 mt-0.5">
              {task.research_type === "EMPIRICAL_HUMAN"
                ? isEn
                  ? "Fieldwork"
                  : "Thực địa"
                : task.research_type === "EMPIRICAL_COMPUTATIONAL"
                  ? isEn
                    ? "Computational"
                    : "Tính toán"
                  : isEn
                    ? "Literature Review"
                    : "Tổng quan"}
            </div>
          </div>
          <div>
            <span className="text-xs text-zinc-500">
              {isEn ? "Research Depth" : "Độ sâu nghiên cứu"}
            </span>
            <div className="font-semibold text-zinc-800 mt-0.5">
              {task.research_depth}
            </div>
          </div>
          <div>
            <span className="text-xs text-zinc-500">
              {isEn ? "Report Length" : "Độ dài báo cáo"}
            </span>
            <div className="font-semibold text-zinc-800 mt-0.5">
              {task.report_length}
            </div>
          </div>
          <div>
            <span className="text-xs text-zinc-500">
              {isEn ? "Citation Style" : "Kiểu trích dẫn"}
            </span>
            <div className="font-semibold text-zinc-800 mt-0.5">
              {task.citation_style}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm border-t border-zinc-100 pt-4">
          <div>
            <span className="text-xs text-zinc-500">
              {isEn ? "Plan Approval (HITL)" : "Duyệt kế hoạch (HITL)"}
            </span>
            <div className="font-semibold text-zinc-800 mt-0.5">
              {task.require_plan_approval
                ? isEn
                  ? "Enabled"
                  : "Bật"
                : isEn
                  ? "Disabled"
                  : "Tắt"}
            </div>
          </div>
          <div>
            <span className="text-xs text-zinc-500">
              {isEn ? "Max Iterations" : "Vòng lặp tối đa"}
            </span>
            <div className="font-semibold text-zinc-800 mt-0.5">
              {task.max_iterations}
            </div>
          </div>
          <div>
            <span className="text-xs text-zinc-500">
              {isEn ? "Max Sources" : "Nguồn tối đa"}
            </span>
            <div className="font-semibold text-zinc-800 mt-0.5">
              {task.max_sources}
            </div>
          </div>
          <div>
            <span className="text-xs text-zinc-500">
              {isEn ? "Attempt Number" : "Lần chạy thử lại"}
            </span>
            <div className="font-semibold text-zinc-800 mt-0.5">
              {task.attempt_number}
            </div>
          </div>
        </div>

        {task.user_data_submission && (
          <div className="border-t border-zinc-100 pt-4">
            <h3 className="font-semibold text-zinc-900 text-sm mb-2 flex items-center gap-1.5">
              <FlaskConical size={14} className="text-indigo-600" />
              {isEn
                ? "Submitted Empirical / Fieldwork Data"
                : "Dữ liệu thực nghiệm đã cung cấp"}
            </h3>
            <div className="bg-zinc-50 p-4 rounded-xl border border-zinc-200 text-xs space-y-2">
              {task.user_data_submission.sample_size != null && (
                <div className="flex justify-between">
                  <span className="text-zinc-500">
                    {isEn ? "Actual Sample Size:" : "Cỡ mẫu thực tế:"}
                  </span>
                  <span className="font-semibold text-zinc-800">
                    {task.user_data_submission.sample_size}
                  </span>
                </div>
              )}
              {task.user_data_submission.data_provenance && (
                <div className="flex justify-between">
                  <span className="text-zinc-500">
                    {isEn ? "Data Provenance:" : "Xuất xứ / Nguồn:"}
                  </span>
                  <span className="font-semibold text-zinc-800">
                    {task.user_data_submission.data_provenance}
                  </span>
                </div>
              )}
              {task.user_data_submission.method_notes && (
                <div>
                  <span className="text-zinc-500 font-medium">
                    {isEn ? "Methodology & Tools:" : "Phương pháp & công cụ:"}
                  </span>
                  <p className="text-zinc-700 mt-0.5">
                    {task.user_data_submission.method_notes}
                  </p>
                </div>
              )}
              <div>
                <span className="text-zinc-500 font-medium">
                  {isEn ? "Findings Summary:" : "Tóm tắt kết quả:"}
                </span>
                <p className="text-zinc-800 font-medium mt-0.5 whitespace-pre-wrap">
                  {task.user_data_submission.results_summary}
                </p>
              </div>
            </div>
          </div>
        )}

        <div className="border-t border-zinc-100 pt-4 flex flex-wrap items-center justify-between text-xs text-zinc-500 gap-2">
          <span>
            {isEn ? "Created: " : "Tạo lúc: "}
            {formatDate(task.created_at, language)}
          </span>
          {task.completed_at && (
            <span>
              {isEn ? "Completed: " : "Hoàn thành lúc: "}
              {formatDate(task.completed_at, language)}
            </span>
          )}
          <Link className="underline hover:text-zinc-900" href="/dashboard">
            {isEn ? "Back to Dashboard" : "Quay lại danh sách bài"}
          </Link>
        </div>
      </Card>

      {/* Danger Zone */}
      <div className="rounded-2xl border border-red-200 bg-red-50/50 p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h3 className="font-semibold text-red-900">
            {isEn ? "Danger Zone" : "Vùng nguy hiểm"}
          </h3>
          <p className="text-xs text-red-700 mt-0.5">
            {isEn
              ? "Permanently delete this research project and all associated sources, citations, and artifacts."
              : "Xóa vĩnh viễn bài nghiên cứu này cùng toàn bộ nguồn và trích dẫn liên quan."}
          </p>
        </div>
        {confirmDelete ? (
          <div className="flex items-center gap-2">
            <Button
              variant="danger"
              onClick={() => void onDeleteTask()}
              isLoading={isDeleting}
            >
              <Trash2 size={15} className="mr-1.5" />{" "}
              {isEn ? "Confirm Delete" : "Xác nhận xóa vĩnh viễn"}
            </Button>
            <Button
              variant="outline"
              onClick={() => setConfirmDelete(false)}
            >
              {isEn ? "Cancel" : "Hủy"}
            </Button>
          </div>
        ) : (
          <Button
            variant="danger"
            onClick={() => setConfirmDelete(true)}
            isLoading={isDeleting}
          >
            <Trash2 size={15} className="mr-1.5" />{" "}
            {isEn ? "Delete Research Project" : "Xóa bài nghiên cứu"}
          </Button>
        )}
      </div>
    </div>
  );
}
