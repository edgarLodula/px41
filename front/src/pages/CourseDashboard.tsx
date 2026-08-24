import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertCircle, BookOpen, Download, FileText, Loader2, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { BASE_URL, triggerBlobDownload } from "@/lib/api";
import styles from "./css/CourseDashboard.module.css";

interface Apostila {
  nome: string;
  data: string;
  status: "gerada" | "pendente" | string;
}

interface Curso {
  nome: string;
  pasta: string;
  apostilas: Apostila[];
}

const Header = () => (
  <header className={styles.header}>
    <div className={styles.headerInner}>
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
          px41 — Gerador de Apostilas e Vídeos com IA
        </p>
      </div>
    </div>
  </header>
);

const CourseDashboard = () => {
  const navigate = useNavigate();
  const goGerar = () => navigate("/gerar-conteudo");

  const [cursos, setCursos] = useState<Curso[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const fetchCursos = useCallback(() => {
    setLoading(true);
    setErro(null);
    fetch(`${BASE_URL}/cursos`)
      .then((res) => {
        if (!res.ok) throw new Error("Erro ao buscar cursos");
        return res.json();
      })
      .then((data) => setCursos(data.cursos ?? []))
      .catch((err) => setErro(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchCursos();
  }, [fetchCursos]);

  const handleDownload = async (nome: string) => {
    try {
      const res = await fetch(
        `${BASE_URL}/download/apostila/${encodeURIComponent(nome)}`
      );
      if (!res.ok) throw new Error(`Download falhou: ${res.status}`);
      const disposition = res.headers.get("content-disposition");
      const match = disposition?.match(/filename\*?=["']?(?:UTF-8'')?([^"';\r\n]+)/i);
      const filename = match?.[1] ? decodeURIComponent(match[1]) : nome;
      const blob = await res.blob();
      triggerBlobDownload(blob, filename);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className={styles.page}>
      <Header />

      <main className={styles.main}>
        <div className={styles.topRow}>
          <div>
            <h2 className={styles.pageTitle}>Cursos</h2>
            <p className={styles.pageDesc}>
              Gerencie os cursos e as apostilas geradas pela IA
            </p>
          </div>
          <Button size="lg" onClick={goGerar} className={styles.genButton}>
            <Plus className="w-5 h-5 mr-2" />
            Gerar Conteúdo
          </Button>
        </div>

        {loading && (
          <div className={styles.loadingWrap}>
            <Loader2 className="w-8 h-8 animate-spin mb-3" />
            <p className={styles.loadingText}>Carregando cursos...</p>
          </div>
        )}

        {!loading && erro && (
          <div className={styles.errorBox}>
            <AlertCircle className="w-10 h-10 text-destructive mb-3" />
            <p className={styles.errorTitle}>
              Não foi possível conectar ao servidor.
            </p>
            <p className={styles.errorDesc}>
              Verifique se o backend está rodando em localhost:8000.
            </p>
            <Button onClick={fetchCursos} variant="outline">
              Tentar novamente
            </Button>
          </div>
        )}

        {!loading && !erro && cursos.length === 0 && (
          <div className={styles.emptyWrap}>
            <BookOpen className="w-16 h-16 text-muted-foreground/50 mb-4" />
            <h3 className={styles.emptyTitle}>
              Nenhum curso criado ainda
            </h3>
            <p className={styles.emptyDesc}>
              Clique em "Gerar Conteúdo" para processar o primeiro PDF e criar
              apostilas.
            </p>
            <Button size="lg" onClick={goGerar}>
              <Plus className="w-5 h-5 mr-2" />
              Gerar Conteúdo
            </Button>
          </div>
        )}

        {!loading && !erro && cursos.length > 0 && (
          <div className={styles.coursesGrid}>
            {cursos.map((course) => (
              <div key={course.pasta} className={styles.courseCard}>
                <div className={styles.courseHeader}>
                  <div className={styles.courseIconBox}>
                    <BookOpen className="w-5 h-5 text-primary" />
                  </div>
                  <div className={styles.courseTitleBlock}>
                    <h3 className={styles.courseName}>
                      {course.nome}
                    </h3>
                    <p className={styles.courseCount}>
                      {course.apostilas.length} apostila(s)
                    </p>
                  </div>
                </div>

                <div className={styles.apostilaList}>
                  {course.apostilas.length === 0 ? (
                    <p className={styles.apostilaEmpty}>
                      Nenhuma apostila gerada ainda
                    </p>
                  ) : (
                    course.apostilas.map((a, i) => (
                      <div key={i} className={styles.apostilaRow}>
                        <FileText className="w-4 h-4 text-muted-foreground shrink-0" />
                        <div className={styles.apostilaInfo}>
                          <p className={styles.apostilaName}>{a.nome}</p>
                          <p className={styles.apostilaDate}>{a.data}</p>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          className={styles.downloadBtn}
                          onClick={() => handleDownload(a.nome)}
                        >
                          <Download className="w-3.5 h-3.5" />
                        </Button>
                      </div>
                    ))
                  )}
                </div>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={goGerar}
                  className={styles.footerBtn}
                >
                  <Plus className="w-4 h-4 mr-2" />
                  Gerar Conteúdo
                </Button>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
};

export default CourseDashboard;
