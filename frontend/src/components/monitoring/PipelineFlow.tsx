'use client';

import React from 'react';
import {
  CheckCircle2, Circle, Clock, Loader2, XCircle, Info, ChevronRight,
  Sparkles, AlertCircle
} from 'lucide-react';
import type { StageDisplayState } from '@/lib/monitoring';

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
}

export function PipelineFlow({
  stages,
  currentStep,
  activeStageKey,
  status,
  activities = [],
  isEn,
  t,
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
      {/* Header bar */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-zinc-900" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-800">
            {t('mon_pipeline_title')} ({stages.length})
          </h3>
          <span className="text-[11px] text-zinc-500 font-mono">
            DAG Workflow
          </span>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <span className="text-zinc-500">{t('mon_current_step')}:</span>
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full font-semibold text-xs bg-zinc-900 text-white shadow-2xs">
            {activeIdx !== -1 && (
              <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-ping shrink-0" />
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
      <div className="relative rounded-2xl border border-zinc-200/90 bg-white p-4 sm:p-5 shadow-xs overflow-hidden">
        {/* Subtle grid background for academic/pipeline visual */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#f4f4f5_1px,transparent_1px),linear-gradient(to_bottom,#f4f4f5_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] opacity-60 pointer-events-none" />

        <div className="relative z-10 flex items-center overflow-x-auto py-3 px-1 scrollbar-thin scrollbar-thumb-zinc-300">
          {stages.map((stage, idx) => {
            const state = getStageState(stage, idx);
            const isLast = idx === stages.length - 1;
            const nextState = !isLast ? getStageState(stages[idx + 1], idx + 1) : null;

            return (
              <React.Fragment key={stage.key}>
                {/* Stage Node Box */}
                <div
                  className={`group relative flex flex-col justify-between p-3.5 rounded-xl border transition-all duration-200 shrink-0 min-w-[170px] sm:min-w-[195px] max-w-[210px] select-none ${
                    state === 'active'
                      ? 'border-blue-500 bg-white ring-4 ring-blue-500/15 shadow-[0_0_20px_rgba(59,130,246,0.22)] -translate-y-0.5'
                      : state === 'paused'
                      ? 'border-amber-400 bg-amber-50/50 ring-4 ring-amber-500/15 shadow-[0_0_15px_rgba(245,158,11,0.2)] -translate-y-0.5'
                      : state === 'failed'
                      ? 'border-red-400 bg-red-50/40 ring-2 ring-red-400/20'
                      : state === 'done'
                      ? 'border-emerald-200/90 bg-white hover:border-emerald-300 shadow-2xs hover:shadow-xs'
                      : 'border-zinc-200/90 bg-zinc-50/60 text-zinc-500 hover:border-zinc-300'
                  }`}
                >
                  {/* Top status indicator row */}
                  <div className="flex items-center justify-between gap-1 mb-2">
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono text-[11px] font-semibold text-zinc-400 group-hover:text-zinc-600 transition-colors">
                        #{idx + 1}
                      </span>
                    </div>

                    {/* Status Icon */}
                    <div className="shrink-0">
                      {state === 'active' && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-50 text-blue-700 border border-blue-200 animate-pulse">
                          <Loader2 size={11} className="animate-spin text-blue-600" />
                          <span>{isEn ? 'Running' : 'Đang xử lý'}</span>
                        </span>
                      )}
                      {state === 'done' && (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          <CheckCircle2 size={12} className="text-emerald-600" />
                          <span>{isEn ? 'Done' : 'Xong'}</span>
                        </span>
                      )}
                      {state === 'paused' && (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-800 border border-amber-300 animate-pulse">
                          <Clock size={11} className="text-amber-600" />
                          <span>{isEn ? 'Awaiting' : 'Chờ duyệt'}</span>
                        </span>
                      )}
                      {state === 'failed' && (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-red-50 text-red-700 border border-red-200">
                          <XCircle size={11} className="text-red-600" />
                          <span>{isEn ? 'Failed' : 'Lỗi'}</span>
                        </span>
                      )}
                      {state === 'pending' && (
                        <Circle size={12} className="text-zinc-300" />
                      )}
                    </div>
                  </div>

                  {/* Stage title */}
                  <div className="space-y-0.5">
                    <div className={`font-semibold text-xs sm:text-[13px] line-clamp-1 ${
                      state === 'active'
                        ? 'text-blue-900 font-bold'
                        : state === 'done'
                        ? 'text-zinc-900'
                        : 'text-zinc-700'
                    }`}>
                      {isEn ? (stage.name_en || stage.name) : stage.name}
                    </div>

                    {/* Agent badge */}
                    <div className="flex items-center gap-1 text-[11px] text-zinc-500 truncate font-medium">
                      <span className="inline-block w-1 h-1 rounded-full bg-zinc-300 group-hover:bg-zinc-400" />
                      <span>{stage.agent}</span>
                    </div>
                  </div>

                  {/* Subtle active glow bar at the bottom */}
                  {state === 'active' && (
                    <div className="absolute inset-x-0 bottom-0 h-1 bg-gradient-to-r from-blue-500 via-indigo-500 to-blue-600 rounded-b-xl" />
                  )}
                  {state === 'paused' && (
                    <div className="absolute inset-x-0 bottom-0 h-1 bg-gradient-to-r from-amber-400 via-amber-500 to-amber-600 rounded-b-xl" />
                  )}
                  {state === 'done' && (
                    <div className="absolute inset-x-0 bottom-0 h-0.5 bg-emerald-500 rounded-b-xl opacity-80" />
                  )}
                </div>

                {/* Connector between nodes (GitHub Actions line with directional arrow) */}
                {!isLast && (
                  <div className="flex items-center shrink-0 w-8 sm:w-10 px-1 relative">
                    {/* Connector line */}
                    <div
                      className={`h-[2px] w-full transition-colors duration-300 ${
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
                      size={12}
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

        {/* Constraint note on non-linear backtracking */}
        <div className="mt-2 pt-3 border-t border-zinc-100 flex items-start gap-2 text-xs text-zinc-600 leading-relaxed font-normal">
          <Info size={14} className="text-zinc-500 shrink-0 mt-0.5" />
          <span>{t('mon_backtrack_note')}</span>
        </div>
      </div>
    </div>
  );
}
