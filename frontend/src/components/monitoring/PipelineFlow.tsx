'use client';

import React from 'react';
import Link from 'next/link';
import {
  CheckCircle2, Circle, Clock, Loader2, XCircle, ChevronRight,
  ArrowUpRight
} from 'lucide-react';

export interface PipelineStageItem {
  key: string;
  name: string;
  name_en?: string;
  agent: string;
  description: string;
  description_en?: string;
}

export interface PipelineFlowProps {
  stages: PipelineStageItem[];
  currentStep?: string | null;
  activeStageKey: string;
  status: string;
  activities?: Array<{ agent?: string; status?: string }>;
  isEn: boolean;
  t: (key: any) => string;
  researchId?: string;
  researchType?: string;
}

function getStageDestination(
  stageKey: string,
  researchId: string | undefined,
  status: string,
  researchType?: string
) {
  const base = researchId ? `/research/${researchId}` : '/dashboard';

  // Specific attention states (waiting for user action)
  if (status === 'WAITING_USER_DATA' && (stageKey === 'METHODOLOGIST' || stageKey === 'EXPERIMENT_RUNNER')) {
    if (researchType === 'EMPIRICAL_COMPUTATIONAL') {
      return {
        href: `${base}?tab=experiments#upload-dataset`,
        labelEn: 'Awaiting CSV dataset — Click to upload dataset',
        labelVi: 'Đang chờ nạp dữ liệu — Bấm để nạp tập dữ liệu CSV',
        actionTextEn: 'Upload dataset →',
        actionTextVi: 'Nạp dữ liệu CSV →',
        isAwaiting: true,
      };
    }
    return {
      href: `${base}#fieldwork-section`,
      labelEn: 'Awaiting fieldwork data — Click to submit fieldwork results',
      labelVi: 'Đang chờ kết quả — Bấm để nạp dữ liệu thực địa',
      actionTextEn: 'Submit fieldwork data →',
      actionTextVi: 'Nạp dữ liệu thực địa →',
      isAwaiting: true,
    };
  }

  if (status === 'WAITING_APPROVAL' && stageKey === 'SUPERVISOR') {
    return {
      href: `${base}#plan-review-section`,
      labelEn: 'Awaiting plan approval — Click to review & approve plan',
      labelVi: 'Đang chờ duyệt — Bấm để xem & duyệt kế hoạch',
      actionTextEn: 'Review & approve plan →',
      actionTextVi: 'Duyệt kế hoạch →',
      isAwaiting: true,
    };
  }

  switch (stageKey) {
    case 'SUPERVISOR':
      return {
        href: `${base}?tab=protocol`,
        labelEn: 'Click to view research plan & protocol',
        labelVi: 'Bấm để xem kế hoạch & đề cương nghiên cứu',
        actionTextEn: 'View plan →',
        actionTextVi: 'Xem kế hoạch →',
        isAwaiting: false,
      };
    case 'RESEARCHER':
      return {
        href: `${base}?tab=sources`,
        labelEn: 'Click to view literature & search sources',
        labelVi: 'Bấm để xem tài liệu & nguồn tìm kiếm',
        actionTextEn: 'View sources →',
        actionTextVi: 'Nguồn tài liệu →',
        isAwaiting: false,
      };
    case 'CURATOR':
      return {
        href: `${base}?tab=sources`,
        labelEn: 'Click to view indexed documents & chunks',
        labelVi: 'Bấm để xem tài liệu đã xử lý',
        actionTextEn: 'Indexed chunks →',
        actionTextVi: 'Xử lý tài liệu →',
        isAwaiting: false,
      };
    case 'ANALYST':
      return {
        href: `${base}?tab=citations`,
        labelEn: 'Click to view evidence claims & matrix',
        labelVi: 'Bấm để xem phân tích bằng chứng khoa học',
        actionTextEn: 'Evidence matrix →',
        actionTextVi: 'Bằng chứng đối chiếu →',
        isAwaiting: false,
      };
    case 'METHODOLOGIST':
      return {
        href: researchType === 'EMPIRICAL_COMPUTATIONAL' ? `${base}?tab=experiments` : `${base}#fieldwork-section`,
        labelEn: 'Click to view methodology & field data',
        labelVi: 'Bấm để xem phương pháp & dữ liệu thực địa',
        actionTextEn: 'Method & data →',
        actionTextVi: 'Phương pháp & dữ liệu →',
        isAwaiting: false,
      };
    case 'EXPERIMENT_RUNNER':
      return {
        href: `${base}?tab=experiments`,
        labelEn: 'Click to view computational experiments',
        labelVi: 'Bấm để xem thực nghiệm tính toán',
        actionTextEn: 'Experiments →',
        actionTextVi: 'Thực nghiệm →',
        isAwaiting: false,
      };
    case 'WRITER':
      return {
        href: base,
        labelEn: 'Click to view research paper manuscript',
        labelVi: 'Bấm để đọc bản thảo bài báo khoa học',
        actionTextEn: 'Read manuscript →',
        actionTextVi: 'Đọc bài báo →',
        isAwaiting: false,
      };
    case 'CRITIC':
      return {
        href: researchId ? `/research/${researchId}/revisions` : base,
        labelEn: 'Click to view peer critique & editorial revisions',
        labelVi: 'Bấm để xem phản biện & góp ý sửa bài',
        actionTextEn: 'Critique & revisions →',
        actionTextVi: 'Phản biện & Sửa →',
        isAwaiting: false,
      };
    case 'POST_PROCESSOR':
      return {
        href: `${base}?tab=citations`,
        labelEn: 'Click to inspect citations & publication export',
        labelVi: 'Bấm để kiểm tra trích dẫn & xuất bản',
        actionTextEn: 'Citations & export →',
        actionTextVi: 'Trích dẫn & Xuất file →',
        isAwaiting: false,
      };
    default:
      return {
        href: base,
        labelEn: 'Click to open research workspace',
        labelVi: 'Bấm để mở workspace làm việc',
        actionTextEn: 'Open workspace →',
        actionTextVi: 'Mở workspace →',
        isAwaiting: false,
      };
  }
}

export function PipelineFlow({
  stages,
  currentStep,
  activeStageKey,
  status,
  activities = [],
  isEn,
  t,
  researchId,
  researchType,
}: PipelineFlowProps) {
  const isWorkflowCompleted = status === 'COMPLETED' || status === 'SUCCESS';
  const isFailed = status === 'FAILED';
  const isCancelled = status === 'CANCELLED';
  const isAwaitingApproval = status === 'WAITING_APPROVAL';
  const isAwaitingData = status === 'WAITING_USER_DATA';

  // Find index of currently active stage
  const activeIdx = stages.findIndex(s => s.key === activeStageKey);

  // Set of agents that have completed in activities
  const executedAgents = new Set(
    activities
      .filter(a => a.status === 'SUCCESS' || a.status === 'COMPLETED')
      .map(a => a.agent?.toLowerCase())
  );

  const getStageState = (stage: PipelineStageItem, idx: number): 'done' | 'active' | 'paused' | 'failed' | 'cancelled' | 'pending' => {
    if (isWorkflowCompleted) return 'done';
    if (isCancelled && idx === activeIdx) return 'cancelled';
    if (isFailed && idx === activeIdx) return 'failed';

    if (stage.key === activeStageKey) {
      if (isAwaitingApproval || isAwaitingData) return 'paused';
      return 'active';
    }

    if (activeIdx !== -1) {
      if (idx < activeIdx) return 'done';
      return 'pending';
    }

    // If activeIdx is -1 (e.g. QUEUED or terminal without active step)
    if (executedAgents.has(stage.agent.toLowerCase())) return 'done';
    return 'pending';
  };

  return (
    <div className="w-full space-y-3">
      {/* Header bar without technical DAG jargon */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-zinc-900" />
          <h3 className="text-xs sm:text-sm font-bold uppercase tracking-wider text-zinc-900">
            {t('mon_pipeline_title')} ({stages.length})
          </h3>
        </div>

        <div className="flex items-center gap-2 text-xs sm:text-sm">
          <span className="text-zinc-500 font-medium">{t('mon_current_step')}:</span>
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full font-bold text-xs bg-zinc-900 text-white shadow-xs">
            {activeIdx !== -1 && (
              <span className="w-2 h-2 rounded-full bg-blue-400 animate-ping shrink-0" />
            )}
            <span>
              {activeIdx !== -1
                ? (isEn ? (stages[activeIdx].name_en || stages[activeIdx].name) : stages[activeIdx].name)
                : isWorkflowCompleted
                ? (isEn ? 'All stages completed' : 'Đã hoàn tất toàn bộ chặng')
                : (isEn ? 'Pending start' : 'Chưa bắt đầu')}
            </span>
          </span>
        </div>
      </div>

      {/* GitHub Actions Connected Pipeline Flow Track */}
      <div className="relative rounded-2xl border border-zinc-200 bg-white p-5 sm:p-6 shadow-xs overflow-hidden">
        {/* Subtle grid background for academic/pipeline visual */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#f4f4f5_1px,transparent_1px),linear-gradient(to_bottom,#f4f4f5_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] opacity-60 pointer-events-none" />

        <div className="relative z-10 flex items-center overflow-x-auto py-2.5 px-1 scrollbar-thin scrollbar-thumb-zinc-300">
          {stages.map((stage, idx) => {
            const state = getStageState(stage, idx);
            const isLast = idx === stages.length - 1;
            const nextState = !isLast ? getStageState(stages[idx + 1], idx + 1) : null;
            const dest = getStageDestination(stage.key, researchId, status, researchType);
            const stageTitle = isEn ? (stage.name_en || stage.name) : stage.name;

            return (
              <React.Fragment key={stage.key}>
                {/* Stage Node Box - Clickable with direct navigation to corresponding workspace */}
                <Link
                  href={dest.href}
                  title={isEn ? dest.labelEn : dest.labelVi}
                  className={`group relative flex flex-col justify-between p-4 rounded-xl border transition-all duration-200 shrink-0 min-w-[190px] sm:min-w-[210px] max-w-[235px] select-none cursor-pointer hover:shadow-md hover:-translate-y-0.5 focus:outline-none focus:ring-2 focus:ring-zinc-900 ${
                    state === 'active'
                      ? 'border-blue-500 bg-blue-50/20 ring-4 ring-blue-500/15 shadow-[0_4px_20px_rgba(59,130,246,0.2)] -translate-y-0.5'
                      : state === 'paused'
                      ? 'border-amber-400 bg-amber-50/70 ring-4 ring-amber-500/20 shadow-[0_4px_16px_rgba(245,158,11,0.2)] -translate-y-0.5 hover:border-amber-500'
                      : state === 'failed'
                      ? 'border-red-400 bg-red-50/50 ring-2 ring-red-400/20'
                      : state === 'done'
                      ? 'border-emerald-300 bg-white shadow-2xs hover:border-emerald-500 hover:shadow-xs'
                      : 'border-zinc-200 bg-zinc-50/70 text-zinc-600 hover:border-zinc-300 hover:bg-white shadow-2xs'
                  }`}
                >
                  {/* Top status indicator row */}
                  <div className="flex items-center justify-between gap-2 mb-2.5">
                    <span className={`font-mono text-xs font-bold px-2 py-0.5 rounded-md ${
                      state === 'active'
                        ? 'bg-blue-100 text-blue-800'
                        : state === 'done'
                        ? 'bg-emerald-100 text-emerald-800'
                        : state === 'paused'
                        ? 'bg-amber-100 text-amber-900'
                        : state === 'failed'
                        ? 'bg-red-100 text-red-800'
                        : 'bg-zinc-100 text-zinc-600 group-hover:text-zinc-800'
                    }`}>
                      #{idx + 1}
                    </span>

                    {/* Status Badge */}
                    <div className="shrink-0">
                      {state === 'active' && (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-50 text-blue-700 border border-blue-200 animate-pulse">
                          <Loader2 size={12} className="animate-spin text-blue-600" />
                          <span>{isEn ? 'Running' : 'Đang xử lý'}</span>
                        </span>
                      )}
                      {state === 'done' && (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-300">
                          <CheckCircle2 size={13} className="text-emerald-600" />
                          <span>{isEn ? 'Done' : 'Xong'}</span>
                        </span>
                      )}
                      {state === 'paused' && (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-900 border border-amber-300 animate-pulse">
                          <Clock size={12} className="text-amber-700" />
                          <span>{isEn ? 'Awaiting' : 'Chờ duyệt'}</span>
                        </span>
                      )}
                      {state === 'failed' && (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-red-50 text-red-700 border border-red-200">
                          <XCircle size={12} className="text-red-600" />
                          <span>{isEn ? 'Failed' : 'Lỗi'}</span>
                        </span>
                      )}
                      {state === 'pending' && (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-xs font-medium text-zinc-400">
                          <Circle size={13} className="text-zinc-300" />
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Stage title & agent */}
                  <div className="space-y-1">
                    <h4 className={`font-bold text-sm sm:text-[15px] tracking-tight line-clamp-1 leading-snug ${
                      state === 'active'
                        ? 'text-blue-950 font-bold'
                        : state === 'paused'
                        ? 'text-amber-950 font-bold'
                        : state === 'done'
                        ? 'text-zinc-900 font-bold'
                        : 'text-zinc-800 font-semibold'
                    }`}>
                      {stageTitle}
                    </h4>

                    {/* Agent badge */}
                    <div className="flex items-center gap-1.5 text-xs text-zinc-600 font-medium">
                      <span className="inline-block w-1.5 h-1.5 rounded-full bg-zinc-300 group-hover:bg-zinc-400" />
                      <span className="truncate">{stage.agent}</span>
                    </div>
                  </div>

                  {/* Bottom Action Hint & Destination Jump */}
                  {dest.isAwaiting ? (
                    <div className="mt-3 pt-2 border-t border-amber-200/80 flex items-center justify-between text-xs font-bold text-amber-950 bg-amber-100/70 -mx-1 px-2.5 py-1.5 rounded-lg">
                      <span className="truncate">{isEn ? dest.actionTextEn : dest.actionTextVi}</span>
                      <ArrowUpRight size={14} className="shrink-0 ml-1 text-amber-900" />
                    </div>
                  ) : (
                    <div className="mt-3 pt-2.5 border-t border-zinc-100 flex items-center justify-between text-xs font-semibold text-zinc-700 group-hover:text-zinc-950 transition-colors">
                      <span className="truncate">{isEn ? dest.actionTextEn : dest.actionTextVi}</span>
                      <ArrowUpRight size={13} className="text-zinc-400 group-hover:text-zinc-950 transition-colors shrink-0 ml-1" />
                    </div>
                  )}

                  {/* Active bottom bar */}
                  {state === 'active' && (
                    <div className="absolute inset-x-0 bottom-0 h-1 bg-gradient-to-r from-blue-500 via-indigo-500 to-blue-600 rounded-b-xl" />
                  )}
                  {state === 'paused' && (
                    <div className="absolute inset-x-0 bottom-0 h-1 bg-gradient-to-r from-amber-400 via-amber-500 to-amber-600 rounded-b-xl" />
                  )}
                  {state === 'done' && (
                    <div className="absolute inset-x-0 bottom-0 h-0.5 bg-emerald-500 rounded-b-xl opacity-90" />
                  )}
                </Link>

                {/* Connector between nodes (GitHub Actions line with directional arrow) */}
                {!isLast && (
                  <div className="flex items-center shrink-0 w-8 sm:w-10 px-1 relative">
                    {/* Connector line */}
                    <div
                      className={`h-[2.5px] w-full transition-colors duration-300 ${
                        state === 'done' && (nextState === 'done' || nextState === 'active')
                          ? 'bg-gradient-to-r from-emerald-500 to-blue-500'
                          : state === 'done'
                          ? 'bg-emerald-500'
                          : state === 'active'
                          ? 'bg-gradient-to-r from-blue-500 to-zinc-300 animate-pulse'
                          : 'border-t-2 border-dashed border-zinc-200'
                      }`}
                    />
                    {/* Flow arrow head */}
                    <ChevronRight
                      size={14}
                      className={`absolute right-0 top-1/2 -translate-y-1/2 -mr-1 transition-colors ${
                        state === 'done' && nextState === 'active'
                          ? 'text-blue-500'
                          : state === 'done'
                          ? 'text-emerald-500'
                          : 'text-zinc-300'
                      }`}
                    />
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </div>
  );
}
