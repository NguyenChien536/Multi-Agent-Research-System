import { Download, FlaskConical } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Components";
import { MarkdownViewer } from "@/components/ui/MarkdownViewer";
import type { ProtocolResponse, ResearchTaskResponse } from "@/types";

interface ProtocolPanelProps {
  task: ResearchTaskResponse;
  isEn: boolean;
  protocol: ProtocolResponse | null;
  protocolError: string;
  onDownloadArtifact: (artifactId: string, filename: string) => Promise<void>;
}

export function ProtocolPanel({
  task,
  isEn,
  protocol,
  protocolError,
  onDownloadArtifact,
}: ProtocolPanelProps) {
  return (
    <div className="w-full max-w-7xl mx-auto space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-zinc-200 pb-4">
        <div>
          <h2 className="text-lg font-bold text-zinc-900 flex items-center gap-2">
            <FlaskConical size={18} className="text-indigo-600" />
            {isEn ? "Study Protocol" : "Đề cương nghiên cứu (Study Protocol)"}
          </h2>
          <p className="text-xs text-zinc-500 mt-0.5">
            {isEn
              ? "Intermediate methodological artifact designed by the Methodologist Agent"
              : "Văn bản trung gian (Intermediate Artifact) được thiết kế bởi Agent Methodologist"}
          </p>
        </div>
        {task.protocol_artifact_id && (
          <Button
            variant="outline"
            onClick={() =>
              void onDownloadArtifact(
                task.protocol_artifact_id!,
                "study_protocol.md",
              )
            }
          >
            <Download size={14} className="mr-1.5" />{" "}
            {isEn ? "Download (.md)" : "Tải về (.md)"}
          </Button>
        )}
      </div>

      {protocolError && (
        <div className="p-4 bg-red-50 text-red-700 text-xs rounded-xl border border-red-200">
          {protocolError}
        </div>
      )}

      {protocol?.content_markdown ? (
        <Card className="p-8 sm:p-12 bg-white shadow-xs">
          <MarkdownViewer
            content={protocol.content_markdown}
            academicStyle={true}
          />
        </Card>
      ) : (
        <div className="p-8 text-center text-zinc-400">
          {isEn
            ? "Loading study protocol..."
            : "Đang tải nội dung đề cương nghiên cứu..."}
        </div>
      )}
    </div>
  );
}
