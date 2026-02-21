import { useEffect, useCallback, useState, useRef } from 'react';
import { motion } from 'framer-motion';
import { Users, Clock, User, PersonStanding, Car, Train, Sunrise, Sun, Sunset, Moon, ChevronUp, ChevronDown } from 'lucide-react';
import type { TravelParams } from '@/types/safety';

interface ParameterPanelProps {
  params: TravelParams;
  onChange: (params: TravelParams) => void;
  showMode?: boolean;
}

const baseGenderOptions: { value: TravelParams['gender']; label: string }[] = [
  { value: 'male', label: 'Male' },
  { value: 'female', label: 'Female' },
  { value: 'mixed', label: 'Mixed' },
  { value: 'prefer-not-to-say', label: 'Any' },
];

const timePeriods = [
  { label: 'Morning', icon: Sunrise, start: 6, end: 12, defaultTime: '09:00', gradient: 'from-amber-400/20 to-orange-400/20', activeGradient: 'from-amber-400 to-orange-400', iconColor: 'text-amber-400' },
  { label: 'Afternoon', icon: Sun, start: 12, end: 17, defaultTime: '14:00', gradient: 'from-yellow-400/20 to-amber-400/20', activeGradient: 'from-yellow-400 to-amber-400', iconColor: 'text-yellow-400' },
  { label: 'Evening', icon: Sunset, start: 17, end: 21, defaultTime: '19:00', gradient: 'from-orange-400/20 to-rose-400/20', activeGradient: 'from-orange-400 to-rose-400', iconColor: 'text-orange-400' },
  { label: 'Night', icon: Moon, start: 21, end: 6, defaultTime: '23:00', gradient: 'from-indigo-400/20 to-purple-400/20', activeGradient: 'from-indigo-400 to-purple-400', iconColor: 'text-indigo-400' },
];

const getActivePeriod = (time: string) => {
  const h = parseInt(time.split(':')[0], 10);
  return timePeriods.find((p) =>
    p.start < p.end ? h >= p.start && h < p.end : h >= p.start || h < p.end
  );
};

/* ── Custom Time Picker ──────────────────────────────────────── */

const parse24 = (time: string) => {
  const [hStr, mStr] = time.split(':');
  return { h24: parseInt(hStr, 10), m: parseInt(mStr, 10) };
};

const to24 = (h12: number, m: number, ampm: 'AM' | 'PM'): string => {
  let h = h12;
  if (ampm === 'AM' && h === 12) h = 0;
  else if (ampm === 'PM' && h !== 12) h += 12;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
};

interface TimePickerProps {
  value: string;          // "HH:mm" 24-hour
  onChange: (v: string) => void;
}

const TimePicker = ({ value, onChange }: TimePickerProps) => {
  const { h24, m } = parse24(value);
  const ampm: 'AM' | 'PM' = h24 >= 12 ? 'PM' : 'AM';
  const h12 = h24 === 0 ? 12 : h24 > 12 ? h24 - 12 : h24;

  const [editingHour, setEditingHour] = useState(false);
  const [editingMin, setEditingMin] = useState(false);
  const [hourDraft, setHourDraft] = useState('');
  const [minDraft, setMinDraft] = useState('');
  const hourRef = useRef<HTMLInputElement>(null);
  const minRef = useRef<HTMLInputElement>(null);

  const setTime = useCallback(
    (h: number, min: number, ap: 'AM' | 'PM') => onChange(to24(h, min, ap)),
    [onChange],
  );

  const incHour = () => {
    const next = h12 === 12 ? 1 : h12 + 1;
    const nextAp = h12 === 11 ? (ampm === 'AM' ? 'PM' : 'AM') : ampm;
    setTime(next, m, nextAp);
  };
  const decHour = () => {
    const next = h12 === 1 ? 12 : h12 - 1;
    const nextAp = h12 === 12 ? (ampm === 'AM' ? 'PM' : 'AM') : ampm;
    setTime(next, m, nextAp);
  };
  const incMin = () => {
    const next = (m + 5) % 60;
    if (next < m) incHour();
    else setTime(h12, next, ampm);
  };
  const decMin = () => {
    const next = m < 5 ? 55 : m - 5;
    if (next > m) decHour();
    else setTime(h12, next, ampm);
  };
  const toggleAmPm = () => setTime(h12, m, ampm === 'AM' ? 'PM' : 'AM');

  // Start editing hour
  const startEditHour = () => {
    setHourDraft(String(h12));
    setEditingHour(true);
    setTimeout(() => hourRef.current?.select(), 0);
  };

  // Start editing minute
  const startEditMin = () => {
    setMinDraft(String(m).padStart(2, '0'));
    setEditingMin(true);
    setTimeout(() => minRef.current?.select(), 0);
  };

  // Commit hour edit
  const commitHour = () => {
    setEditingHour(false);
    const parsed = parseInt(hourDraft, 10);
    if (!isNaN(parsed) && parsed >= 1 && parsed <= 12) {
      setTime(parsed, m, ampm);
    }
  };

  // Commit minute edit
  const commitMin = () => {
    setEditingMin(false);
    const parsed = parseInt(minDraft, 10);
    if (!isNaN(parsed) && parsed >= 0 && parsed <= 59) {
      setTime(h12, parsed, ampm);
    }
  };

  const colBtn =
    'flex items-center justify-center w-full h-7 rounded-lg text-muted-foreground/60 hover:text-foreground hover:bg-white/5 active:scale-95 transition-all';

  const digitDisplay =
    'text-xl font-semibold tabular-nums text-foreground select-none cursor-pointer rounded-lg hover:bg-white/5 px-1 py-0.5 transition-colors';

  const digitInput =
    'w-10 text-center text-xl font-semibold tabular-nums text-foreground bg-white/10 rounded-lg outline-none ring-2 ring-primary/50 px-1 py-0.5';

  return (
    <div className="flex items-center justify-center gap-1 bg-secondary/50 backdrop-blur-sm rounded-xl border border-white/5 px-3 py-2">
      {/* Hour */}
      <div className="flex flex-col items-center w-12">
        <button onClick={incHour} className={colBtn} aria-label="Increase hour">
          <ChevronUp className="w-4 h-4" />
        </button>
        {editingHour ? (
          <input
            ref={hourRef}
            value={hourDraft}
            onChange={(e) => {
              const v = e.target.value.replace(/\D/g, '').slice(0, 2);
              setHourDraft(v);
            }}
            onBlur={commitHour}
            onKeyDown={(e) => {
              if (e.key === 'Enter') commitHour();
              if (e.key === 'Escape') setEditingHour(false);
              e.stopPropagation();
            }}
            className={digitInput}
            aria-label="Type hour"
          />
        ) : (
          <span onClick={startEditHour} className={digitDisplay} title="Click to type hour">
            {String(h12).padStart(2, '0')}
          </span>
        )}
        <button onClick={decHour} className={colBtn} aria-label="Decrease hour">
          <ChevronDown className="w-4 h-4" />
        </button>
      </div>

      <span className="text-xl font-semibold text-muted-foreground select-none pb-0.5">:</span>

      {/* Minute */}
      <div className="flex flex-col items-center w-12">
        <button onClick={incMin} className={colBtn} aria-label="Increase minute">
          <ChevronUp className="w-4 h-4" />
        </button>
        {editingMin ? (
          <input
            ref={minRef}
            value={minDraft}
            onChange={(e) => {
              const v = e.target.value.replace(/\D/g, '').slice(0, 2);
              setMinDraft(v);
            }}
            onBlur={commitMin}
            onKeyDown={(e) => {
              if (e.key === 'Enter') commitMin();
              if (e.key === 'Escape') setEditingMin(false);
              e.stopPropagation();
            }}
            className={digitInput}
            aria-label="Type minute"
          />
        ) : (
          <span onClick={startEditMin} className={digitDisplay} title="Click to type minute">
            {String(m).padStart(2, '0')}
          </span>
        )}
        <button onClick={decMin} className={colBtn} aria-label="Decrease minute">
          <ChevronDown className="w-4 h-4" />
        </button>
      </div>

      {/* AM / PM */}
      <button
        onClick={toggleAmPm}
        className="ml-2 px-3 py-1.5 rounded-lg text-xs font-bold tracking-wide bg-primary/15 text-primary hover:bg-primary/25 active:scale-95 transition-all select-none"
        aria-label={`Toggle AM/PM, currently ${ampm}`}
      >
        {ampm}
      </button>
    </div>
  );
};

const ParameterPanel = ({ params, onChange, showMode = false }: ParameterPanelProps) => {
  const update = <K extends keyof TravelParams>(key: K, value: TravelParams[K]) => {
    onChange({ ...params, [key]: value });
  };

  // Solo traveler: Mixed is invalid — hide it and reset if currently selected
  const isSolo = params.peopleCount === 1;
  const genderOptions = isSolo
    ? baseGenderOptions.filter((g) => g.value !== 'mixed')
    : baseGenderOptions;
  const effectiveGender =
    isSolo && params.gender === 'mixed' ? 'prefer-not-to-say' : params.gender;

  useEffect(() => {
    if (isSolo && params.gender === 'mixed') {
      onChange({ ...params, gender: 'prefer-not-to-say' });
    }
  }, [isSolo, params.gender]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2, duration: 0.4 }}
      className="glass-panel rounded-2xl p-4 sm:p-5 space-y-3.5 sm:space-y-4"
    >
      <h3 className="text-xs sm:text-sm font-medium text-muted-foreground uppercase tracking-wider">
        Travel Details
      </h3>

      {/* People count */}
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Users className="w-4 h-4" />
          <span>People</span>
        </div>
        <div className="flex gap-2">
          {[1, 2, 3, 4].map((n) => (
            <button
              key={n}
              onClick={() => {
                if (n === 1 && params.gender === 'mixed') {
                  onChange({ ...params, peopleCount: 1, gender: 'prefer-not-to-say' });
                } else {
                  update('peopleCount', n);
                }
              }}
              aria-label={`${n === 4 ? '4 or more' : n} ${n === 1 ? 'person' : 'people'}`}
              aria-pressed={params.peopleCount === n}
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
                params.peopleCount === n
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
              }`}
            >
              {n === 4 ? '4+' : n}
            </button>
          ))}
        </div>
      </div>

      {/* Gender */}
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <User className="w-4 h-4" />
          <span>Gender</span>
        </div>
        <div className="flex gap-2">
          {genderOptions.map((g) => (
            <button
              key={g.value}
              onClick={() => update('gender', g.value)}
              aria-label={`Gender: ${g.label}`}
              aria-pressed={effectiveGender === g.value}
              className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all ${
                effectiveGender === g.value
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
              }`}
            >
              {g.label}
            </button>
          ))}
        </div>
      </div>

      {/* Travel Mode */}
      {showMode && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <PersonStanding className="w-4 h-4" />
            <span>Travel Mode</span>
          </div>
          <div className="flex gap-2">
            {([
              { value: 'walking' as const, label: 'Walk', Icon: PersonStanding },
              { value: 'driving' as const, label: 'Drive', Icon: Car },
              { value: 'transit' as const, label: 'Transit', Icon: Train },
            ]).map(({ value, label, Icon }) => (
              <button
                key={value}
                onClick={() => update('mode', value)}
                aria-label={`Travel mode: ${label}`}
                aria-pressed={params.mode === value}
                className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-medium transition-all ${
                  params.mode === value
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Time of Travel */}
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Clock className="w-4 h-4" />
          <span>Time of Travel</span>
        </div>

        {/* Period quick-select */}
        <div className="grid grid-cols-4 gap-1 sm:gap-1.5">
          {timePeriods.map((period) => {
            const active = getActivePeriod(params.timeOfTravel) === period;
            return (
              <button
                key={period.label}
                onClick={() => update('timeOfTravel', period.defaultTime)}
                aria-label={`Set time to ${period.label}`}
                aria-pressed={active}
                className={`relative flex flex-col items-center gap-0.5 sm:gap-1 py-2 sm:py-2.5 rounded-xl text-[10px] sm:text-[11px] font-medium transition-all
                  ${
                    active
                      ? `bg-gradient-to-br ${period.activeGradient} text-white shadow-md shadow-black/20 scale-[1.03]`
                      : `bg-gradient-to-br ${period.gradient} text-muted-foreground hover:scale-[1.02] hover:brightness-110`
                  }`}
              >
                <period.icon className={`w-4 h-4 ${active ? 'text-white' : period.iconColor}`} />
                {period.label}
              </button>
            );
          })}
        </div>

        {/* Custom time picker */}
        <TimePicker
          value={params.timeOfTravel}
          onChange={(v) => update('timeOfTravel', v)}
        />
      </div>
    </motion.div>
  );
};

export default ParameterPanel;
