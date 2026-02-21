import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, X } from 'lucide-react';
import { submitUserReport } from '@/lib/api';
import { toast } from 'sonner';

interface ReportIncidentProps {
  lat: number;
  lng: number;
  userId?: string;
  expanded?: boolean;
}

const incidentTypes = [
  'Theft', 'Assault', 'Vandalism', 'Suspicious Activity',
  'Harassment', 'Vehicle Break-in', 'Poor Lighting', 'Other',
];

const ReportIncident = ({ lat, lng, userId, expanded: externalExpanded }: ReportIncidentProps) => {
  const expanded = externalExpanded ?? false;
  const [showForm, setShowForm] = useState(false);
  const [type, setType] = useState('');
  const [description, setDescription] = useState('');
  const [severity, setSeverity] = useState<'low' | 'medium' | 'high'>('medium');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!type) {
      toast.error('Please select an incident type');
      return;
    }
    setSubmitting(true);
    try {
      await submitUserReport({
        lat,
        lng,
        type,
        description,
        severity,
        timestamp: new Date().toISOString(),
        userId,
      });
      toast.success('Report submitted — thanks for keeping the community safe!');
      setShowForm(false);
      setType('');
      setDescription('');
      setSeverity('medium');
    } catch {
      toast.error('Failed to submit report');
    } finally {
      setSubmitting(false);
    }
  };

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
              {!showForm ? (
                <button
                  onClick={() => setShowForm(true)}
                  className="w-full py-3 rounded-xl border border-dashed border-border text-sm text-muted-foreground hover:text-foreground hover:border-primary/50 active:border-primary/70 transition-colors min-h-[48px]"
                >
                  + Report something near this location
                </button>
              ) : (
                <form onSubmit={handleSubmit} className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-muted-foreground">What happened?</span>
                    <button
                      type="button"
                      onClick={() => setShowForm(false)}
                      className="p-1 rounded hover:bg-secondary"
                    >
                      <X className="w-3 h-3 text-muted-foreground" />
                    </button>
                  </div>

                  {/* Incident type grid */}
                  <div className="grid grid-cols-2 gap-1.5">
                    {incidentTypes.map((t) => (
                      <button
                        key={t}
                        type="button"
                        onClick={() => setType(t)}
                        className={`px-3 py-2.5 sm:py-2 rounded-lg text-xs font-medium transition-all min-h-[40px] ${
                          type === t
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
                        }`}
                      >
                        {t}
                      </button>
                    ))}
                  </div>

                  {/* Severity */}
                  <div className="space-y-1">
                    <span className="text-xs text-muted-foreground">Severity</span>
                    <div className="flex gap-2">
                      {(['low', 'medium', 'high'] as const).map((s) => (
                        <button
                          key={s}
                          type="button"
                          onClick={() => setSeverity(s)}
                          className={`flex-1 py-2.5 sm:py-2 rounded-lg text-xs font-medium transition-all min-h-[40px] ${
                            severity === s
                              ? s === 'low'
                                ? 'bg-green-500/20 text-lumos-safe border border-green-500/30'
                                : s === 'medium'
                                ? 'bg-amber-500/20 text-lumos-caution border border-amber-500/30'
                                : 'bg-red-500/20 text-lumos-danger border border-red-500/30'
                              : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
                          }`}
                        >
                          {s.charAt(0).toUpperCase() + s.slice(1)}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Description */}
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Brief description (optional)..."
                    rows={2}
                    className="w-full bg-secondary text-secondary-foreground px-3 py-2 rounded-lg text-sm outline-none focus:ring-1 focus:ring-primary resize-none"
                  />

                  <button
                    type="submit"
                    disabled={submitting || !type}
                    className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50 hover:opacity-90 transition-opacity"
                  >
                    <Send className="w-4 h-4" />
                    {submitting ? 'Submitting...' : 'Submit Report'}
                  </button>
                </form>
              )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default ReportIncident;
