import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
} from 'recharts';
import { TrendingDown, TrendingUp } from 'lucide-react';
import { fetchHistoricalTrends } from '@/lib/api';
import type { HistoricalDataPoint } from '@/types/safety';

interface HistoricalTrendsProps {
  state: string;
  expanded?: boolean;
}

const HistoricalTrends = ({ state, expanded: externalExpanded }: HistoricalTrendsProps) => {
  const expanded = externalExpanded ?? false;
  const [data, setData] = useState<HistoricalDataPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    // Reset data when state changes so fresh data is fetched
    setData([]);
    setError(false);
  }, [state]);

  useEffect(() => {
    if (!expanded || !state || data.length > 0) return;
    let cancelled = false;
    setLoading(true);
    setError(false);

    fetchHistoricalTrends(state)
      .then((result) => {
        if (!cancelled) {
          setData(result.data || []);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError(true);
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [expanded, state, data.length]);

  // Calculate trend
  const trend = data.length >= 2
    ? data[data.length - 1].total - data[0].total
    : 0;

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
              {loading ? (
                <div className="h-[160px] sm:h-[180px] bg-secondary/50 rounded-xl animate-pulse" />
              ) : error ? (
                <p className="text-sm text-muted-foreground text-center py-6">
                  Historical data unavailable for this state.
                </p>
              ) : data.length > 0 ? (
                <div className="h-[160px] sm:h-[180px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data} margin={{ top: 5, right: 5, left: -15, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis
                        dataKey="year"
                        tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                        axisLine={false}
                      />
                      <YAxis
                        tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                        axisLine={false}
                        tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}K`}
                      />
                      <Tooltip
                        contentStyle={{
                          background: 'hsl(var(--card))',
                          border: '1px solid hsl(var(--border))',
                          borderRadius: '12px',
                          fontSize: '12px',
                          color: 'hsl(var(--card-foreground))',
                        }}
                        formatter={(value: number, name: string) => [
                          value.toLocaleString(),
                          name === 'violentCrime' ? 'Violent Crime' : 'Property Crime',
                        ]}
                      />
                      <Legend
                        wrapperStyle={{ fontSize: '10px' }}
                        formatter={(value: string) =>
                          value === 'violentCrime' ? 'Violent Crime' : 'Property Crime'
                        }
                      />
                      <Line
                        type="monotone"
                        dataKey="violentCrime"
                        stroke="hsl(0, 72%, 55%)"
                        strokeWidth={2}
                        dot={{ r: 3 }}
                        activeDot={{ r: 5 }}
                      />
                      <Line
                        type="monotone"
                        dataKey="propertyCrime"
                        stroke="hsl(38, 92%, 55%)"
                        strokeWidth={2}
                        dot={{ r: 3 }}
                        activeDot={{ r: 5 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-6">
                  No historical data available.
                </p>
              )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default HistoricalTrends;
