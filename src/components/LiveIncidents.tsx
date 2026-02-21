import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Radio, AlertTriangle, CloudLightning, ChevronDown, ChevronUp } from 'lucide-react';
import type { LiveIncident } from '@/types/safety';

interface LiveIncidentsProps {
  incidents: LiveIncident[];
  expanded?: boolean;
}

function formatRelativeDate(dateStr: string): string {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMin = Math.round(diffMs / 60000);
    if (diffMin < 1) return 'Just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHr = Math.round(diffMin / 60);
    if (diffHr < 24) return `${diffHr}h ago`;
    const diffDays = Math.round(diffHr / 24);
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return dateStr;
  }
}

const severityConfig: Record<string, { color: string; bg: string }> = {
  extreme: { color: 'text-red-500', bg: 'bg-red-500/15' },
  severe: { color: 'text-red-400', bg: 'bg-red-500/10' },
  moderate: { color: 'text-amber-500', bg: 'bg-amber-500/10' },
  minor: { color: 'text-green-500', bg: 'bg-green-500/10' },
};

function getSeverityConfig(severity: string) {
  const key = severity.toLowerCase();
  return severityConfig[key] ?? { color: 'text-muted-foreground', bg: 'bg-secondary/50' };
}

const LiveIncidents = ({ incidents, expanded: externalExpanded }: LiveIncidentsProps) => {
  const [showAll, setShowAll] = useState(false);
  const expanded = externalExpanded ?? true;

  if (!incidents || incidents.length === 0) return null;

  const sorted = [...incidents].sort((a, b) => {
    if (a.date && b.date) return b.date.localeCompare(a.date);
    return 0;
  });

  const displayed = showAll ? sorted : sorted.slice(0, 4);

  return (
    <AnimatePresence>
      {expanded && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.3, ease: 'easeInOut' }}
          className="overflow-hidden glass-panel rounded-2xl"
        >
          <div className="p-3 sm:p-4">
            <div className="flex items-center gap-2 mb-2">
              <Radio className="w-3.5 h-3.5 text-primary animate-pulse" />
              <h3 className="text-xs font-semibold text-foreground">
                Live Incidents ({incidents.length})
              </h3>
              <span className="text-[10px] text-muted-foreground">Last 48h</span>
            </div>

            <div className="space-y-1.5">
              {displayed.map((inc, i) => {
                const isWeather = inc.source === 'nws_alerts';
                const Icon = isWeather ? CloudLightning : AlertTriangle;
                const sevConfig = getSeverityConfig(inc.severity);
                const relDate = formatRelativeDate(inc.date);

                return (
                  <motion.div
                    key={`${inc.type}-${inc.date}-${i}`}
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.05 }}
                    className={`flex items-start gap-2 p-2 rounded-xl ${sevConfig.bg} border border-border/30`}
                  >
                    <Icon className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${sevConfig.color}`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <p className="text-[11px] font-medium text-foreground truncate">
                          {inc.headline || inc.type}
                        </p>
                        {inc.severity && (
                          <span className={`text-[9px] font-medium ${sevConfig.color} flex-shrink-0`}>
                            {inc.severity}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        {relDate && (
                          <span className="text-[10px] text-muted-foreground">{relDate}</span>
                        )}
                        {inc.distance_miles > 0 && (
                          <span className="text-[10px] text-muted-foreground">
                            {inc.distance_miles.toFixed(1)} mi
                          </span>
                        )}
                        {inc.source && (
                          <span className="text-[9px] text-muted-foreground/60 truncate">
                            {inc.source.replace('socrata_', '').replace('nws_alerts', 'NWS')}
                          </span>
                        )}
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </div>

            {sorted.length > 4 && (
              <button
                onClick={() => setShowAll(!showAll)}
                className="flex items-center gap-1 mt-2 text-[10px] text-primary hover:text-primary/80 transition-colors mx-auto"
              >
                {showAll ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                {showAll ? 'Show less' : `Show all ${sorted.length} incidents`}
              </button>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default LiveIncidents;
