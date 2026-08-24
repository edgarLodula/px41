import { Check } from "lucide-react";
import { cn } from "@/lib/utils";
import styles from "./css/StepIndicator.module.css";

interface StepIndicatorProps {
  currentStep: number;
  steps: string[];
}

const StepIndicator = ({ currentStep, steps }: StepIndicatorProps) => (
  <div className={styles.wrap}>
    {steps.map((label, i) => {
      const stepNum = i + 1;
      const isActive = stepNum === currentStep;
      const isDone = stepNum < currentStep;
      return (
        <div key={i} className={styles.stepItem}>
          <div className={styles.stepCol}>
            <div
              className={cn(
                styles.circle,
                isDone ? styles.circleDone : isActive ? styles.circleActive : styles.circleInactive
              )}
            >
              {isDone ? <Check className="w-4 h-4" /> : stepNum}
            </div>
            <span className={cn(styles.label, isActive ? styles.labelActive : styles.labelInactive)}>
              {label}
            </span>
          </div>
          {i < steps.length - 1 && (
            <div
              className={cn(styles.connector, isDone ? styles.connectorDone : styles.connectorPending)}
            />
          )}
        </div>
      );
    })}
  </div>
);

export default StepIndicator;
