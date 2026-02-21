import { motion } from 'framer-motion';
import { Shield, AlertTriangle, Clock, Ruler, Navigation, ChevronRight } from 'lucide-react';
import type { RouteAnalysisData } from '@/types/safety';

interface RouteSafetyPanelProps {
  data: RouteAnalysisData;
  originName: string;
  destName: string;
  onStartWalk?: () => void;
}

const riskColors = {
  safe: { bg: 'bg-lumos-safe/10', text: 'text-lumos-safe', border: 'border-lumos-safe/30', bar: 'bg-lumos-safe' },
  caution: { bg: 'bg-lumos-caution/10', text: 'text-lumos-caution', border: 'border-lumos-caution/30', bar: 'bg-lumos-caution' },
  danger: { bg: 'bg-lumos-danger/10', text: 'text-lumos-danger', border: 'border-lumos-danger/30', bar: 'bg-lumos-danger' },
};

const RouteSafetyPanel = ({ data, originName, destName, onStartWalk }: RouteSafetyPanelProps) => {
  const colors = riskColors[data.riskLevel] || riskColors.caution;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="glass-panel rounded-2xl overflow-hidden"
    >
      {/* Header with overall score */}
      <div className="p-4 sm:p-5 space-y-3 sm:space-y-4">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">Route Safety</h3>
            <div className="flex items-baseline gap-2">
              <span className={`text-4xl font-bold tabular-nums ${colors.text}`}>
                {data.overallSafety}
              </span>
              <span className="text-sm text-muted-foreground">/100</span>
            </div>
          </div>
          <div className={`px-3 py-1.5 rounded-full text-xs font-semibold uppercase ${colors.bg} ${colors.text} border ${colors.border}`}>
            {data.riskLevel}
          </div>
        </div>

        {/* Score bar */}
        <div className="w-full h-2 bg-secondary rounded-full overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${data.overallSafety}%` }}
            transition={{ duration: 1, ease: 'easeOut' }}
            className={`h-full rounded-full ${colors.bar}`}
          />
        </div>

        {/* Route summary */}
        <div className="flex flex-wrap items-center gap-3 sm:gap-4 text-sm">
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Ruler className="w-3.5 h-3.5" />
            <span>{data.distance}</span>
          </div>
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Clock className="w-3.5 h-3.5" />
            <span>{data.duration}</span>
          </div>
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Shield className="w-3.5 h-3.5" />
            <span>{data.segments.length} segments</span>
          </div>
        </div>

        {/* Origin → Destination */}
        <div className="flex items-center gap-1.5 sm:gap-2 text-xs text-muted-foreground bg-secondary/30 rounded-xl p-2.5 sm:p-3">
          <div className="w-2 h-2 rounded-full bg-lumos-safe flex-shrink-0" />
          <span className="truncate flex-1">{originName}</span>
          <ChevronRight className="w-3 h-3 flex-shrink-0" />
          <span className="truncate flex-1 text-right">{destName}</span>
          <div className="w-2 h-2 rounded-full bg-lumos-danger flex-shrink-0" />
        </div>
      </div>

      {/* Warnings */}
      {data.warnings && data.warnings.length > 0 && (
        <div className="px-4 sm:px-5 pb-3 sm:pb-4 space-y-2">
          {data.warnings.map((warning, i) => (
            <div
              key={i}
              className="flex items-start gap-2 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs"
            >
              <AlertTriangle className="w-3.5 h-3.5 text-lumos-caution mt-0.5 flex-shrink-0" />
              <span className="text-foreground">{warning}</span>
            </div>
          ))}
        </div>
      )}

      {/* Segment breakdown */}
      <div className="px-4 sm:px-5 pb-3 sm:pb-4">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">Segment Breakdown</p>
        <div className="flex gap-0.5 h-3 rounded-full overflow-hidden">
          {data.segments.map((seg, i) => {
            const segColor = riskColors[seg.riskLevel] || riskColors.caution;
            return (
              <motion.div
                key={i}
                initial={{ scaleX: 0 }}
                animate={{ scaleX: 1 }}
                transition={{ delay: i * 0.05, duration: 0.3 }}
                className={`flex-1 ${segColor.bar} first:rounded-l-full last:rounded-r-full`}
                title={`Segment ${i + 1}: ${seg.safetyScore}/100 (${seg.riskLevel})`}
              />
            );
          })}
        </div>
        <div className="flex justify-between text-[10px] text-muted-foreground mt-1">
          <span>Start</span>
          <span>End</span>
        </div>
      </div>

      {/* Start walk button */}
      {onStartWalk && (
        <div className="px-4 sm:px-5 pb-4 sm:pb-5">
          <button
            onClick={onStartWalk}
            className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-primary text-primary-foreground font-medium text-sm hover:opacity-90 transition-opacity"
          >
            <Navigation className="w-4 h-4" />
            Start Walk Tracking
          </button>
        </div>
      )}
    </motion.div>
  );
};

export default RouteSafetyPanel;
