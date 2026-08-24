import { useCallback, useState } from "react";
import { Upload, FileText, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import styles from "./css/UploadStep.module.css";

interface UploadedFile {
  file: File;
  id: string;
}

interface UploadStepProps {
  onStart: (files: File[], instructions: string) => void;
}

const formatSize = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const UploadStep = ({ onStart }: UploadStepProps) => {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [instructions, setInstructions] = useState("");

  const addFiles = useCallback((newFiles: FileList | null) => {
    if (!newFiles) return;
    const pdfs = Array.from(newFiles).filter(f => f.type === "application/pdf");
    setFiles(prev => [
      ...prev,
      ...pdfs.map(f => ({ file: f, id: crypto.randomUUID() })),
    ]);
  }, []);

  const removeFile = (id: string) => setFiles(prev => prev.filter(f => f.id !== id));

  return (
    <div className={styles.wrap}>
      <div
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={e => { e.preventDefault(); setDragOver(false); addFiles(e.dataTransfer.files); }}
        className={cn(styles.dropzone, dragOver ? styles.dropzoneActive : styles.dropzoneInactive)}
        onClick={() => {
          const input = document.createElement("input");
          input.type = "file";
          input.multiple = true;
          input.accept = ".pdf";
          input.onchange = () => addFiles(input.files);
          input.click();
        }}
      >
        <Upload className="w-10 h-10 mx-auto mb-3 text-muted-foreground" />
        <p className={styles.dropzoneTitle}>Arraste PDFs aqui ou clique para selecionar</p>
        <p className={styles.dropzoneHint}>Apenas arquivos PDF</p>
      </div>

      {files.length > 0 && (
        <div className={styles.fileList}>
          {files.map(f => (
            <div key={f.id} className={styles.fileRow}>
              <FileText className="w-5 h-5 text-primary shrink-0" />
              <div className={styles.fileInfo}>
                <p className={styles.fileName}>{f.file.name}</p>
                <p className={styles.fileSize}>{formatSize(f.file.size)}</p>
              </div>
              <button onClick={() => removeFile(f.id)} className={styles.removeBtn}>
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className={styles.instructionsWrap}>
        <label className={styles.instructionsLabel}>
          Instruções de alteração (opcional)
        </label>
        <Textarea
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
          rows={4}
          className={styles.textarea}
          placeholder="Descreva o que deve ser modificado, ajustado ou destacado na geração do conteúdo. Ex: Adicionar mais exemplos práticos no módulo 2, remover referências desatualizadas, adaptar linguagem para nível básico..."
        />
      </div>

      <Button
        className={styles.submitButton}
        size="lg"
        disabled={files.length === 0}
        onClick={() => onStart(files.map(f => f.file), instructions)}
      >
        Iniciar pipeline
      </Button>
    </div>
  );
};

export default UploadStep;
