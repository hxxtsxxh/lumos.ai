import { motion, AnimatePresence } from 'framer-motion';
import { Hospital, Shield, Flame, Navigation } from 'lucide-react';
import type { NearbyPOI } from '@/types/safety';

interface NearbyPOIsProps {
  pois: NearbyPOI[];
  loading?: boolean;
  expanded?: boolean;
  /** When provided, clicking a place name/row flies the map to that location */
  onSelectPOI?: (poi: NearbyPOI) => void;
}

const typeConfig: Record<string, { icon: React.ElementType; color: string; label: string }> = {
  police: { icon: Shield, color: 'text-blue-600 dark:text-blue-400', label: 'Police Station' },
  hospital: { icon: Hospital, color: 'text-lumos-safe', label: 'Hospital' },
  fire_station: { icon: Flame, color: 'text-orange-600 dark:text-orange-400', label: 'Fire Station' },
};

const NearbyPOIs = ({ pois, loading, expanded: externalExpanded, onSelectPOI }: NearbyPOIsProps) => {
  const expanded = externalExpanded ?? false;

  if (!pois.length && !loading) return null;

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
              {loading ? (
                [1, 2, 3].map((i) => (
                  <div key={i} className="h-14 bg-secondary/50 rounded-xl animate-pulse" />
                ))
              ) : (
                pois.map((poi, i) => {
                  const config = typeConfig[poi.type] || typeConfig.police;
                  const Icon = config.icon;
                  const handleClick = () => onSelectPOI?.(poi);
                  return (
                    <motion.button
                      key={i}
                      type="button"
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.05 }}
                      onClick={handleClick}
                      className={`w-full flex items-center gap-2.5 sm:gap-3 p-2.5 sm:p-3 rounded-xl bg-secondary/30 border border-border/50 text-left transition-colors min-h-[48px] ${onSelectPOI ? 'hover:bg-secondary/50 active:bg-secondary/60 hover:border-border cursor-pointer' : ''}`}
                      aria-label={`Focus map on ${poi.name}`}
                    >
                      <div className={`p-2 rounded-lg bg-secondary ${config.color}`}>
                        <Icon className="w-4 h-4" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-foreground truncate">{poi.name}</p>
                        <p className="text-xs text-muted-foreground truncate">{poi.address}</p>
                      </div>
                      <div className="flex items-center gap-1 text-xs text-muted-foreground flex-shrink-0">
                        <Navigation className="w-3 h-3" />
                        {poi.distance < 1000
                          ? `${Math.round(poi.distance)}m`
                          : `${(poi.distance / 1000).toFixed(1)}km`}
                      </div>
                    </motion.button>
                  );
                })
              )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default NearbyPOIs;
