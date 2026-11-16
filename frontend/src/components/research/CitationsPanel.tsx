'use client';
import { ExternalLink } from 'lucide-react';
import { Card } from '@/components/ui/Components';
import type { CitationResponse, ResearchTaskResponse } from '@/types';

interface CitationsPanelProps {
  task: ResearchTaskResponse;
  citations: CitationResponse[];
  citationsError: string;
  loadCitations: () => Promise<void>;
  isEn: boolean;
  highlightedRef: string | null;
}

export function CitationsPanel({ task, citations, citationsError, loadCitations, isEn, highlightedRef }: CitationsPanelProps) {
  return (
              <div className="w-full max-w-7xl mx-auto space-y-6">
                <div>
                  <h2 className="text-xl font-bold text-zinc-900">{isEn ? "Linked Evidence & Citations" : "Bằng chứng & Trích dẫn có nguồn"} ({citations.length})</h2>
                  <p className="text-xs text-zinc-500 mt-0.5">
                    {isEn ? "Each citation is anchored to an indexed literature chunk and corresponding claim in the paper." : "Mỗi trích dẫn được neo chặt vào đoạn trích nguồn (chunk) và luận điểm (claim) tương ứng trong bài báo."}
                  </p>
                </div>

                {citationsError && (
                  <div className="text-sm text-red-600 bg-red-50 p-4 rounded-xl border border-red-200">
                    {citationsError} <button className="underline ml-2" onClick={() => void loadCitations()}>{isEn ? "Retry" : "Thử lại"}</button>
                  </div>
                )}

                {citations.length === 0 ? (
                  <Card className="p-8 text-center text-zinc-500">
                    {['COMPLETED', 'PARTIAL', 'NEEDS_REVIEW'].includes(task.status)
                      ? (isEn ? "No verified citations recorded for this project yet." : "Chưa có trích dẫn đã xác minh cho bài này.")
              : (isEn ? "Citations will appear when the pipeline extracts verified claims." : "Trích dẫn sẽ xuất hiện khi pipeline hoàn thành trích xuất bằng chứng.")}
                  </Card>
                ) : (
                  <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                    {citations.map((citation) => {
                      const isHighlighted = highlightedRef && (citation.citation_label.includes(highlightedRef) || String(citation.citation_number) === highlightedRef);
                      return (
                        <Card
                          key={citation.id}
                          className={`p-5 space-y-3 transition-all flex flex-col justify-between ${isHighlighted ? 'ring-2 ring-blue-500 bg-blue-50/30' : 'hover:border-zinc-300'}`}
                        >
                          <div className="space-y-3">
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-zinc-100 text-zinc-800 border border-zinc-200">
                                {citation.citation_label || `[${citation.citation_number ?? '?'}]`}
                              </span>
                              {citation.source_url ? (
                                <a
                                  href={citation.source_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-xs font-medium text-blue-600 hover:underline inline-flex items-center gap-1 max-w-xs sm:max-w-sm truncate"
                                >
                                  <span className="truncate">{citation.source_title || citation.source_url}</span>
                                  <ExternalLink size={12} className="shrink-0" />
                                </a>
                              ) : (
                                <span className="text-xs text-zinc-400">{isEn ? "No source link" : "Không có liên kết nguồn"}</span>
                              )}
                            </div>

                            {citation.claim_text && (
                              <div className="text-sm sm:text-base text-zinc-900 font-semibold leading-relaxed">
                                <span className="text-zinc-500 font-normal">{isEn ? "Source-linked claim: " : "Luận điểm gắn nguồn: "}</span>
                                {citation.claim_text}
                              </div>
                            )}

                            {citation.chunk_content && (
                              <blockquote className="text-sm text-zinc-800 border-l-4 border-blue-500 pl-4 py-2.5 italic bg-zinc-50 rounded-r-xl leading-relaxed border-t border-b border-r border-zinc-200/60">
                                &ldquo;{citation.chunk_content}&rdquo;
                              </blockquote>
                            )}
                          </div>
                        </Card>
                      );
                    })}
                  </div>
                )}
              </div>
  );
}
