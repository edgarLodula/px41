import { useEffect, useState } from "react";
import { Download, Loader2, RefreshCw, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { BASE_URL, downloadApostila, approve } from "@/lib/api";
import { cn } from "@/lib/utils";
import styles from "./css/ApprovalStep.module.css";

interface ApprovalStepProps {
  onApprove: () => void;
  onReject: () => void;
}

const ApprovalStep = ({ onApprove }: ApprovalStepProps) => {
  const [downloaded, setDownloaded] = useState(false);
  const [checked, setChecked] = useState(false);
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState("");
  const [redoing, setRedoing] = useState(false);
  const [redoError, setRedoError] = useState<string | null>(null);

  useEffect(() => {
    if (!redoing) return;

    let networkErrors = 0;

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${BASE_URL}/status`);
        const data = await res.json();
        networkErrors = 0;
        if (data.status === "awaiting_approval") {
          setRedoing(false);
          setDownloaded(false);
          setChecked(false);
        }
        if (data.status === "error") {
          setRedoing(false);
          setRedoError(data.error || "Erro ao refazer o conteúdo.");
        }
      } catch {
        networkErrors += 1;
        if (networkErrors >= 5) {
          setRedoing(false);
          setRedoError("Sem resposta do servidor. Verifique se o backend está rodando.");
        }
      }
    }, 3000);

    const timeout = setTimeout(() => {
      setRedoing(false);
      setRedoError("Tempo limite excedido aguardando o pipeline. Tente novamente.");
    }, 300_000);

    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, [redoing]);

  const handleDownload = async () => {
    try {
      await downloadApostila();
      setDownloaded(true);
    } catch {
      alert("Erro ao baixar a apostila. Tente novamente.");
    }
  };

  const handleApprove = async () => {
    setLoading(true);
    try {
      await approve();
      onApprove();
    } catch {
      alert("Erro ao aprovar. Tente novamente.");
    } finally {
      setLoading(false);
    }
  };

  const handleRedo = async () => {
    setRedoing(true);
    setRedoError(null);
    try {
      const res = await fetch(`${BASE_URL}/redo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ suggestions }),
      });
      if (!res.ok) throw new Error(`Redo falhou: ${res.status}`);
      // redoing permanece true; o polling aguarda awaiting_approval
    } catch {
      setRedoing(false);
      setRedoError("Erro ao refazer. Tente novamente.");
    }
  };

  return (
    <div className={styles.wrap}>
      <div className={styles.card}>
        <div className={styles.headerRow}>
          <div className={styles.iconBox}>
            <ShieldCheck className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h2 className={styles.title}>Content Approval</h2>
            <p className={styles.desc}>
              Review and approve the generated content before script creation.
            </p>
          </div>
        </div>

        <div className={styles.infoBox}>
          <p className={styles.infoLabel}>Disciplina</p>
          <p className={styles.infoValue}>Curso Técnico San Marino</p>
        </div>

        <Button
          className={styles.fullWidth}
          size="lg"
          onClick={handleDownload}
          variant={downloaded ? "outline" : "default"}
          disabled={redoing || loading}
        >
          <Download className="w-4 h-4 mr-2" />
          {downloaded ? "Baixar novamente" : "Baixar apostila"}
        </Button>

        {!downloaded && !redoing && (
          <p className={styles.hint}>
            Baixe e leia a apostila antes de aprovar
          </p>
        )}

        {redoing && (
          <p className={styles.hint}>
            Aguardando conclusão do pipeline…
          </p>
        )}

        <div className={styles.checkboxRow}>
          <Checkbox
            id="reviewed"
            disabled={!downloaded || redoing || loading}
            checked={checked}
            onCheckedChange={v => setChecked(v === true)}
            className={styles.checkboxOffset}
          />
          <label
            htmlFor="reviewed"
            className={cn(styles.label, downloaded && !redoing ? styles.labelActive : styles.labelInactive)}
          >
            Li e revisei o documento gerado
          </label>
        </div>

        <Button
          className={styles.fullWidth}
          size="lg"
          disabled={!checked || loading || redoing}
          onClick={handleApprove}
        >
          {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
          Aprovar e gerar vídeo
        </Button>

        <div className={styles.textareaSection}>
          <textarea
            placeholder="Descreva as alterações desejadas..."
            value={suggestions}
            onChange={e => setSuggestions(e.target.value)}
            disabled={redoing || loading}
            rows={3}
            className={styles.textarea}
          />

          <Button
            variant="outline"
            className={styles.redoButton}
            size="lg"
            disabled={redoing || loading}
            onClick={handleRedo}
          >
            {redoing ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Gerando...
              </>
            ) : (
              <>
                <RefreshCw className="w-4 h-4 mr-2" />
                Refazer com sugestões
              </>
            )}
          </Button>

          {redoError && (
            <p className={styles.redoError}>{redoError}</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default ApprovalStep;
