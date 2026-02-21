import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ShieldAlert, ShieldCheck, Shield } from 'lucide-react';
import { generateSafetyTips, type AISafetyTip, type EnrichedTipsContext } from '@/lib/gemini';
import type { SafetyData, TravelParams, LiveIncident, NearbyPOI } from '@/types/safety';

interface AISafetyTipsProps {
  data: SafetyData;
  locationName: string;
  params: TravelParams;
  expanded?: boolean;
  liveIncidents?: LiveIncident[];
  nearbyPOIs?: NearbyPOI[];
  neighborhoodContext?: string;
  sentimentSummary?: string;
}

const priorityConfig = {
  high: { icon: ShieldAlert, color: 'text-lumos-danger', bg: 'bg-red-500/10', border: 'border-red-500/20' },
  medium: { icon: Shield, color: 'text-lumos-caution', bg: 'bg-amber-500/10', border: 'border-amber-500/20' },
  low: { icon: ShieldCheck, color: 'text-lumos-safe', bg: 'bg-green-500/10', border: 'border-green-500/20' },
};

function buildLiveIncidentSummary(incidents: LiveIncident[]): string {
  if (!incidents || incidents.length === 0) return '';
  return incidents.slice(0, 8).map((inc) => {
    const parts = [inc.type];
    if (inc.distance_miles > 0) parts.push(`${inc.distance_miles.toFixed(1)}mi away`);
    if (inc.date) {
      try {
        const d = new Date(inc.date);
        const now = new Date();
        const hoursAgo = Math.round((now.getTime() - d.getTime()) / (1000 * 60 * 60));
        if (hoursAgo < 1) parts.push('just now');
        else if (hoursAgo < 24) parts.push(`${hoursAgo}h ago`);
        else parts.push(`${Math.round(hoursAgo / 24)}d ago`);
      } catch { /* skip */ }
    }
    if (inc.severity) parts.push(inc.severity);
    return parts.join(', ');
  }).join('; ');
}

const AISafetyTips = ({ data, locationName, params, expanded: externalExpanded, liveIncidents, nearbyPOIs, neighborhoodContext, sentimentSummary }: AISafetyTipsProps) => {
  const [tips, setTips] = useState<AISafetyTip[]>([]);
  const [loading, setLoading] = useState(true);
  const expanded = externalExpanded ?? false;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    const enriched: EnrichedTipsContext = {
      liveIncidentSummary: buildLiveIncidentSummary(liveIncidents ?? []),
      nearbyPOIs: nearbyPOIs?.map((p) => `${p.name} (${p.type}, ${(p.distance / 1609.34).toFixed(1)}mi)`) ?? [],
      neighborhoodContext: neighborhoodContext ?? '',
      sentimentSummary: sentimentSummary ?? '',
    };

    generateSafetyTips(
      locationName,
      data.safetyIndex,
      data.incidentTypes.map((i) => i.type),
      params.timeOfTravel,
      params.peopleCount,
      params.gender,
      enriched
    ).then((result) => {
      if (!cancelled) {
        setTips(result);
        setLoading(false);
      }
    }).catch(() => {
      if (!cancelled) setLoading(false);
    });

    return () => { cancelled = true; };
  }, [locationName, data.safetyIndex, params.timeOfTravel, params.peopleCount, params.gender, liveIncidents, nearbyPOIs, neighborhoodContext, sentimentSummary]);

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
          <div className="p-3 sm:p-4 space-y-2">
            {loading ? (
              <>
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-16 bg-secondary/50 rounded-xl animate-pulse" />
                ))}
              </>
            ) : (
              tips.map((tip, i) => {
                const config = priorityConfig[tip.priority];
                const Icon = config.icon;
                return (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.1 }}
                    className={`flex gap-2 sm:gap-2.5 p-2 sm:p-2.5 rounded-xl ${config.bg} border ${config.border}`}
                  >
                    <Icon className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${config.color}`} />
                    <div>
                      <p className="text-xs font-medium text-foreground">{tip.title}</p>
                      <p className="text-[11px] text-muted-foreground mt-0.5 leading-relaxed">
                        {tip.description}
                      </p>
                    </div>
                  </motion.div>
                );
              })
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default AISafetyTips;
