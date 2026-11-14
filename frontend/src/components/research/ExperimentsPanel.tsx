"use client";

import type { ChangeEvent, RefObject } from 'react';
import { AlertTriangle, CheckCircle2, Clock, Database, Download, FlaskConical, UploadCloud, XCircle } from 'lucide-react';
import { Badge, Card } from '@/components/ui/Components';
import { Button } from '@/components/ui/Button';
import { api } from '@/lib/api';
import type { ResearchTaskResponse, ArtifactItemResponse, AnalysisRunResponse, ExperimentJournalEntryResponse } from '@/types';

interface ExperimentsPanelProps {
  task: ResearchTaskResponse;
  artifacts: ArtifactItemResponse[];
  experiments: AnalysisRunResponse[];
  journal: ExperimentJournalEntryResponse[];
  isEn: boolean;
  language: 'en' | 'vi';
  formatDate: (value: string, language: 'en' | 'vi') => string;
  datasetFileInputRef: RefObject<HTMLInputElement>;
  handleUploadDataset: (event: ChangeEvent<HTMLInputElement>) => void;
  isUploadingDataset: boolean;
  datasetUploadError: string | null;
  datasetUploadSuccess: string | null;
}

export function ExperimentsPanel({ task, artifacts, experiments, journal, isEn, language, formatDate, datasetFileInputRef, handleUploadDataset, isUploadingDataset, datasetUploadError, datasetUploadSuccess }: ExperimentsPanelProps) {
  return (
              <div className="w-full max-w-7xl mx-auto space-y-6">
                {/* 1. DATASET MANAGEMENT CARD */}
                <Card className="p-6">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-100 pb-4">
                    <div>
                      <h2 className="font-semibold text-zinc-900 text-base flex items-center gap-2">
                        <Database size={18} className="text-blue-600" />
                        {isEn ? "Experimental Dataset (Dataset CSV)" : "Tập dữ liệu thực nghiệm (Dataset CSV)"}
                      </h2>
                      <p className="text-xs text-zinc-500 mt-1">
                        {isEn ? <>Provide tabular numeric CSV dataset for computational routine <code className="px-1.5 py-0.5 rounded bg-zinc-100 text-zinc-800 font-mono">tabular_regression_v1</code>.</> : <>Cung cấp tệp CSV dữ liệu số phục vụ routine tính toán <code className="px-1.5 py-0.5 rounded bg-zinc-100 text-zinc-800 font-mono">tabular_regression_v1</code>.</>}
                      </p>
                    </div>
                    <div>
                      <input
                        ref={datasetFileInputRef}
                        type="file"
                        accept=".csv"
                        onChange={handleUploadDataset}
                        className="hidden"
                      />
                      <Button
                        variant="outline"
                        onClick={() => datasetFileInputRef.current?.click()}
                        disabled={isUploadingDataset || !['PENDING', 'WAITING_APPROVAL', 'WAITING_USER_DATA'].includes(task.status)}
                        className="text-xs"
                      >
                        <UploadCloud size={14} className="mr-1.5" />
                        {isUploadingDataset ? (isEn ? 'Uploading...' : 'Đang tải lên...') : (isEn ? 'Upload Dataset (.csv)' : 'Tải lên tập dữ liệu (.csv)')}
                      </Button>
                    </div>
                  </div>

                  {datasetUploadError && (
                    <div className="mt-3 p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg flex items-center gap-2">
                      <XCircle size={14} className="shrink-0" />
                      <span>{datasetUploadError}</span>
                    </div>
                  )}

                  {datasetUploadSuccess && (
                    <div className="mt-3 p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-lg flex items-center gap-2">
                      <CheckCircle2 size={14} className="shrink-0 text-emerald-600" />
                      <span>{datasetUploadSuccess}</span>
                    </div>
                  )}

                  {/* Artifacts with DATASET_CSV */}
                  {(() => {
                    const dsArtifact = artifacts.find(a => a.export_type === 'DATASET_CSV');
                    return (
                      <div className="mt-4 p-4 rounded-xl bg-zinc-50 border border-zinc-200/80 text-xs">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                          <div>
                            <span className="font-semibold text-zinc-800">
                              {dsArtifact ? (isEn ? `Dataset: ${dsArtifact.file_path.split('/').pop()}` : `Tập dữ liệu: ${dsArtifact.file_path.split('/').pop()}`) : (isEn ? 'Data Mode: Standard synthetic benchmark dataset (50 samples, seed 42)' : 'Chế độ dữ liệu: Tự động sinh tập benchmark số đối chuẩn (50 mẫu, seed 42)')}
                            </span>
                            <p className="text-zinc-500 text-[11px] mt-0.5">
                              {dsArtifact
                                ? (isEn ? `Size: ${(dsArtifact.file_size_bytes / 1024).toFixed(1)} KB` : `Dung lượng: ${(dsArtifact.file_size_bytes / 1024).toFixed(1)} KB`)
                                : (isEn ? 'System automatically uses standardized benchmark data if no custom dataset is provided.' : 'Hệ thống tự động sử dụng tập dữ liệu chuẩn hóa nếu bạn không tải lên tệp tùy chỉnh.')}
                            </p>
                          </div>
                          {dsArtifact && (
                            <a
                              href={api.tasks.getArtifactDownloadUrl(task.id, dsArtifact.id)}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-100 font-medium text-xs self-start sm:self-auto"
                            >
                              <Download size={13} /> {isEn ? "Download CSV" : "Tải CSV"}
                            </a>
                          )}
                        </div>
                      </div>
                    );
                  })()}
                </Card>

                {/* 2. LATEST EXPERIMENT RUN & METRICS COMPARISON */}
                {experiments.length > 0 ? (
                  experiments.map((exp, idx) => {
                    const m = exp.metrics || {};
                    const baseM = m.baseline || {};
                    const modelM = m.model || {};
                    const comp = m.comparison || {};
                    const verdict = comp.verdict;
                    const reproStatus = exp.reproducibility_status;

                    return (
                      <Card key={exp.id || idx} className="p-6 space-y-5">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-zinc-100 pb-4">
                          <div>
                            <div className="flex items-center gap-2">
                              <h2 className="font-semibold text-zinc-900 text-base">
                                Routine: <code className="font-mono text-indigo-700">{exp.routine_name}</code>
                              </h2>
                              <Badge variant="outline" className="text-xs">
                                {exp.status}
                              </Badge>
                            </div>
                            <p className="text-xs text-zinc-500 mt-1 font-mono">
                              Checksum: {exp.input_checksum ? exp.input_checksum.slice(0, 16) + '...' : 'N/A'} • {exp.manifest.valid_rows || exp.manifest.dataset_rows || 50} {isEn ? 'samples' : 'mẫu'} • Split 80/20 (seed 42)
                            </p>
                          </div>
                          <div>
                            {reproStatus === 'PASSED' ? (
                              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-100 text-emerald-800 text-xs font-medium border border-emerald-200">
                                <CheckCircle2 size={13} className="text-emerald-600" />
                                {isEn ? "Repeatability check PASSED (abs diff ≤ 10⁻⁸)" : "Tái lập kiểm chứng ĐẠT (abs diff ≤ 10⁻⁸)"}
                              </span>
                            ) : reproStatus === 'FAILED' ? (
                              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-red-100 text-red-800 text-xs font-medium border border-red-200">
                                <XCircle size={13} className="text-red-600" />
                                {isEn ? "Repeatability check FAILED" : "Tái lập kiểm chứng THẤT BẠI"}
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-zinc-100 text-zinc-600 text-xs font-medium">
                                {isEn ? "Repeatability not checked" : "Chưa kiểm tái lập"}
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Comparative Metrics Table */}
                        <div>
                          <h3 className="text-xs font-semibold text-zinc-700 uppercase tracking-wider mb-2">
                            {isEn ? "Scientific Empirical Benchmarks" : "Bảng đo lường đối chứng khoa học (Empirical Benchmarks)"}
                          </h3>
                          <div className="overflow-x-auto rounded-xl border border-zinc-200">
                            <table className="w-full text-xs text-left">
                              <thead className="bg-zinc-50 text-zinc-700 border-b border-zinc-200 font-medium">
                                <tr>
                                  <th className="py-2.5 px-4">{isEn ? "Model" : "Mô hình"}</th>
                                  <th className="py-2.5 px-4">{isEn ? "MAE (Primary Metric)" : "MAE (Chỉ số chính)"}</th>
                                  <th className="py-2.5 px-4">{isEn ? "RMSE (Secondary Metric)" : "RMSE (Chỉ số phụ)"}</th>
                                  <th className="py-2.5 px-4">{isEn ? "Coefficient of Determination R²" : "Hệ số xác định R²"}</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-zinc-200">
                                <tr className="hover:bg-zinc-50/50">
                                  <td className="py-2.5 px-4 font-medium text-zinc-800">
                                    Mean Baseline <span className="text-zinc-400 font-normal">({isEn ? "Sample Mean" : "Nghiệm trung bình"})</span>
                                  </td>
                                  <td className="py-2.5 px-4 font-mono">{baseM.mae != null ? baseM.mae.toFixed(6) : '—'}</td>
                                  <td className="py-2.5 px-4 font-mono">{baseM.rmse != null ? baseM.rmse.toFixed(6) : '—'}</td>
                                  <td className="py-2.5 px-4 font-mono">{baseM.r2 != null ? baseM.r2.toFixed(6) : '—'}</td>
                                </tr>
                                <tr className="hover:bg-zinc-50/50 bg-indigo-50/20">
                                  <td className="py-2.5 px-4 font-medium text-indigo-900">
                                    Ridge Regression <span className="text-indigo-600 font-normal">(alpha=1.0)</span>
                                  </td>
                                  <td className="py-2.5 px-4 font-mono font-semibold text-indigo-900">{modelM.mae != null ? modelM.mae.toFixed(6) : '—'}</td>
                                  <td className="py-2.5 px-4 font-mono text-indigo-900">{modelM.rmse != null ? modelM.rmse.toFixed(6) : '—'}</td>
                                  <td className="py-2.5 px-4 font-mono text-indigo-900">{modelM.r2 != null ? modelM.r2.toFixed(6) : '—'}</td>
                                </tr>
                                <tr className="bg-zinc-50/80 font-medium">
                                  <td className="py-2.5 px-4 text-zinc-700">{isEn ? "Delta (Ridge - Baseline)" : "Chênh lệch (Delta: Ridge - Baseline)"}</td>
                                  <td className={`py-2.5 px-4 font-mono ${comp.delta_mae != null && comp.delta_mae < 0 ? 'text-emerald-700 font-semibold' : 'text-zinc-700'}`}>
                                    {comp.delta_mae != null ? (comp.delta_mae > 0 ? `+${comp.delta_mae.toFixed(6)}` : comp.delta_mae.toFixed(6)) : '—'}
                                  </td>
                                  <td className="py-2.5 px-4 font-mono text-zinc-700">
                                    {comp.delta_rmse != null ? (comp.delta_rmse > 0 ? `+${comp.delta_rmse.toFixed(6)}` : comp.delta_rmse.toFixed(6)) : '—'}
                                  </td>
                                  <td className="py-2.5 px-4 text-zinc-500">—</td>
                                </tr>
                              </tbody>
                            </table>
                          </div>
                        </div>

                        {/* Verdict Card */}
                        {verdict && (
                          <div className={`p-4 rounded-xl border text-xs ${verdict === 'IMPROVEMENT' ? 'bg-emerald-50 border-emerald-200 text-emerald-900' : 'bg-amber-50 border-amber-200 text-amber-900'}`}>
                            <div className="flex items-center gap-2 font-semibold">
                              {verdict === 'IMPROVEMENT' ? (
                                <>
                                  <CheckCircle2 size={16} className="text-emerald-600" />
                                  <span>{isEn ? `Verdict: IMPROVEMENT — Ridge Regression reduced MAE error (${comp.pct_improvement ?? 0}% relative to baseline).` : `Kết luận: CẢI THIỆN (IMPROVEMENT) — Ridge Regression giảm sai số MAE (${comp.pct_improvement ?? 0}% so với baseline).`}</span>
                                </>
                              ) : (
                                <>
                                  <AlertTriangle size={16} className="text-amber-600" />
                                  <span>{isEn ? "Verdict: NO_IMPROVEMENT — Valid negative result integrity. Ridge regression did not outperform simple sample mean." : "Kết luận: KHÔNG CẢI THIỆN (NO_IMPROVEMENT) — Kết quả âm hợp lệ (Negative Result Integrity). Ridge regression không vượt trội hơn nghiệm trung bình đơn giản."}</span>
                                </>
                              )}
                            </div>
                            <p className="mt-1 text-[11px] opacity-80">
                              {isEn ? "Scientific Integrity Principle: All empirical measurements (whether improved or negative findings) are transparently recorded and included in the paper." : "Nguyên tắc tính toàn vẹn khoa học: Mọi kết quả đo lường (dù tốt hơn hay không cải thiện) đều được báo cáo minh bạch và đưa vào bản thảo bài báo."}
                            </p>
                          </div>
                        )}

                        {/* Non-causal Disclaimer */}
                        <div className="p-3 bg-zinc-50 rounded-xl border border-zinc-200 text-[11px] text-zinc-600">
                          {isEn ? <><strong>Scientific Limitation:</strong> Regression model measures predictive correlation on test splits (exploratory). Results must never be interpreted as causal relationships (non-causal).</> : <><strong>Giới hạn khoa học:</strong> Mô hình hồi quy đo lường mối tương quan và hiệu năng dự đoán trên tập kiểm thử (predictive/exploratory). Kết quả tuyệt đối không được suy luận thành quan hệ nhân quả (non-causal).</>}
                        </div>

                        {/* Experiment Artifacts */}
                        <div className="pt-2">
                          <h4 className="text-xs font-semibold text-zinc-700 mb-2">{isEn ? "Stored Experimental Artifacts" : "Tệp dữ liệu thực nghiệm đã lưu (Artifacts)"}</h4>
                          <div className="flex flex-wrap gap-2">
                            {artifacts
                              .filter(a => ['METRICS_JSON', 'MANIFEST_JSON', 'CHART_DATA_JSON', 'REPRO_README'].includes(a.export_type))
                              .map(art => (
                                <a
                                  key={art.id}
                                  href={api.tasks.getArtifactDownloadUrl(task.id, art.id)}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50 text-xs font-mono"
                                >
                                  <Download size={12} />
                                  {art.file_path.split('/').pop()}
                                </a>
                              ))}
                          </div>
                        </div>
                      </Card>
                    );
                  })
                ) : (
                  <Card className="p-8 text-center text-zinc-500">
                    <FlaskConical size={32} className="mx-auto text-zinc-400 mb-2" />
                    <p className="text-sm font-medium text-zinc-700">{isEn ? "No computational routine results yet" : "Chưa có kết quả thực nghiệm tính toán"}</p>
                    <p className="text-xs text-zinc-500 mt-1">
                      {task.status === 'PENDING'
                        ? (isEn ? 'Click Start Research to launch the empirical benchmark pipeline.' : 'Nhấn Bắt đầu nghiên cứu để khởi chạy pipeline tính toán đối chuẩn.')
                        : (isEn ? 'Routine tabular_regression_v1 will run automatically during the pipeline.' : 'Routine tabular_regression_v1 sẽ tự động chạy trong luồng nghiên cứu.')}
                    </p>
                  </Card>
                )}

                {/* 3. SCIENTIFIC AUDIT JOURNAL TIMELINE */}
                {journal.length > 0 && (
                  <Card className="p-6">
                    <h3 className="font-semibold text-zinc-900 text-sm mb-4 flex items-center gap-2">
                      <Clock size={16} className="text-zinc-600" />
                      {isEn ? "Scientific Experiment Journal (Immutable Append-Only Audit Log)" : "Sổ nhật ký thí nghiệm nghiên cứu (Immutable Append-Only Journal)"}
                    </h3>
                    <div className="relative border-l-2 border-zinc-200 ml-3 space-y-6">
                      {journal.map(entry => {
                        const kindColors: Record<string, string> = {
                          PLAN_FROZEN: 'border-zinc-200 bg-zinc-100 text-zinc-800',
                          STARTED: 'border-zinc-200 bg-zinc-100 text-zinc-800',
                          EXECUTION_RESULT: 'border-zinc-200 bg-zinc-100 text-zinc-800',
                          OBSERVATION: 'border-zinc-200 bg-zinc-100 text-zinc-800',
                          REPRODUCTION_CHECK: 'border-zinc-200 bg-zinc-100 text-zinc-800',
                          INTERPRETATION: 'border-zinc-200 bg-zinc-100 text-zinc-800',
                        };
                        const colorClass = kindColors[entry.kind] || 'border-zinc-200 bg-white text-zinc-800';

                        return (
                          <div key={entry.id} className="relative pl-6">
                            <span className="absolute -left-3 top-1 w-5 h-5 rounded-full border border-zinc-300 bg-white flex items-center justify-center text-[10px] font-bold text-zinc-700">
                              {entry.sequence}
                            </span>
                            <div className="space-y-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-md border ${colorClass}`}>
                                  {entry.kind}
                                </span>
                                <span className="text-xs text-zinc-400 font-mono">
                                  {isEn ? "Agent: " : "Tác tử: "}<strong className="text-zinc-700">{entry.actor}</strong> • {formatDate(entry.created_at, language)}
                                </span>
                              </div>
                              {entry.payload && (
                                <div className="p-3 bg-zinc-50 rounded-lg text-xs font-mono text-zinc-700 overflow-x-auto mt-1 border border-zinc-200/60 leading-relaxed">
                                  {entry.payload.summary ? (
                                    <p className="font-sans text-zinc-800">{entry.payload.summary}</p>
                                  ) : (
                                    <pre className="text-[11px]">{JSON.stringify(entry.payload, null, 2)}</pre>
                                  )}
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </Card>
                )}
              </div>
  );
}
