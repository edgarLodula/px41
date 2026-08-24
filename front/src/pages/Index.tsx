import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import StepIndicator from "@/components/StepIndicator";
import UploadStep from "@/components/UploadStep";
import ProcessingStep, { PipelineStage, STAGE_NAMES } from "@/components/ProcessingStep";
import ApprovalStep from "@/components/ApprovalStep";
import ScriptApprovalStep from "@/components/ScriptApprovalStep";
import VideoStep from "@/components/VideoStep";
import { uploadPDFs } from "@/lib/api";
import styles from "./css/Index.module.css";

const STEPS = ["Upload", "Processing", "Content Approval", "Script Approval", "Videos Ready"];

const makeStages = (): PipelineStage[] =>
  STAGE_NAMES.map(name => ({ name, status: "waiting" as const }));

const Index = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [stages, setStages] = useState<PipelineStage[]>(makeStages);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const reset = () => {
    setStep(1);
    setStages(makeStages());
    setUploadError(null);
  };

  const handleStart = async (files: File[], instructions: string) => {
    setUploadError(null);
    try {
      await uploadPDFs(files, instructions);
      setStep(2);
    } catch (err) {
      setUploadError("Erro ao enviar os PDFs. Verifique se o backend está rodando em localhost:8000.");
    }
  };

  const handleStagesUpdate = useCallback((s: PipelineStage[]) => setStages(s), []);
  const handleProcessingComplete = useCallback(() => setStep(3), []);

  return (
    <div className={styles.page}>
      {/* Header */}
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/")}
            className={styles.backButton}
          >
            <ArrowLeft className="w-4 h-4 mr-1" />
            Cursos
          </Button>
          <div className={styles.logoBox}>
            <span className={styles.logoText}>
              SM
            </span>
          </div>
          <div className={styles.titleBlock}>
            <h1 className={styles.title}>
              Escola Técnica San Marino
            </h1>
            <p className={styles.subtitle}>
              px41 — Gerador de Apostilas
            </p>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className={styles.main}>
        <div className={styles.card}>
          {/* Stepper */}
          <div className={styles.stepperWrap}>
            <StepIndicator currentStep={step} steps={STEPS} />
          </div>

          {step === 1 && (
            <>
              <UploadStep onStart={handleStart} />
              {uploadError && (
                <p className={styles.uploadError}>{uploadError}</p>
              )}
            </>
          )}
          {step === 2 && (
            <ProcessingStep
              stages={stages}
              onStagesUpdate={handleStagesUpdate}
              onComplete={handleProcessingComplete}
            />
          )}
          {step === 3 && (
            <ApprovalStep
              onApprove={() => setStep(4)}
              onReject={reset}
            />
          )}
          {step === 4 && (
            <ScriptApprovalStep
              onApprove={() => setStep(5)}
              onRequestChanges={() => setStep(3)}
            />
          )}
          {step === 5 && <VideoStep onRestart={reset} />}
        </div>
      </main>
    </div>
  );
};

export default Index;