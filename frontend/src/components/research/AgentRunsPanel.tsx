"use client";

import { Activity } from 'lucide-react';
import { Badge, Card } from '@/components/ui/Components';
import type { AgentRunResponse, ResearchTaskResponse } from '@/types';

interface AgentRunsPanelProps {
  task: ResearchTaskResponse;
  runs: AgentRunResponse[];
  runsError: string | null;
  runStatusFilter: string;
  isWorking: boolean;
  isEn: boolean;
  language: 'en' | 'vi';
  formatDate: (value: string, language: 'en' | 'vi') => string;
}

export function AgentRunsPanel({ task, runs, runsError, runStatusFilter, isWorking, isEn, language, formatDate }: AgentRunsPanelProps) {
  return (
              <div className="w-full max-w-7xl mx-auto space-y-6">
                {/* KPI Overview */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div className="p-4 rounded-xl border border-zinc-200 bg-white shadow-sm space-y-1">
                    <span className="text-xs text-zinc-500 font-medium">{isEn ? "Total Cost" : "Tổng chi phí"}</span>
                    <div className="text-xl font-bold text-zinc-900 font-mono">${Number(task.total_cost_usd).toFixed(4)}</div>
                    <span className="text-xs text-zinc-700 font-medium">{isEn ? "Estimated USD" : "USD ước tính"}</span>
                  </div>
                  <div className="p-4 rounded-xl border border-zinc-200 bg-white shadow-sm space-y-1">
                    <span className="text-xs text-zinc-500 font-medium">{isEn ? "Total Tokens" : "Tổng Tokens"}</span>
                    <div className="text-xl font-bold text-zinc-900 font-mono">{task.total_tokens_used.toLocaleString('vi-VN')}</div>
                    <span className="text-xs text-zinc-700 font-medium">Input + Output</span>
                  </div>
                  <div className="p-4 rounded-xl border border-zinc-200 bg-white shadow-sm space-y-1">
                    <span className="text-xs text-zinc-500 font-medium">{isEn ? "Agent Runs" : "Lượt chạy Agent"}</span>
                    <div className="text-xl font-bold text-zinc-900">{runs.length}</div>
                    <span className="text-xs text-zinc-700 font-medium">{isEn ? "Recorded" : "Đã ghi nhận"}</span>
                  </div>
                  <div className="p-4 rounded-xl border border-zinc-200 bg-white shadow-sm space-y-1">
                    <span className="text-xs text-zinc-500 font-medium">{isEn ? "Completion Time" : "Thời gian hoàn tất"}</span>
                    <div className="text-sm font-semibold text-zinc-800 line-clamp-1 mt-1">
                      {task.completed_at ? formatDate(task.completed_at, language) : isWorking ? (isEn ? 'Running...' : 'Đang thực thi...') : (isEn ? 'Not completed' : 'Chưa hoàn tất')}
                    </div>
                    <span className="text-xs text-zinc-700 font-medium">{isEn ? "Attempt #" : "Lần chạy #"}{task.attempt_number}</span>
                  </div>
                </div>

                {/* Workflow Allowance & Quota Status Card */}
                {task.token_allowance && (
                  <Card className="p-5 border border-zinc-200 bg-white space-y-3 shadow-xs">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-zinc-100 pb-2.5">
                      <div>
                        <h3 className="font-bold text-sm text-zinc-900">
                          {isEn ? "Shared Agent Workflow Allowance" : "Hạn mức phân bổ toàn chu trình tác tử"}
                        </h3>
                        <p className="text-xs text-zinc-500 mt-0.5">
                          {isEn
                            ? "The agents in this research workflow share these limits. You may approve an increase within the system ceiling."
                            : "Các tác tử trong bài nghiên cứu này dùng chung hạn mức. Bạn có thể duyệt tăng trong trần của hệ thống."}
                        </p>
                      </div>
                      {task.token_allowance.can_extend && (
                        <span className="shrink-0 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          {isEn ? "Extension Available" : "Có thể tăng hạn mức"}
                        </span>
                      )}
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                      <div className="p-3 rounded-lg bg-zinc-50 border border-zinc-200/80">
                        <span className="text-zinc-500 font-medium block mb-0.5">{isEn ? "Cost Allowance" : "Hạn mức chi phí"}</span>
                        <div className="font-mono font-bold text-zinc-900 text-sm">
                          ${task.token_allowance.cost_used_usd != null ? task.token_allowance.cost_used_usd.toFixed(4) : Number(task.total_cost_usd).toFixed(4)}
                          <span className="text-zinc-500 text-xs font-normal"> / {task.token_allowance.max_cost_usd != null ? `$${task.token_allowance.max_cost_usd.toFixed(2)}` : '—'}</span>
                        </div>
                      </div>

                      <div className="p-3 rounded-lg bg-zinc-50 border border-zinc-200/80">
                        <span className="text-zinc-500 font-medium block mb-0.5">{isEn ? "Model Calls" : "Lượt gọi mô hình"}</span>
                        <div className="font-mono font-bold text-zinc-900 text-sm">
                          {task.token_allowance.calls_used ?? runs.length}
                          <span className="text-zinc-500 text-xs font-normal"> / {task.token_allowance.max_llm_calls ?? '—'}</span>
                        </div>
                      </div>

                      <div className="p-3 rounded-lg bg-zinc-50 border border-zinc-200/80">
                        <span className="text-zinc-500 font-medium block mb-0.5">{isEn ? "Input Tokens" : "Token đầu vào (Input)"}</span>
                        <div className="font-mono font-bold text-zinc-900 text-sm">
                          {task.token_allowance.input_used ? task.token_allowance.input_used.toLocaleString() : '0'}
                          <span className="text-zinc-500 text-xs font-normal"> / {task.token_allowance.max_input_tokens != null ? task.token_allowance.max_input_tokens.toLocaleString() : '—'}</span>
                        </div>
                      </div>

                      <div className="p-3 rounded-lg bg-zinc-50 border border-zinc-200/80">
                        <span className="text-zinc-500 font-medium block mb-0.5">{isEn ? "Output Tokens" : "Token tạo ra (Output)"}</span>
                        <div className="font-mono font-bold text-zinc-900 text-sm">
                          {task.token_allowance.output_used ? task.token_allowance.output_used.toLocaleString() : '0'}
                          <span className="text-zinc-500 text-xs font-normal"> / {task.token_allowance.max_output_tokens != null ? task.token_allowance.max_output_tokens.toLocaleString() : '—'}</span>
                        </div>
                      </div>
                    </div>
                  </Card>
                )}

                {runsError && (
                  <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700">
                    {runsError}
                  </div>
                )}

                {runs.length === 0 ? (
                  <Card className="p-8 text-center text-zinc-600 max-w-xl mx-auto space-y-3">
                    <Activity size={36} className="mx-auto text-zinc-400" />
                    <div>
                      <h3 className="font-semibold text-zinc-900 text-base">{isEn ? "No agent runs recorded yet" : "Chưa có lượt chạy agent nào"}</h3>
                      <p className="text-sm text-zinc-500 mt-1">
                        {isEn ? "When the research pipeline executes, individual agent steps, tokens, and estimated costs will display here." : "Khi bài nghiên cứu bắt đầu chạy, tiến trình từng agent cùng token và chi phí sẽ hiển thị chi tiết tại đây."}
                      </p>
                    </div>
                  </Card>
                ) : (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h2 className="text-base font-bold text-zinc-900">{isEn ? "Agent Execution Sequence" : "Chi tiết chuỗi thực thi tác tử"}</h2>
                      <span className="text-xs text-zinc-500">{runs.length} {isEn ? "runs" : "tác tử"}</span>
                    </div>

                    <div className="relative border-l-2 border-zinc-200 ml-4 pl-6 space-y-6">
                      {runs.filter(r => runStatusFilter === 'ALL' || r.status === runStatusFilter).map((run, index) => {
                        const isSuccess = run.status === 'SUCCESS';
                        const isRunning = run.status === 'RUNNING';
                        return (
                          <div key={run.id} className="relative">
                            {/* Timeline bullet */}
                            <span className={`absolute -left-[33px] top-1.5 w-4 h-4 rounded-full border-2 border-white flex items-center justify-center ${
                              isSuccess ? 'bg-emerald-500 ring-2 ring-emerald-200' : isRunning ? 'bg-blue-500 ring-2 ring-blue-200 animate-pulse' : 'bg-red-500 ring-2 ring-red-200'
                            }`} />

                            <Card className="p-5 space-y-3 hover:border-zinc-300 transition-all shadow-sm">
                              {/* Run Header */}
                              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-100 pb-2.5">
                                <div className="flex items-center gap-2">
                                  <span className="font-bold text-sm text-zinc-900">
                                    #{index + 1} {run.agent_name}
                                  </span>
                                  <Badge variant={isSuccess ? 'success' : isRunning ? 'default' : 'danger'}>
                                    {run.status}
                                  </Badge>
                                  {run.iteration > 0 && (
                                    <span className="text-xs px-2 py-0.5 rounded-full bg-zinc-100 text-zinc-600 font-mono">
                                      {isEn ? "Iteration" : "Vòng"} {run.iteration}
                                    </span>
                                  )}
                                </div>

                                <div className="flex items-center gap-3 text-xs text-zinc-500 font-mono">
                                  <span>{run.duration_ms >= 1000 ? `${(run.duration_ms / 1000).toFixed(2)}s` : `${run.duration_ms}ms`}</span>
                                  {run.model && (
                                    <span className="px-2 py-0.5 rounded bg-zinc-100 text-zinc-700 border border-zinc-200">
                                      {run.model}
                                    </span>
                                  )}
                                </div>
                              </div>

                              {/* Token and Cost Metrics */}
                              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-zinc-50/90 p-3.5 sm:p-4 rounded-xl border border-zinc-200/80">
                                <div>
                                  <span className="text-sm text-zinc-600 font-medium block">Tokens Input:</span>
                                  <div className="text-base sm:text-lg font-bold text-zinc-900 font-mono mt-0.5">{run.input_tokens.toLocaleString()}</div>
                                </div>
                                <div>
                                  <span className="text-sm text-zinc-600 font-medium block">Tokens Output:</span>
                                  <div className="text-base sm:text-lg font-bold text-zinc-900 font-mono mt-0.5">{run.output_tokens.toLocaleString()}</div>
                                </div>
                                <div>
                                  <span className="text-sm text-zinc-600 font-medium block">{isEn ? "Total Tokens:" : "Tổng Tokens:"}</span>
                                  <div className="text-base sm:text-lg font-bold text-zinc-900 font-mono mt-0.5">{(run.input_tokens + run.output_tokens).toLocaleString()}</div>
                                </div>
                                <div>
                                  <span className="text-sm text-zinc-600 font-medium block">{isEn ? "Estimated Cost:" : "Chi phí ước tính:"}</span>
                                  <div className="text-base sm:text-lg font-bold text-zinc-900 font-mono mt-0.5">${Number(run.estimated_cost).toFixed(6)}</div>
                                </div>
                              </div>

                              {/* Summaries */}
                              {(Object.keys(run.input_summary || {}).length > 0 || Object.keys(run.output_summary || {}).length > 0) && (
                                <div className="space-y-2 pt-1 text-sm">
                                  {Object.keys(run.output_summary || {}).length > 0 && (
                                    <div className="text-zinc-700 flex flex-wrap items-center gap-2">
                                      <span className="font-semibold text-zinc-800 text-sm">{isEn ? "Agent Output: " : "Kết quả đầu ra: "}</span>
                                      <span className="font-mono text-sm text-zinc-900 bg-zinc-100 px-2 py-1 rounded-md border border-zinc-200/60">
                                        {JSON.stringify(run.output_summary)}
                                      </span>
                                    </div>
                                  )}
                                  {run.tool_calls && run.tool_calls.length > 0 && (
                                    <div className="text-zinc-700 flex flex-wrap items-center gap-2">
                                      <span className="font-semibold text-zinc-800 text-sm">{isEn ? "Tools Executed: " : "Công cụ đã gọi: "}</span>
                                      <span className="font-mono text-zinc-800 flex flex-wrap gap-1.5">
                                        {run.tool_calls.map((tc, idx) => (
                                          <span key={idx} className="inline-block px-2 py-0.5 rounded-md bg-zinc-100 text-zinc-900 border border-zinc-200 font-mono text-xs sm:text-sm font-medium">
                                            {tc.tool || JSON.stringify(tc)}
                                          </span>
                                        ))}
                                      </span>
                                    </div>
                                  )}
                                </div>
                              )}

                              {run.error_message && (
                                <div className="text-xs text-red-700 bg-red-50 p-2.5 rounded-lg border border-red-200">
                                  <strong>{isEn ? "Error: " : "Lỗi: "}</strong>{run.error_message}
                                </div>
                              )}
                            </Card>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
  );
}
