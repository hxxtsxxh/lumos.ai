import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, MapPin, Trash2, Clock } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { getUserReports, deleteReport, type SavedReport } from '@/lib/savedReports';

interface SavedReportsPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onLoadReport: (report: SavedReport) => void;
}

const SavedReportsPanel = ({ isOpen, onClose, onLoadReport }: SavedReportsPanelProps) => {
  const { user } = useAuth();
  const [reports, setReports] = useState<SavedReport[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen && user) {
      setLoading(true);
      getUserReports(user.uid)
        .then(setReports)
        .catch(() => setReports([]))
        .finally(() => setLoading(false));
    }
  }, [isOpen, user]);

  const handleDelete = async (id: string) => {
    await deleteReport(id);
    setReports((prev) => prev.filter((r) => r.id !== id));
  };

  const getScoreColor = (score: number) => {
    if (score >= 70) return 'text-lumos-safe';
    if (score >= 40) return 'text-lumos-caution';
    return 'text-lumos-danger';
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
            onClick={onClose}
          />
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed right-0 top-0 bottom-0 w-full sm:max-w-md glass-panel z-50 overflow-y-auto"
          >
            <div className="p-4 sm:p-6">
              <div className="flex items-center justify-between mb-4 sm:mb-6">
                <h2 className="text-xl font-display font-semibold text-foreground">Saved Reports</h2>
                <button
                  onClick={onClose}
                  className="p-2 rounded-xl hover:bg-secondary/50 transition-colors"
                >
                  <X className="w-5 h-5 text-muted-foreground" />
                </button>
              </div>

              {loading ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-20 bg-secondary/50 rounded-xl animate-pulse" />
                  ))}
                </div>
              ) : reports.length === 0 ? (
                <div className="text-center py-12">
                  <MapPin className="w-10 h-10 text-muted-foreground mx-auto mb-3 opacity-50" />
                  <p className="text-muted-foreground">No saved reports yet</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Search a location and save the report to see it here.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {reports.map((report) => (
                    <motion.div
                      key={report.id}
                      layout
                      className="bg-secondary/30 rounded-xl p-4 hover:bg-secondary/50 transition-colors cursor-pointer group"
                      onClick={() => {
                        onLoadReport(report);
                        onClose();
                      }}
                    >
                      <div className="flex items-start justify-between">
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium text-foreground truncate">
                            {report.locationName}
                          </p>
                          <div className="flex items-center gap-3 mt-1.5">
                            <span className={`text-lg font-display font-bold ${getScoreColor(report.safetyIndex)}`}>
                              {report.safetyIndex}
                            </span>
                            <span className="text-xs text-muted-foreground flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              {report.params.timeOfTravel}
                            </span>
                          </div>
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(report.id);
                          }}
                          className="p-2 rounded-lg opacity-100 sm:opacity-0 sm:group-hover:opacity-100 hover:bg-destructive/20 transition-all"
                        >
                          <Trash2 className="w-4 h-4 text-destructive" />
                        </button>
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

export default SavedReportsPanel;
