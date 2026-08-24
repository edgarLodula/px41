import { useEffect, useRef, useState } from "react";
import { Download, RotateCcw, Play, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { getStatus, listVideos, downloadVideoByName } from "@/lib/api";
import { cn } from "@/lib/utils";
import styles from "./css/VideoStep.module.css";

interface VideoStepProps {
  onRestart: () => void;
}

const formatTitle = (name: string) => name.replace(/_/g, " ");

const VideoStep = ({ onRestart }: VideoStepProps) => {
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [videos, setVideos] = useState<string[]>([]);
  const [loadingList, setLoadingList] = useState(false);
  const [downloading, setDownloading] = useState<string | null>(null);
  const progressRef = useRef(0);

  useEffect(() => {
    const anim = setInterval(() => {
      if (progressRef.current < 90) {
        progressRef.current += 2;
        setProgress(progressRef.current);
      }
    }, 1000);

    const finish = async () => {
      clearInterval(anim);
      clearInterval(poll);
      clearTimeout(timeout);
      setProgress(100);
      setLoadingList(true);
      try {
        const list = await listVideos();
        setVideos(list);
      } catch (err) {
        console.warn("Falha ao listar vídeos:", err);
        setVideos([]);
      } finally {
        setLoadingList(false);
        setDone(true);
      }
    };

    const poll = setInterval(async () => {
      try {
        const data = await getStatus();
        if (data.status === "done") {
          await finish();
        }
        if (data.status === "error") {
          clearInterval(anim);
          clearInterval(poll);
          clearTimeout(timeout);
          setError(data.error || "Erro na geração do vídeo");
        }
      } catch (err) {
        console.error("Erro no polling de vídeo:", err);
      }
    }, 3000);

    const timeout = setTimeout(() => {
      clearInterval(anim);
      clearInterval(poll);
      setError("Tempo limite excedido aguardando o backend. Verifique os logs e tente novamente.");
    }, 600_000);

    return () => {
      clearInterval(anim);
      clearInterval(poll);
      clearTimeout(timeout);
    };
  }, []);

  const handleDownload = async (nome: string) => {
    setDownloading(nome);
    try {
      await downloadVideoByName(nome);
    } catch (err) {
      console.warn(`Falha no download de ${nome}:`, err);
    } finally {
      setDownloading(null);
    }
  };

  if (error) {
    return (
      <div className={styles.centerWrap}>
        <p className={styles.errorTitle}>Erro na geração do vídeo</p>
        <p className={styles.errorDesc}>{error}</p>
        <Button variant="outline" className={styles.outlineFullBtn} size="lg" onClick={onRestart}>
          <RotateCcw className="w-4 h-4 mr-2" />
          Reiniciar
        </Button>
      </div>
    );
  }

  if (!done) {
    return (
      <div className={styles.centerWrap}>
        <p className={styles.statusTitle}>Gerando vídeo-aulas…</p>
        <Progress value={progress} className={styles.progressBar} />
        <p className={styles.percentText}>{progress}%</p>
      </div>
    );
  }

  return (
    <div className={styles.readyWrap}>
      <div className={styles.readyHeader}>
        <p className={styles.readyTitle}>Vídeos prontos!</p>
        <p className={styles.readySub}>
          Faça o download dos arquivos MP4 abaixo
        </p>
      </div>

      {loadingList ? (
        <div className={styles.loadingList}>
          <Loader2 className="w-5 h-5 mr-2 animate-spin" />
          Carregando lista de vídeos…
        </div>
      ) : videos.length === 0 ? (
        <p className={styles.noVideos}>
          Nenhum vídeo disponível.
        </p>
      ) : (
        <div className={styles.videoGrid}>
          {videos.map((nome) => (
            <div key={nome} className={styles.videoCard}>
              <h3 className={styles.videoTitle}>
                {formatTitle(nome)}
              </h3>
              <div className={styles.videoBox}>
                <div className={cn(styles.thumbnail, "group")}>
                  <div className={styles.playCircle}>
                    <Play className="w-6 h-6 text-primary-foreground ml-0.5" fill="currentColor" />
                  </div>
                </div>
                <div className={styles.videoFooter}>
                  <Button
                    className={styles.fullWidth}
                    size="sm"
                    onClick={() => handleDownload(nome)}
                    disabled={downloading === nome}
                  >
                    {downloading === nome ? (
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    ) : (
                      <Download className="w-4 h-4 mr-2" />
                    )}
                    Download MP4
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className={styles.bottomWrap}>
        <Button variant="outline" className={styles.outlineFullBtn} size="lg" onClick={onRestart}>
          <RotateCcw className="w-4 h-4 mr-2" />
          Nova disciplina
        </Button>
      </div>
    </div>
  );
};

export default VideoStep;
