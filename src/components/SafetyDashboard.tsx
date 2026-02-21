import { motion } from 'framer-motion';
import {
  Shield, Info, AlertTriangle, Clock,
  Sun, Cloud, CloudRain, CloudDrizzle, CloudSnow,
  CloudLightning, CloudFog, Wind, Tornado, Thermometer,
  Car, Package, Flame, Home, Hammer, Wine,
  Skull, Crosshair, Ban, UserX, ShieldAlert,
  FileWarning, Banknote, Pill, AlertCircle, Bike,
} from 'lucide-react';
import type { SafetyData, WeatherInfo } from '@/types/safety';
import { useState } from 'react';
import type { LucideIcon } from 'lucide-react';

interface SafetyDashboardProps {
  data: SafetyData & { weather?: WeatherInfo };
  locationName: string;
}

const weatherIcons: Record<string, { Icon: LucideIcon; color: string }> = {
  Clear:        { Icon: Sun,            color: 'text-amber-400' },
  Clouds:       { Icon: Cloud,          color: 'text-slate-400' },
  Rain:         { Icon: CloudRain,      color: 'text-blue-400' },
  Drizzle:      { Icon: CloudDrizzle,   color: 'text-sky-400' },
  Thunderstorm: { Icon: CloudLightning, color: 'text-purple-400' },
  Snow:         { Icon: CloudSnow,      color: 'text-sky-300' },
  Mist:         { Icon: CloudFog,       color: 'text-gray-400' },
  Fog:          { Icon: CloudFog,       color: 'text-gray-400' },
  Haze:         { Icon: CloudFog,       color: 'text-yellow-400' },
  Smoke:        { Icon: Wind,           color: 'text-gray-500' },
  Dust:         { Icon: Wind,           color: 'text-orange-400' },
  Tornado:      { Icon: Tornado,        color: 'text-red-400' },
};

const fallbackWeatherIcon = { Icon: Thermometer, color: 'text-muted-foreground' };

interface IncidentStyle { Icon: LucideIcon; color: string; bg: string }

const incidentKeywords: Array<{ keywords: string[]; style: IncidentStyle }> = [
  { keywords: ['vehicle', 'auto theft', 'car theft', 'motor', 'carjack'],       style: { Icon: Car,         color: 'text-lumos-caution', bg: 'bg-amber-500/20' } },
  { keywords: ['theft', 'larceny', 'shoplift', 'stolen', 'pickpocket'],         style: { Icon: Package,     color: 'text-lumos-caution', bg: 'bg-amber-500/20' } },
  { keywords: ['burglary', 'break-in', 'breaking'],                             style: { Icon: Home,        color: 'text-amber-600',     bg: 'bg-amber-500/15' } },
  { keywords: ['robbery', 'armed robbery', 'mugging'],                          style: { Icon: Banknote,    color: 'text-lumos-danger',  bg: 'bg-red-500/20' } },
  { keywords: ['assault', 'battery', 'attack', 'fight'],                        style: { Icon: UserX,       color: 'text-lumos-danger',  bg: 'bg-red-500/20' } },
  { keywords: ['homicide', 'murder', 'manslaughter', 'killing'],                style: { Icon: Skull,       color: 'text-lumos-danger',  bg: 'bg-red-500/20' } },
  { keywords: ['sexual', 'rape', 'indecen'],                                    style: { Icon: ShieldAlert, color: 'text-lumos-danger',  bg: 'bg-red-500/20' } },
  { keywords: ['weapon', 'gun', 'firearm', 'shoot', 'stab', 'knife'],           style: { Icon: Crosshair,   color: 'text-lumos-danger',  bg: 'bg-red-500/20' } },
  { keywords: ['vandal', 'damage', 'graffiti', 'mischief', 'destruction'],      style: { Icon: Hammer,      color: 'text-primary',       bg: 'bg-primary/20' } },
  { keywords: ['drug', 'narcotic', 'substance', 'controlled'],                  style: { Icon: Pill,        color: 'text-primary',       bg: 'bg-primary/20' } },
  { keywords: ['fraud', 'forg', 'embezzle', 'identity', 'scam', 'counterfeit'], style: { Icon: FileWarning, color: 'text-lumos-caution', bg: 'bg-amber-500/20' } },
  { keywords: ['arson', 'fire'],                                                style: { Icon: Flame,       color: 'text-orange-500',    bg: 'bg-orange-500/20' } },
  { keywords: ['dui', 'dwi', 'drunk', 'impaired', 'alcohol'],                   style: { Icon: Wine,        color: 'text-primary',       bg: 'bg-primary/20' } },
  { keywords: ['trespass', 'prowl', 'loiter'],                                  style: { Icon: Ban,         color: 'text-lumos-caution', bg: 'bg-amber-500/20' } },
  { keywords: ['bicycle', 'bike'],                                              style: { Icon: Bike,        color: 'text-lumos-teal',    bg: 'bg-lumos-teal/20' } },
];

const defaultIncidentStyle: IncidentStyle = { Icon: AlertCircle, color: 'text-primary', bg: 'bg-primary/20' };

function getIncidentStyle(type: string): IncidentStyle {
  const lower = type.toLowerCase();
  for (const entry of incidentKeywords) {
    if (entry.keywords.some((kw) => lower.includes(kw))) return entry.style;
  }
  return defaultIncidentStyle;
}

const celsiusToF = (c: number) => Math.round(c * 9 / 5 + 32);

const WeatherBadge = ({ weather }: { weather: WeatherInfo }) => {
  const { Icon, color } = weatherIcons[weather.condition] ?? fallbackWeatherIcon;
  const desc = weather.description
    ? weather.description.charAt(0).toUpperCase() + weather.description.slice(1)
    : weather.condition;
  return (
    <div className="flex items-center gap-2 bg-secondary/60 rounded-lg px-3 py-1.5 shrink-0" title={desc}>
      <Icon className={`w-5 h-5 ${color}`} />
      {weather.temp_celsius != null && (
        <span className="text-sm font-semibold tabular-nums text-foreground">
          {celsiusToF(weather.temp_celsius)}°F
        </span>
      )}
    </div>
  );
};

const SafetyDashboard = ({ data, locationName }: SafetyDashboardProps) => {
  const [showSources, setShowSources] = useState(false);
  const [showAllIncidents, setShowAllIncidents] = useState(false);

  const getScoreColor = (score: number) => {
    if (score >= 70) return 'safe';
    if (score >= 40) return 'caution';
    return 'danger';
  };

  const scoreType = getScoreColor(data.safetyIndex);
  const gradientClass = `safety-gradient-${scoreType}`;
  const glowClass = `glow-${scoreType}`;

  const scoreLabels = {
    safe: 'Generally Safe',
    caution: 'Use Caution',
    danger: 'High Risk',
  };

  const visibleIncidents = showAllIncidents ? data.incidentTypes : data.incidentTypes.slice(0, 3);

  return (
    <motion.div
      initial={{ opacity: 0, x: 30 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5, ease: 'easeOut' }}
      className="space-y-3 w-full max-w-none md:max-w-sm"
    >
      {/* Combined: Location + Score + Time */}
      <div className={`glass-panel rounded-2xl p-4 sm:p-5 ${glowClass}`}>
        {/* Location row */}
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="min-w-0">
            <p className="text-[11px] text-muted-foreground uppercase tracking-wider">Analyzing</p>
            <h2 className="text-base font-display font-semibold text-foreground truncate">{locationName}</h2>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            {data.weather && data.weather.condition !== 'unknown' && (
              <WeatherBadge weather={data.weather} />
            )}
            <button
              onClick={() => setShowSources(!showSources)}
              className="p-1 rounded-md hover:bg-secondary transition-colors"
              title="View data sources"
              aria-label="Toggle data sources panel"
              aria-expanded={showSources}
            >
              <Info className="w-4 h-4 text-muted-foreground" />
            </button>
          </div>
        </div>

        {/* Score row */}
        <div className="flex items-center gap-3 mb-2">
          <div className={`text-4xl sm:text-5xl font-display font-bold leading-none ${scoreType === 'safe' ? 'text-lumos-safe' :
            scoreType === 'caution' ? 'text-lumos-caution' : 'text-lumos-danger'
          }`}>
            {data.safetyIndex}
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-1.5">
              <Shield className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">/100</span>
              <span className={`text-sm font-medium ml-auto ${scoreType === 'safe' ? 'text-lumos-safe' :
                scoreType === 'caution' ? 'text-lumos-caution' : 'text-lumos-danger'
              }`}>
                {scoreLabels[scoreType]}
              </span>
            </div>
            <div className="mt-2 h-2 bg-secondary rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${data.safetyIndex}%` }}
                transition={{ duration: 1, ease: 'easeOut', delay: 0.3 }}
                className={`h-full rounded-full ${gradientClass}`}
              />
            </div>
          </div>
        </div>

        {/* Time Analysis — inline */}
        <div className="grid grid-cols-2 gap-2 sm:gap-2.5 mt-3">
          <div className="bg-secondary/40 rounded-lg px-2.5 sm:px-3 py-2">
            <p className="text-[11px] text-muted-foreground">Peak Risk</p>
            <p className="text-sm font-medium text-foreground">{data.timeAnalysis.peakHours}</p>
          </div>
          <div className="bg-secondary/40 rounded-lg px-2.5 sm:px-3 py-2">
            <p className="text-[11px] text-muted-foreground">Safest Window</p>
            <p className="text-sm font-medium text-lumos-safe">{data.timeAnalysis.safestHours}</p>
          </div>
        </div>

        {/* Divider */}
        <div className="border-t border-border/50 my-3" />

        {/* Common Incidents — inline */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-primary" />
              <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Common Incidents</span>
            </div>
            {data.incidentTypes.length > 3 && (
              <button
                onClick={() => setShowAllIncidents(!showAllIncidents)}
                className="text-[10px] text-primary hover:underline"
              >
                {showAllIncidents ? 'Less' : `+${data.incidentTypes.length - 3}`}
              </button>
            )}
          </div>
          <div className="space-y-1.5">
            {visibleIncidents.map((incident) => {
              const style = getIncidentStyle(incident.type);
              const IncIcon = style.Icon;
              return (
                <div key={incident.type} className="flex items-center gap-2.5">
                  <div className="w-7 h-7 rounded-lg bg-primary/15 flex items-center justify-center shrink-0">
                    <IncIcon className="w-3.5 h-3.5 text-primary" />
                  </div>
                  <span className="text-xs text-foreground truncate flex-1">
                    {incident.type}
                  </span>
                  <span className="text-[11px] text-muted-foreground tabular-nums w-8 text-right shrink-0">
                    {Math.round(incident.probability * 100)}%
                  </span>
                  <div className="w-16 h-1.5 bg-secondary rounded-full overflow-hidden shrink-0">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${incident.probability * 100}%` }}
                      transition={{ duration: 0.8, delay: 0.5 }}
                      className="h-full rounded-full bg-primary/70"
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Data Sources (expandable) */}
      {showSources && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="glass-panel rounded-2xl p-3 sm:p-4"
        >
          <p className="text-xs font-medium text-muted-foreground mb-2">Data Sources</p>
          {data.dataSources.map((source) => (
            <div key={source.name} className="flex justify-between py-1.5 border-b border-border last:border-0">
              <div>
                <p className="text-xs text-foreground">{source.name}</p>
                <p className="text-[10px] text-muted-foreground">{source.lastUpdated}</p>
              </div>
              <span className="text-[10px] text-muted-foreground">{(source.recordCount / 1000).toFixed(0)}K</span>
            </div>
          ))}
        </motion.div>
      )}
    </motion.div>
  );
};

export default SafetyDashboard;
