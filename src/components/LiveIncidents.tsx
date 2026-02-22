import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Radio, Clock, AlertTriangle, Navigation, ChevronLeft, ChevronRight } from 'lucide-react';
import type { HeatmapPoint } from '@/lib/api';

const PAGE_SIZE = 7;

interface LiveIncidentsProps {
  incidents: HeatmapPoint[];
  expanded?: boolean;
  onSelectIncident?: (incident: HeatmapPoint) => void;
}

function timeAgo(ts: number): string {
  const diffMs = Date.now() - ts;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'Just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ${diffMin % 60}m ago`;
  return `${Math.floor(diffHr / 24)}d ago`;
}

function severityInfo(weight: number) {
  if (weight > 0.6) return { label: 'High', color: 'text-red-500 dark:text-red-400', bg: 'bg-red-500/15', border: 'border-red-500/30' };
  if (weight > 0.3) return { label: 'Moderate', color: 'text-amber-500 dark:text-amber-400', bg: 'bg-amber-500/15', border: 'border-amber-500/30' };
  return { label: 'Low', color: 'text-purple-500 dark:text-purple-400', bg: 'bg-purple-500/15', border: 'border-purple-500/30' };
}

const LiveIncidents = ({ incidents, expanded: externalExpanded, onSelectIncident }: LiveIncidentsProps) => {
  const expanded = externalExpanded ?? false;
  const [page, setPage] = useState(0);

  // Reset page when incidents change or panel closes/opens
  useEffect(() => { setPage(0); }, [incidents, expanded]);

  if (!incidents.length) return null;

  // Sort by most recent first
  const sorted = [...incidents].sort((a, b) => (b.ts ?? 0) - (a.ts ?? 0));
  const totalPages = Math.ceil(sorted.length / PAGE_SIZE);
  const pageIncidents = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const start = page * PAGE_SIZE + 1;
  const end = Math.min((page + 1) * PAGE_SIZE, sorted.length);

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
          <div className="p-3 sm:p-4 space-y-1.5">
            <div className="flex items-center gap-2 mb-2">
              <Radio className="w-4 h-4 text-purple-400" />
              <span className="text-xs font-medium text-muted-foreground">
                {incidents.length} live incident{incidents.length !== 1 ? 's' : ''} nearby
              </span>
              <span className="ml-auto flex items-center gap-1 text-[10px] text-muted-foreground/70">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                Real-time
              </span>
            </div>
            {pageIncidents.map((incident, i) => {
              const sev = severityInfo(incident.weight);
              const handleClick = () => onSelectIncident?.(incident);
              return (
                <motion.button
                  key={`${incident.lat}-${incident.lng}-${page}-${i}`}
                  type="button"
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.03 }}
                  onClick={handleClick}
                  className={`w-full flex items-center gap-2.5 sm:gap-3 p-2.5 sm:p-3 rounded-xl bg-secondary/30 border border-border/50 text-left transition-colors min-h-[48px] ${onSelectIncident ? 'hover:bg-secondary/50 active:bg-secondary/60 hover:border-border cursor-pointer' : ''}`}
                  aria-label={`Focus map on ${incident.type ?? 'incident'}`}
                >
                  <div className={`p-2 rounded-lg ${sev.bg} ${sev.color} flex-shrink-0`}>
                    <AlertTriangle className="w-4 h-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">
                      {incident.type || 'Unknown Incident'}
                    </p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className={`text-[10px] sm:text-xs font-medium ${sev.color}`}>
                        {sev.label}
                      </span>
                      {incident.ts ? (
                        <span className="flex items-center gap-0.5 text-[10px] sm:text-xs text-muted-foreground">
                          <Clock className="w-3 h-3" />
                          {timeAgo(incident.ts)}
                        </span>
                      ) : null}
                    </div>
                  </div>
                  {onSelectIncident && (
                    <Navigation className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                  )}
                </motion.button>
              );
            })}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 pt-2 pb-14 sm:pb-0 border-t border-border/30">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed transition-colors px-2 py-1 rounded-lg hover:bg-secondary/50"
                  aria-label="Previous page"
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                  Prev
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                  disabled={page >= totalPages - 1}
                  className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed transition-colors px-2 py-1 rounded-lg hover:bg-secondary/50"
                  aria-label="Next page"
                >
                  Next
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
                <span className="text-[10px] sm:text-xs text-muted-foreground tabular-nums">
                  {start}–{end} of {sorted.length}
                </span>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default LiveIncidents;
