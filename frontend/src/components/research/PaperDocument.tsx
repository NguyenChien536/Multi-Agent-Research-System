import {
  Check,
  ChevronDown,
  Copy,
  Download,
  FileDown,
  FileText,
  Loader2,
  Maximize2,
  Minimize2,
  Package,
  Printer,
} from "lucide-react";
import { Badge } from "@/components/ui/Components";
import { Button } from "@/components/ui/Button";
import { ManuscriptReadiness } from "@/components/research/ManuscriptReadiness";
import {
  PublicationArticle,
  PublicationExport,
} from "@/components/research/PublicationPaper";
import { withoutRepeatedTitle } from "@/lib/paperPresentation";
import type { ResearchReportResponse, ResearchTaskResponse } from "@/types";

interface PaperDocumentProps {
  task: ResearchTaskResponse;
  report: ResearchReportResponse;
  isEn: boolean;
  language: "en" | "vi";
  isCopied: boolean;
  isWidePaper: boolean;
  isDownloadMenuOpen: boolean;
  setIsDownloadMenuOpen: (
    value: boolean | ((previous: boolean) => boolean),
  ) => void;
  isExportingDocx: boolean;
  onCopyMarkdown: () => void;
  onToggleWidePaper: () => void;
  onDownloadDocx: () => Promise<void>;
  onDownloadMarkdown: () => void;
  onDownloadBundle: () => void;
  onCitationClick: (label: string) => void;
  statusLabel: (status: string, language: "en" | "vi") => string;
  formatDate: (value: string, language: "en" | "vi") => string;
}

export function PaperDocument({
  task,
  report,
  isEn,
  language,
  isCopied,
  isWidePaper,
  isDownloadMenuOpen,
  setIsDownloadMenuOpen,
  isExportingDocx,
  onCopyMarkdown,
  onToggleWidePaper,
  onDownloadDocx,
  onDownloadMarkdown,
  onDownloadBundle,
  onCitationClick,
  statusLabel,
  formatDate,
}: PaperDocumentProps) {
  return (
    <div className="space-y-6 print:space-y-0">
      <ManuscriptReadiness report={report} taskId={task.id} isEn={isEn} />
      {["FAILED", "CANCELLED"].includes(task.status) && (
        <div className="rounded-xl bg-amber-50 border border-amber-200 p-4 text-sm text-amber-800 flex items-center justify-between print:hidden">
          <span>
            {statusLabel(task.status, language)} —{" "}
            {["FAILED", "CANCELLED"].includes(task.status)
              ? isEn
                ? `Showing saved version ${report.version_number}; the latest operation did not replace it.`
                : `Đang hiển thị phiên bản ${report.version_number} đã lưu; thao tác vừa rồi không ghi đè bản này.`
              : isEn
                ? "Review evidence, validation findings and remaining limitations before use."
                : "Cần rà soát bằng chứng, kết quả kiểm tra và các hạn chế trước khi sử dụng."}
          </span>
          <Badge variant="outline">{statusLabel(task.status, language)}</Badge>
        </div>
      )}

      {/* Scientific Journal 2-Column Presentation */}
      <div className="paper-layout-container printable-paper-container">
        {/* Main Scientific Paper Document */}
        <article className="printable-article w-full min-w-0 bg-white rounded-2xl border border-zinc-200/90 shadow-sm overflow-hidden print:border-none print:shadow-none print:p-0 print:m-0 print:rounded-none">
          {/* Journal Cover / Top Masthead */}
          <div className="border-b border-zinc-200 bg-gradient-to-b from-zinc-50/80 to-white px-6 sm:px-10 md:px-12 pt-8 pb-7 print:px-0 print:pt-0 print:bg-none print:border-b-2 print:border-zinc-800">
            {/* Academic Meta Topline */}
            <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-zinc-500 font-mono border-b border-zinc-100 pb-3 mb-5 print:border-zinc-300">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded bg-zinc-900 text-white font-bold tracking-wider text-[10px] uppercase font-sans print:border print:border-zinc-800">
                  Synthia Research Draft
                </span>
                <span className="text-zinc-300">|</span>
                <span className="font-semibold text-zinc-700 tracking-wide">
                  {task.research_type === "EMPIRICAL_COMPUTATIONAL"
                    ? "COMPUTATIONAL INVESTIGATION REPORT"
                    : task.research_type === "EMPIRICAL_HUMAN"
                      ? "EMPIRICAL FIELD STUDY & PROTOCOL"
                      : "LITERATURE REVIEW & SYNTHESIS"}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <span>
                  {isEn ? "Draft version" : "Phiên bản bản thảo"}{" "}
                  {report.version_number}
                </span>
                <span>•</span>
                <span>{formatDate(report.created_at, language)}</span>
              </div>
            </div>

            {/* Paper Title */}
            <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold text-zinc-900 tracking-tight leading-tight">
              {report.title}
            </h1>

            {/* Authors & Laboratory Metadata */}
            <div className="mt-5 pt-4 border-t border-zinc-100 flex flex-wrap items-center justify-between gap-4 text-xs print:border-zinc-300">
              <div>
                <div className="font-semibold text-zinc-800 text-sm">
                  {isEn
                    ? "AI-assisted research draft"
                    : "Bản thảo nghiên cứu có AI hỗ trợ"}
                </div>
                <div className="text-zinc-500 mt-0.5">
                  {isEn
                    ? "Verify claims and references before academic use."
                    : "Cần kiểm chứng luận điểm và nguồn trước khi sử dụng học thuật."}
                </div>
                <div className="text-zinc-400 mt-0.5 text-[11px] print:hidden">
                  {isEn
                    ? "Not a published or peer-reviewed article."
                    : "Chưa phải bài báo đã xuất bản hoặc qua phản biện học thuật."}
                </div>
              </div>

              {/* Quick Actions */}
              <div className="flex flex-wrap items-center gap-2 print:hidden">
                <Button
                  variant="outline"
                  onClick={() => window.print()}
                  title={
                    isEn
                      ? "Print full paper or Save as PDF"
                      : "In toàn bộ bài báo hoặc Lưu thành PDF"
                  }
                  className="h-8 px-2.5 text-xs hover:bg-zinc-100 cursor-pointer"
                >
                  <Printer size={13} className="mr-1.5" />{" "}
                  {isEn ? "Print / PDF" : "In / PDF"}
                </Button>
                <Button
                  variant="outline"
                  onClick={onCopyMarkdown}
                  title={
                    isEn
                      ? "Copy full Markdown content"
                      : "Sao chép toàn bộ nội dung Markdown"
                  }
                  className="h-8 px-2.5 text-xs hover:bg-zinc-100 cursor-pointer"
                >
                  {isCopied ? (
                    <Check size={13} className="text-emerald-600 mr-1.5" />
                  ) : (
                    <Copy size={13} className="mr-1.5" />
                  )}
                  {isCopied
                    ? isEn
                      ? "Copied"
                      : "Đã chép"
                    : isEn
                      ? "Copy"
                      : "Sao chép"}
                </Button>
                <Button
                  variant={isWidePaper ? "primary" : "outline"}
                  onClick={onToggleWidePaper}
                  title={
                    isWidePaper
                      ? isEn
                        ? "Exit full width reading (show sidebars)"
                        : "Thu gọn về kích thước chuẩn (hiện thanh bên)"
                      : isEn
                        ? "Full width reading mode (hide sidebars)"
                        : "Phóng to toàn màn hình (ẩn thanh bên)"
                  }
                  className={`h-8 px-2.5 text-xs font-semibold cursor-pointer ${isWidePaper ? "bg-zinc-900 text-white" : "hover:bg-zinc-100"}`}
                >
                  {isWidePaper ? (
                    <Minimize2 size={13} className="mr-1.5" />
                  ) : (
                    <Maximize2 size={13} className="mr-1.5" />
                  )}
                  {isWidePaper
                    ? isEn
                      ? "Standard"
                      : "Thu gọn"
                    : isEn
                      ? "Full Width"
                      : "Phóng to"}
                </Button>

                {/* Download Formats Dropdown */}
                <div className="relative">
                  <Button
                    variant="primary"
                    onClick={() => setIsDownloadMenuOpen((prev) => !prev)}
                    disabled={isExportingDocx}
                    title={
                      isEn
                        ? "Select download format (Word, Markdown, JSON)"
                        : "Chọn định dạng tải bài báo (Word, Markdown, JSON)"
                    }
                    className="h-8 px-3 text-xs bg-zinc-900 hover:bg-zinc-800 text-white cursor-pointer shadow-xs flex items-center"
                  >
                    {isExportingDocx ? (
                      <Loader2 size={13} className="mr-1.5 animate-spin" />
                    ) : (
                      <Download size={13} className="mr-1.5" />
                    )}
                    <span>
                      {isExportingDocx
                        ? isEn
                          ? "Exporting Word..."
                          : "Đang tạo Word..."
                        : isEn
                          ? "Download"
                          : "Tải về"}
                    </span>
                    <ChevronDown
                      size={13}
                      className={`ml-1.5 transition-transform duration-150 ${isDownloadMenuOpen ? "rotate-180" : ""}`}
                    />
                  </Button>

                  {isDownloadMenuOpen && (
                    <>
                      <div
                        className="fixed inset-0 z-40"
                        onClick={() => setIsDownloadMenuOpen(false)}
                      />
                      <div className="absolute right-0 mt-1.5 w-72 rounded-xl bg-white border border-zinc-200 shadow-xl py-1.5 z-50 text-left">
                        <div className="px-3 py-1.5 text-[10.5px] font-semibold text-zinc-400 uppercase tracking-wider border-b border-zinc-100">
                          {isEn
                            ? "Select download format"
                            : "Chọn định dạng tải xuống"}
                        </div>

                        {/* Word (.docx) */}
                        <button
                          type="button"
                          onClick={async () => {
                            setIsDownloadMenuOpen(false);
                            await onDownloadDocx();
                          }}
                          className="w-full px-3 py-2.5 text-left hover:bg-zinc-100 flex items-start gap-3 transition-colors cursor-pointer group"
                        >
                          <div className="p-1.5 rounded-lg bg-zinc-100 text-zinc-700 group-hover:bg-zinc-200 shrink-0 mt-0.5">
                            <FileDown size={16} />
                          </div>
                          <div>
                            <div className="font-semibold text-xs text-zinc-900 group-hover:text-blue-900 flex items-center gap-1.5">
                              Microsoft Word (.docx)
                              <span className="text-xs px-1.5 py-0.5 rounded bg-zinc-100 text-zinc-700 font-medium border border-zinc-200">
                                {isEn ? "Recommended" : "Khuyên dùng"}
                              </span>
                            </div>
                            <div className="text-[11px] text-zinc-500 mt-0.5 leading-snug">
                              {isEn
                                ? "Standard formatted Word document with tables, outline, and references"
                                : "Văn bản Word chuẩn báo cáo khoa học với bảng, danh mục và tài liệu tham khảo"}
                            </div>
                          </div>
                        </button>

                        {/* Markdown (.md) */}
                        <button
                          type="button"
                          onClick={() => {
                            setIsDownloadMenuOpen(false);
                            onDownloadMarkdown();
                          }}
                          className="w-full px-3 py-2.5 text-left hover:bg-zinc-100 flex items-start gap-3 transition-colors cursor-pointer group"
                        >
                          <div className="p-1.5 rounded-lg bg-zinc-100 text-zinc-700 group-hover:bg-zinc-200 shrink-0 mt-0.5">
                            <FileText size={16} />
                          </div>
                          <div>
                            <div className="font-semibold text-xs text-zinc-900 group-hover:text-emerald-900">
                              Markdown (.md)
                            </div>
                            <div className="text-[11px] text-zinc-500 mt-0.5 leading-snug">
                              {isEn
                                ? "Standard Markdown text source file"
                                : "Tệp văn bản nguồn định dạng Markdown tiêu chuẩn"}
                            </div>
                          </div>
                        </button>

                        <div className="border-t border-zinc-100 my-1"></div>

                        {/* JSON Data Bundle */}
                        <button
                          type="button"
                          onClick={() => {
                            setIsDownloadMenuOpen(false);
                            onDownloadBundle();
                          }}
                          className="w-full px-3 py-2.5 text-left hover:bg-zinc-100 flex items-start gap-3 transition-colors cursor-pointer group"
                        >
                          <div className="p-1.5 rounded-lg bg-zinc-100 text-zinc-700 group-hover:bg-zinc-200 shrink-0 mt-0.5">
                            <Package size={16} />
                          </div>
                          <div>
                            <div className="font-semibold text-xs text-zinc-900 group-hover:text-amber-900">
                              {isEn
                                ? "Research data bundle (.json)"
                                : "Gói dữ liệu nghiên cứu (.json)"}
                            </div>
                            <div className="text-[11px] text-zinc-500 mt-0.5 leading-snug">
                              {isEn
                                ? "Includes full paper, retrieved sources, and verified citations"
                                : "Bao gồm bài báo, nguồn tài liệu và trích dẫn bằng chứng"}
                            </div>
                          </div>
                        </button>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>

          <PublicationExport
            taskId={task.id}
            version={report.version_number}
            isEn={isEn}
          />
          {/* Scientific Article Body rendered by MarkdownViewer with academicStyle */}
          <div className="px-6 sm:px-10 md:px-12 py-8">
            <PublicationArticle
              metadata={report.review_metadata}
              content={withoutRepeatedTitle(
                report.content_markdown,
                report.title,
              )}
              academicStyle={true}
              onCitationClick={(label) => {
                onCitationClick(label);
              }}
            />
          </div>

          {/* Publication Footer */}
          <div className="border-t border-stone-200/60 bg-white px-6 sm:px-10 py-5 text-xs text-zinc-500 flex flex-wrap items-center justify-between gap-4 print:bg-white print:px-0">
            <div>
              <div className="font-medium text-zinc-700">
                Synthia Multi-Agent Research Platform
              </div>
              <div>
                {isEn
                  ? "AI-assisted draft linked to source passages; claims still require scientific review."
                  : "Bản thảo có AI hỗ trợ, gắn với trích đoạn nguồn; luận điểm vẫn cần kiểm chứng khoa học."}
              </div>
            </div>
            <div className="font-mono text-[11px] text-zinc-400">
              ID: {task.id} · v{report.version_number}
            </div>
          </div>
        </article>

        {/* Right Sidebar: Table of Contents & Article Metadata */}
      </div>
    </div>
  );
}
