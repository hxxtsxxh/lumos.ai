import { motion, AnimatePresence } from 'framer-motion';
import { Phone, Building, Hospital, ShieldCheck } from 'lucide-react';
import type { EmergencyNumber } from '@/lib/api';

interface EmergencyResourcesProps {
  locationName: string;
  numbers?: EmergencyNumber[];
  expanded?: boolean;
  onCall911?: () => void;
}

const iconMap: Record<string, React.ElementType> = {
  phone: Phone,
  shield: ShieldCheck,
  hospital: Hospital,
  building: Building,
};

const colorMap: Record<string, string> = {
  danger: 'text-lumos-danger',
  caution: 'text-lumos-caution',
  safe: 'text-lumos-safe',
  primary: 'text-primary',
};

const EmergencyResources = ({ locationName, numbers, expanded: externalExpanded, onCall911 }: EmergencyResourcesProps) => {
  const expanded = externalExpanded ?? false;
  const resources = numbers && numbers.length > 0
    ? numbers.map((n) => ({
        label: n.label,
        number: n.number,
        icon: iconMap[n.icon] || Phone,
        color: colorMap[n.color] || 'text-primary',
      }))
    : [
        { label: 'Emergency', number: '911', icon: Phone, color: 'text-lumos-danger' },
        { label: 'Non-Emergency Police', number: '311', icon: ShieldCheck, color: 'text-lumos-caution' },
        { label: 'Crisis Hotline', number: '988', icon: Hospital, color: 'text-lumos-safe' },
        { label: 'Domestic Violence', number: '1-800-799-7233', icon: Building, color: 'text-primary' },
      ];
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
            <div className="grid grid-cols-2 gap-1.5">
                {resources.map((r) => {
                  const is911 = r.number === '911';

                  if (is911 && onCall911) {
                    return (
                      <button
                        key={r.number}
                        onClick={onCall911}
                        className="flex items-center gap-1.5 bg-red-500/20 border border-red-500/40 rounded-lg px-2 sm:px-2.5 py-2 sm:py-2.5 hover:bg-red-500/30 active:bg-red-500/40 transition-colors group min-h-[44px] text-left"
                      >
                        <r.icon className="w-3.5 h-3.5 text-lumos-danger flex-shrink-0" />
                        <div className="min-w-0">
                          <p className="text-[10px] text-muted-foreground truncate">{r.label}</p>
                          <p className="text-xs font-medium text-lumos-danger">
                            {r.number} &middot; LUMOS AI
                          </p>
                        </div>
                      </button>
                    );
                  }

                  return (
                    <a
                      key={r.number}
                      href={`tel:${r.number}`}
                      className="flex items-center gap-1.5 bg-secondary/50 rounded-lg px-2 sm:px-2.5 py-2 sm:py-2.5 hover:bg-secondary/70 active:bg-secondary/90 transition-colors group min-h-[44px]"
                    >
                      <r.icon className={`w-3.5 h-3.5 ${r.color} flex-shrink-0`} />
                      <div className="min-w-0">
                        <p className="text-[10px] text-muted-foreground truncate">{r.label}</p>
                        <p className="text-xs font-medium text-foreground group-hover:text-primary transition-colors">
                          {r.number}
                        </p>
                      </div>
                    </a>
                  );
                })}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default EmergencyResources;
