import { useMemo, useState } from "react";
import { ChevronDown, ChevronUp, Check, Pencil, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import styles from "./css/ScriptApprovalStep.module.css";

interface ScriptApprovalStepProps {
  onApprove: () => void;
  onRequestChanges: () => void;
}

type Status = "pending" | "approved" | "changes";

const DISCIPLINES = [
  "Administração de Unidades de Enfermagem",
  "Anatomia e Fisiologia I",
  "Anatomia e Fisiologia II",
  "Anatomia Masculina",
  "Componentes",
  "Enfermagem Materno Infantil",
];

const buildMockScript = (name: string) => `# Roteiro: ${name}

## Introdução
Olá, futuros profissionais da saúde! Sejam bem-vindos a mais uma aula do curso técnico da Escola San Marino. Hoje vamos estudar ${name}, um conteúdo essencial para a sua formação prática e teórica.

Antes de iniciarmos, lembre-se: o aprendizado em enfermagem exige atenção aos detalhes, raciocínio clínico e empatia com o paciente. Tenha em mãos seu caderno de anotações.

## Desenvolvimento

### 1. Fundamentos
Nesta primeira parte, vamos compreender os conceitos centrais que sustentam o estudo de ${name}. Esses fundamentos servirão de base para todas as próximas etapas do conteúdo.

- Definição e importância clínica
- Aplicações no cotidiano hospitalar
- Relações com outras disciplinas do curso

### 2. Aprofundamento Teórico
Aqui exploramos os mecanismos, estruturas e processos relacionados ao tema. Cada item será apresentado com exemplos práticos e situações reais da rotina de enfermagem.

A teoria sempre dialoga com a prática — observe como cada conceito se manifesta na atuação diária do profissional técnico de enfermagem.

### 3. Aplicação Prática
Vamos analisar casos clínicos simulados para fixar o conteúdo:
- Caso 1: avaliação inicial do paciente
- Caso 2: intervenção e cuidados específicos
- Caso 3: registros e comunicação com a equipe multidisciplinar

## Conclusão
Concluímos aqui nosso estudo sobre ${name}. Revise as anotações, refaça os exercícios propostos e consulte sempre o material complementar disponível na plataforma.

Lembre-se: o conhecimento técnico, somado ao cuidado humano, é o que diferencia um excelente profissional de enfermagem. Até a próxima aula!`;

const StatusBadge = ({ status }: { status: Status }) => {
  const map = {
    pending: { label: "Pendente", cls: styles.badgePending },
    approved: { label: "Aprovado", cls: styles.badgeApproved },
    changes: { label: "Alteração solicitada", cls: styles.badgeChanges },
  } as const;
  const { label, cls } = map[status];
  return (
    <span className={cn(styles.badge, cls)}>
      {label}
    </span>
  );
};

const ScriptApprovalStep = ({ onApprove, onRequestChanges }: ScriptApprovalStepProps) => {
  const [statuses, setStatuses] = useState<Record<string, Status>>(
    () => Object.fromEntries(DISCIPLINES.map(d => [d, "pending"])) as Record<string, Status>
  );
  const [expanded, setExpanded] = useState<string | null>(DISCIPLINES[0]);

  const approvedCount = useMemo(
    () => Object.values(statuses).filter(s => s === "approved").length,
    [statuses]
  );
  const total = DISCIPLINES.length;
  const allApproved = approvedCount === total;

  const setStatus = (name: string, status: Status) =>
    setStatuses(prev => ({ ...prev, [name]: status }));

  return (
    <div className={styles.wrap}>
      <div className={styles.card}>
        <div className={styles.headerRow}>
          <div className={styles.iconBox}>
            <FileText className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h2 className={styles.title}>Script Approval</h2>
            <p className={styles.desc}>
              Revise e aprove o roteiro de cada disciplina antes da geração dos vídeos
            </p>
          </div>
        </div>

        <div className={styles.list}>
          {DISCIPLINES.map(name => {
            const status = statuses[name];
            const isOpen = expanded === name;
            return (
              <div
                key={name}
                className={cn(styles.item, isOpen ? styles.itemOpen : styles.itemClosed)}
              >
                <button
                  type="button"
                  onClick={() => setExpanded(isOpen ? null : name)}
                  className={styles.itemHeader}
                >
                  <div className={styles.itemLeft}>
                    <span className={styles.itemName}>
                      {name}
                    </span>
                    <StatusBadge status={status} />
                  </div>
                  {isOpen ? (
                    <ChevronUp className={styles.chevron} />
                  ) : (
                    <ChevronDown className={styles.chevron} />
                  )}
                </button>

                {isOpen && (
                  <div className={styles.itemBody}>
                    <div className={styles.scriptBox}>
                      {buildMockScript(name)}
                    </div>
                    <div className={styles.actions}>
                      <Button
                        size="sm"
                        onClick={() => setStatus(name, "approved")}
                        disabled={status === "approved"}
                      >
                        <Check className="w-4 h-4 mr-1.5" />
                        Aprovar Roteiro
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className={styles.outlineBtn}
                        onClick={() => setStatus(name, "changes")}
                      >
                        <Pencil className="w-4 h-4 mr-1.5" />
                        Solicitar Alteração
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div className={styles.footer}>
          <p className={styles.countText}>
            <span className={styles.countBold}>{approvedCount}</span> de{" "}
            <span className={styles.countBold}>{total}</span> roteiros aprovados
          </p>

          <Button
            className={styles.fullWidth}
            size="lg"
            disabled={!allApproved}
            onClick={onApprove}
          >
            Aprovar Todos e Gerar Vídeos
          </Button>

          <button
            type="button"
            onClick={onRequestChanges}
            className={styles.rejectBtn}
          >
            Reprovar Tudo e Resetar
          </button>
        </div>
      </div>
    </div>
  );
};

export default ScriptApprovalStep;
