import { useEffect, useRef } from "react";
import { Check, AlertCircle, Loader2, Clock } from "lucide-react";
import { getStatus } from "@/lib/api";
import { cn } from "@/lib/utils";
import styles from "./css/ProcessingStep.module.css";

export type StageStatus = "waiting" | "running" | "done" | "error";

export interface PipelineStage {
  name: string;
  status: StageStatus;
}

const STAGE_NAMES = [
  "Extração de PDF",
  "Carregamento Base",
  "Embeddings",
  "Índice FAISS",
  "Setup Gemini",
  "Geração Markdown",
  "PDF da Apostila",
  "Geração de Vídeo",
];

interface ProcessingStepProps {
  stages: PipelineStage[];
  onStagesUpdate: (stages: PipelineStage[]) => void;
  onComplete: () => void;
}

const statusIcon = (status: StageStatus) => {
  switch (status) {
    case "waiting": return <Clock className="w-5 h-5 text-muted-foreground" />;
    case "running": return <Loader2 className="w-5 h-5 text-primary animate-spin" />;
    case "done":    return <Check className="w-5 h-5 text-green-500" />;
    case "error":   return <AlertCircle className="w-5 h-5 text-destructive" />;
  }
};

const ProcessingStep = ({ stages, onStagesUpdate, onComplete }: ProcessingStepProps) => {
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const data = await getStatus();

        // Mapeia os stages do backend para o formato do front
        const updated: PipelineStage[] = data.stages.map((s: { name: string; status: string }) => ({
          name: s.name,
          status: s.status as StageStatus,
        }));

        onStagesUpdate(updated);

        // Pipeline pausou para aprovação → avança para etapa 3
        if (data.status === "awaiting_approval") {
          clearInterval(interval);
          onCompleteRef.current();
        }

        // Erro no pipeline
        if (data.status === "error") {
          clearInterval(interval);
        }
      } catch (err) {
        console.error("Erro no polling:", err);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [onStagesUpdate]);

  const stageLabelClass = (status: StageStatus) => {
    switch (status) {
      case "waiting": return styles.stageWaiting;
      case "running": return styles.stageRunning;
      case "done": return styles.stageDone;
      case "error": return styles.stageError;
    }
  };

  return (
    <div className={styles.wrap}>
      <p className={styles.caption}>
        Processando seus documentos…
      </p>
      <div className={styles.list}>
        {stages.map((stage, i) => (
          <div
            key={i}
            className={cn(styles.stageRow, stage.status === "running" && styles.stageRowRunning)}
          >
            {statusIcon(stage.status)}
            <span className={cn(styles.stageLabel, stageLabelClass(stage.status))}>
              {stage.name}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

export { STAGE_NAMES };
export default ProcessingStep;