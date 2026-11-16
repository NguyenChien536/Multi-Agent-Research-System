'use client';
import type { ChangeEvent, RefObject } from 'react';
import { AlertTriangle, CheckCircle2, Download, ExternalLink, FileUp, Loader2, RefreshCw, Search, UploadCloud } from 'lucide-react';
import { Badge, Card } from '@/components/ui/Components';
import { Button } from '@/components/ui/Button';
import type { ArtifactItemResponse, ResearchSourceResponse, ResearchTaskResponse } from '@/types';

interface SourcesPanelProps {
  task: ResearchTaskResponse;
  sources: ResearchSourceResponse[];
  artifacts: ArtifactItemResponse[];
  isEn: boolean;
  isWorking: boolean;
  sourcesError: string;
  loadSources: () => Promise<void>;
  handleFileUpload: (event: ChangeEvent<HTMLInputElement>) => Promise<void>;
  handleDownloadArtifact: (artifactId: string, filename: string) => Promise<void>;
  handleRetrySource: (sourceId: string) => Promise<void>;
  retryingSourceId: string | null;
  isUploading: boolean;
  uploadError: string;
  setUploadError: (value: string) => void;
  uploadSuccess: string | null;
  setUploadSuccess: (value: string | null) => void;
  fileInputRef: RefObject<HTMLInputElement>;
  formatDate: (value: string) => string;
  sourceSearch: string;
  setSourceSearch: (value: string) => void;
}

export function SourcesPanel({
  task, sources, artifacts, isEn, isWorking, sourcesError, loadSources,
  handleFileUpload, handleDownloadArtifact, handleRetrySource,
  retryingSourceId, isUploading, uploadError, setUploadError,
  uploadSuccess, setUploadSuccess, fileInputRef, formatDate, sourceSearch, setSourceSearch,
}: SourcesPanelProps) {
  const filteredSources = sources.filter(source =>
    `${source.title ?? ''} ${source.url} ${source.content_snippet ?? ''} ${source.source_tag}`
      .toLowerCase().includes(sourceSearch.toLowerCase())
  );
  return (
              <div className="w-full max-w-7xl mx-auto space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <h2 className="text-xl font-bold text-zinc-900">{isEn ? "Retrieved Literature & Sources" : "Nguồn tài liệu đã thu thập"} ({sources.length})</h2>
                    <p className="text-xs text-zinc-500 mt-0.5">{isEn ? "Websites, scientific papers, and private documents gathered and indexed by AI agents." : "Các website, bài báo khoa học và tài liệu được Agent tìm kiếm và lập chỉ mục."}</p>
                  </div>
                  <div className="relative w-full sm:w-72">
                    <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
                    <input
                      value={sourceSearch}
                      onChange={e => setSourceSearch(e.target.value)}
                      placeholder={isEn ? "Search sources..." : "Tìm trong nguồn..."}
                      className="w-full pl-9 pr-4 py-2 bg-zinc-50 border border-zinc-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
                    />
                  </div>
                </div>

                {/* PDF Ingestion Card (SRS FR-02 & Private Artifact Grounding) */}
                <Card className="p-6 sm:p-7 border-dashed border-2 border-zinc-300 bg-white hover:border-zinc-400 transition-colors rounded-2xl shadow-xs">
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <UploadCloud size={20} className="text-zinc-700" />
                        <h3 className="font-bold text-base sm:text-lg text-zinc-900">{isEn ? "Upload Private Grounding PDF" : "Tải lên tài liệu PDF riêng tư (Private Grounding)"}</h3>
                      </div>
                      <p className="text-xs text-zinc-500 leading-relaxed">
                        {isEn ? "Text is extracted and indexed as reliable grounding evidence for research agents (max 5 files, < 20MB, < 100 pages)." : "Hệ thống sẽ trích xuất và lập chỉ mục làm tài liệu tham khảo cho các tác tử nghiên cứu (tối đa 5 file, < 20MB, < 100 trang)." }
                      </p>
                    </div>

                    <div className="shrink-0 flex items-center gap-2">
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept=".pdf,application/pdf"
                        onChange={(e) => void handleFileUpload(e)}
                        className="hidden"
                        id="pdf-upload-input"
                        disabled={isUploading || task.status === 'COMPLETED' || task.status === 'CANCELLED'}
                      />
                      <Button
                        variant="outline"
                        onClick={() => fileInputRef.current?.click()}
                        isLoading={isUploading}
                        disabled={task.status === 'COMPLETED' || task.status === 'CANCELLED'}
                      >
                        <FileUp size={15} className="mr-1.5" />
                        {isUploading ? (isEn ? 'Uploading PDF...' : 'Đang nạp PDF...') : (isEn ? 'Upload PDF' : 'Tải lên PDF')}
                      </Button>
                    </div>
                  </div>

                  {uploadError && (
                    <div className="mt-3 text-xs text-red-600 bg-red-50 p-2.5 rounded-lg border border-red-200 flex items-center justify-between">
                      <span>{uploadError}</span>
                      <button onClick={() => setUploadError('')} className="text-red-400 hover:text-red-700 ml-2">✕</button>
                    </div>
                  )}

                  {uploadSuccess && (
                    <div className="mt-3 text-xs text-emerald-700 bg-emerald-50 p-2.5 rounded-lg border border-emerald-200 flex items-center justify-between">
                      <span className="flex items-center gap-1.5">
                        <CheckCircle2 size={14} className="text-emerald-600 shrink-0" />
                        {uploadSuccess}
                      </span>
                      <button onClick={() => setUploadSuccess(null)} className="text-emerald-500 hover:text-emerald-800 ml-2">✕</button>
                    </div>
                  )}
                </Card>

                {sourcesError && (
                  <div className="text-sm text-red-600 bg-red-50 p-4 rounded-xl border border-red-200">
                    {sourcesError} <button className="underline ml-2" onClick={() => void loadSources()}>{isEn ? "Retry" : "Thử lại"}</button>
                  </div>
                )}

                {sources.length === 0 ? (
                  <Card className="p-8 text-center text-zinc-500">
                    {isWorking ? (isEn ? 'Agents are searching and reviewing literature...' : 'Agent đang tìm kiếm và duyệt nguồn...') : (isEn ? 'No literature sources saved for this research project yet.' : 'Chưa có nguồn tài liệu nào được lưu cho bài nghiên cứu này.')}
                  </Card>
                ) : filteredSources.length === 0 ? (
                  <Card className="p-8 text-center text-zinc-500">
                    {isEn ? `No sources match keyword "${sourceSearch}".` : `Không tìm thấy nguồn tài liệu phù hợp với từ khóa "${sourceSearch}".`}
                  </Card>
                ) : (
                  <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                    {filteredSources.map((source) => (
                      <Card key={source.id} className="p-5 space-y-3 hover:border-zinc-300 transition-colors flex flex-col justify-between">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-zinc-100 text-zinc-800 border border-zinc-200">
                              [{source.source_tag}]
                            </span>
                            <Badge variant="outline">{source.source_type}</Badge>
                            {source.ingestion_status && (
                              <Badge variant={source.ingestion_status === 'READY' ? 'success' : source.ingestion_status === 'FAILED' ? 'danger' : source.ingestion_status === 'PROCESSING' ? 'default' : 'outline'}>
                                {source.ingestion_status === 'PROCESSING' && <Loader2 size={11} className="mr-1 inline animate-spin" />}
                                {source.ingestion_status}
                              </Badge>
                            )}
                            {source.relevance_score > 0 && (
                              <span className="text-xs text-emerald-600 font-medium">
                                {isEn ? "Relevance: " : "Liên quan: "}{(source.relevance_score * 100).toFixed(0)}%
                              </span>
                            )}
                          </div>
                          <span className="text-xs text-zinc-400">{formatDate(source.created_at)}</span>
                        </div>

                        <div>
                          {source.source_type === 'PDF' ? (
                            <div className="flex flex-col gap-2">
                              <div className="flex items-center gap-2">
                                <span className="font-semibold text-base text-zinc-900">{source.title || (isEn ? 'Internal PDF Document' : 'Tài liệu PDF nội bộ')}</span>
                                <Badge variant="purple">{isEn ? "Private Document" : "Tài liệu riêng"}</Badge>
                              </div>
                              {(() => {
                                const matchingArt = artifacts.find(a => source.url.includes(a.file_path.split('/').pop() || '') || a.file_path.includes(source.title || ''));
                                if (matchingArt) {
                                  return (
                                    <div className="pt-1">
                                      <button
                                        type="button"
                                        onClick={() => handleDownloadArtifact(matchingArt.id, matchingArt.file_path.split('/').pop() || 'document.pdf')}
                                        className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium bg-zinc-100 hover:bg-zinc-200 text-zinc-800 border border-zinc-200 transition-colors cursor-pointer"
                                      >
                                        <Download size={13} className="text-purple-600" />
                                        <span>{isEn ? "Download Original PDF" : "Tải PDF gốc"} ({(matchingArt.file_size_bytes / 1024 / 1024).toFixed(2)} MB)</span>
                                      </button>
                                    </div>
                                  );
                                }
                                return null;
                              })()}
                            </div>
                          ) : (
                            <a
                              href={source.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="font-semibold text-base text-zinc-900 hover:text-blue-600 inline-flex items-center gap-1.5 transition-colors"
                            >
                              <span>{source.title || source.url}</span>
                              <ExternalLink size={14} className="shrink-0 text-zinc-400" />
                            </a>
                          )}
                          <div className="text-xs font-mono text-zinc-600 mt-1 truncate">{source.url}</div>
                        </div>

                        {(source.venue || source.search_provider || source.doi) && (
                          <div className="text-xs text-zinc-500 flex flex-wrap items-center gap-2">
                            {source.search_provider && (
                              <span className="px-1.5 py-0.5 rounded bg-zinc-100 text-zinc-700 border border-zinc-200 font-medium">
                                {source.search_provider}
                              </span>
                            )}
                            {source.venue && <span className="italic">{source.venue}</span>}
                            {source.doi && <span className="font-mono text-zinc-400">DOI: {source.doi}</span>}
                          </div>
                        )}

                        {source.ingestion_status === 'FAILED' && (
                          <div className="p-3 bg-red-50/80 border border-red-200 rounded-lg text-xs space-y-2">
                            <div className="flex items-start gap-2 text-red-700">
                              <AlertTriangle size={14} className="shrink-0 mt-0.5 text-red-600" />
                              <div className="flex-1">
                                <span className="font-semibold">{isEn ? 'Ingestion Failed: ' : 'Trích xuất thất bại: '}</span>
                                <span className="text-red-600">{source.ingestion_error || (isEn ? 'Unknown extraction error.' : 'Lỗi trích xuất không xác định.')}</span>
                              </div>
                            </div>
                            <Button
                              variant="danger-outline"
                              className="!h-8 !px-3 text-xs"
                              onClick={() => void handleRetrySource(source.id)}
                              isLoading={retryingSourceId === source.id}
                            >
                              <RefreshCw size={12} className="mr-1.5" />
                              {isEn ? 'Retry Ingestion' : 'Thử lại trích xuất'}
                            </Button>
                          </div>
                        )}

                        {source.content_snippet && (
                          <p className="text-sm leading-relaxed text-zinc-700 bg-zinc-50 p-3.5 rounded-xl border border-zinc-200 line-clamp-4">
                            {source.content_snippet}
                          </p>
                        )}

                        {source.attribution && (
                          <div className="text-xs text-zinc-500 border-t border-zinc-100 pt-2 flex items-center justify-between">
                            <span>{isEn ? "Attribution: " : "Tác quyền: "}{source.attribution}</span>
                            {source.license_name && <span>{isEn ? "License: " : "Giấy phép: "}{source.license_name}</span>}
                          </div>
                        )}
                      </Card>
                    ))}
                  </div>
                )}
              </div>
  );
}
