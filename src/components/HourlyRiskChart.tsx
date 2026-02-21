import { motion } from 'framer-motion';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { Clock } from 'lucide-react';
import type { HourlyRiskData } from '@/lib/api';

interface HourlyRiskChartProps {
  currentHour: number; // 0-23
  hourlyData: HourlyRiskData[];
}

const HourlyRiskChart = ({ currentHour, hourlyData }: HourlyRiskChartProps) => {
  const data = hourlyData;
  const currentLabel = data[currentHour]?.hour;

  // Compute dynamic Y-axis bounds that zoom into the actual data range
  const risks = data.map(d => d.risk);
  const dataMin = Math.min(...risks);
  const dataMax = Math.max(...risks);
  const padding = Math.max(5, Math.round((dataMax - dataMin) * 0.25));
  const yMin = Math.max(0, dataMin - padding);
  const yMax = Math.min(100, dataMax + padding);

  // Pick gradient color based on mean risk level
  const meanRisk = risks.reduce((a, b) => a + b, 0) / risks.length;
  const gradientColor =
    meanRisk >= 55
      ? 'hsl(0, 80%, 55%)'   // red for high-risk areas
      : meanRisk >= 35
        ? 'hsl(38, 92%, 55%)' // amber for moderate
        : 'hsl(142, 71%, 45%)'; // green for safe

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3, duration: 0.4 }}
      className="glass-panel rounded-2xl p-4 sm:p-5"
      role="figure"
      aria-label="24-hour crime risk pattern chart"
    >
      <div className="flex items-center gap-2 mb-3 sm:mb-4">
        <Clock className="w-4 h-4 text-muted-foreground" />
        <span className="text-xs sm:text-sm font-medium text-muted-foreground">24-Hour Risk Pattern</span>
      </div>

      <div className="h-[120px] sm:h-[140px] -mx-2">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="riskGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={gradientColor} stopOpacity={0.4} />
                <stop offset="100%" stopColor={gradientColor} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="hour"
              tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
              axisLine={false}
              tickLine={false}
              interval={2}
            />
            <YAxis
              domain={[yMin, yMax]}
              tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
              axisLine={false}
              tickLine={false}
              width={30}
              tickFormatter={(v: number) => `${v}%`}
            />
            <Tooltip
              contentStyle={{
                background: 'hsl(var(--card))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '12px',
                fontSize: '12px',
                color: 'hsl(var(--card-foreground))',
              }}
              formatter={(value: number) => [`${value}%`, 'Risk Level']}
            />
            {currentLabel && (
              <ReferenceLine
                x={currentLabel}
                stroke="hsl(174, 62%, 47%)"
                strokeDasharray="4 4"
                label={{
                  value: 'Now',
                  position: 'top',
                  fill: 'hsl(174, 62%, 47%)',
                  fontSize: 10,
                }}
              />
            )}
            <Area
              type="monotone"
              dataKey="risk"
              stroke={gradientColor}
              strokeWidth={2}
              fill="url(#riskGradient)"
              animationDuration={1200}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
};

export default HourlyRiskChart;
