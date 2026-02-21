import { motion } from 'framer-motion';

interface HeatmapLegendProps {
  visible: boolean;
  inline?: boolean;
  showCitizen?: boolean;
  incidentCount?: number;
  radiusMiles?: number;
  locationName?: string;
  mode?: 'density' | 'hotspots';
}

export default function HeatmapLegend({ visible, inline = false, showCitizen, incidentCount, radiusMiles = 3, locationName, mode = 'density' }: HeatmapLegendProps) {
  if (!visible) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 10 }}
      className={inline ? 'glass-panel px-3 sm:px-3.5 py-2 sm:py-2.5 rounded-xl' : 'absolute bottom-6 right-4 sm:right-6 z-20 glass-panel px-3 sm:px-3.5 py-2 sm:py-2.5 rounded-xl pointer-events-auto max-w-[calc(100vw-2rem)] sm:max-w-[280px]'}
    >
      <div className="flex items-center gap-2.5">
        <span className="text-[11px] font-semibold text-foreground whitespace-nowrap shrink-0">
          {mode === 'hotspots' ? 'Hotspots' : 'Density'}
        </span>
        <span className="text-[10px] uppercase text-muted-foreground shrink-0">Low</span>
        <div className="flex-1 h-2 rounded-full bg-gradient-to-r from-emerald-500/60 via-amber-500/80 to-red-500 opacity-80 min-w-[60px]" />
        <span className="text-[10px] uppercase text-muted-foreground shrink-0">High</span>
        {incidentCount != null && incidentCount > 0 && (
          <span className="text-[11px] text-muted-foreground whitespace-nowrap shrink-0">
            <strong className="text-foreground">{incidentCount.toLocaleString()}</strong> incidents
          </span>
        )}
      </div>
      {showCitizen && (
        <div className="flex items-center gap-2.5 mt-2">
          <span className="text-[11px] font-semibold text-foreground whitespace-nowrap shrink-0">Live</span>
          <span className="text-[10px] uppercase text-muted-foreground shrink-0">Low</span>
          <div className="flex-1 h-2 rounded-full bg-gradient-to-r from-purple-400 via-fuchsia-500 to-rose-500 opacity-80 min-w-[60px]" />
          <span className="text-[10px] uppercase text-muted-foreground shrink-0">High</span>
        </div>
      )}
    </motion.div>
  );
}
