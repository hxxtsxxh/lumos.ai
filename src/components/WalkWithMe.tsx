import { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Navigation, X, Share2, Phone } from 'lucide-react';
import { toast } from 'sonner';

interface WalkWithMeProps {
  destLat: number;
  destLng: number;
  destName: string;
  routeSafetyScore: number;
  onStop: () => void;
  onPositionUpdate?: (lat: number, lng: number) => void;
}

const WalkWithMe = ({ destLat, destLng, destName, routeSafetyScore, onStop, onPositionUpdate }: WalkWithMeProps) => {
  const [position, setPosition] = useState<{ lat: number; lng: number } | null>(null);
  const [distanceRemaining, setDistanceRemaining] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [sharing, setSharing] = useState(false);
  const watchRef = useRef<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Haversine distance in meters
  const getDistance = useCallback((lat1: number, lng1: number, lat2: number, lng2: number) => {
    const R = 6371000;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) ** 2 +
      Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
      Math.sin(dLng / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }, []);

  // Start geolocation watch
  useEffect(() => {
    if (!navigator.geolocation) {
      toast.error('Geolocation is not supported by your browser');
      return;
    }

    watchRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        const { latitude: lat, longitude: lng } = pos.coords;
        setPosition({ lat, lng });
        onPositionUpdate?.(lat, lng);

        const dist = getDistance(lat, lng, destLat, destLng);
        setDistanceRemaining(dist);

        // Check if arrived (within 50m)
        if (dist < 50) {
          toast.success('You have arrived at your destination!', { duration: 5000 });
          onStop();
        }
      },
      (err) => {
        console.warn('Geolocation error:', err);
        toast.error('Unable to get your location. Check permissions.');
      },
      {
        enableHighAccuracy: true,
        maximumAge: 5000,
        timeout: 15000,
      }
    );

    // Elapsed timer
    timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);

    return () => {
      if (watchRef.current !== null) navigator.geolocation.clearWatch(watchRef.current);
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [destLat, destLng, getDistance, onStop, onPositionUpdate]);

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  const formatDistance = (m: number) => {
    if (m < 1000) return `${Math.round(m)}m`;
    return `${(m / 1000).toFixed(1)}km`;
  };

  const handleShare = async () => {
    if (!position) return;
    setSharing(true);
    const text = `I'm walking to ${destName}. Track my location: https://maps.google.com/?q=${position.lat},${position.lng}\n\nSafety Score: ${routeSafetyScore}/100\n\nSent via Lumos`;
    try {
      if (navigator.share) {
        await navigator.share({ title: 'My Walk - Lumos', text });
      } else {
        await navigator.clipboard.writeText(text);
        toast.success('Location copied to clipboard');
      }
    } catch {
      // User cancelled share
    } finally {
      setSharing(false);
    }
  };

  const scoreColor = routeSafetyScore >= 70
    ? 'text-lumos-safe'
    : routeSafetyScore >= 40
    ? 'text-lumos-caution'
    : 'text-lumos-danger';

  return (
    <motion.div
      initial={{ opacity: 0, y: 50 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 50 }}
      className="fixed bottom-0 left-0 right-0 z-50 p-3 sm:p-4 pb-safe"
    >
      <div className="max-w-md mx-auto glass-panel rounded-2xl overflow-hidden border border-primary/20">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border/50">
          <div className="flex items-center gap-2">
            <div className="relative">
              <Navigation className="w-5 h-5 text-primary animate-pulse" />
              <div className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-lumos-safe animate-ping" />
            </div>
            <div>
              <p className="text-sm font-medium text-foreground">Walk in Progress</p>
              <p className="text-xs text-muted-foreground">{formatTime(elapsed)} elapsed</p>
            </div>
          </div>
          <button
            onClick={onStop}
            className="p-2 rounded-xl hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Stop walk tracking"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-2 sm:gap-3 p-3 sm:p-4">
          <div className="text-center">
            <p className="text-xs text-muted-foreground mb-1">Distance</p>
            <p className="text-lg font-semibold text-foreground">
              {distanceRemaining !== null ? formatDistance(distanceRemaining) : '...'}
            </p>
          </div>
          <div className="text-center">
            <p className="text-xs text-muted-foreground mb-1">Safety</p>
            <p className={`text-lg font-semibold ${scoreColor}`}>
              {routeSafetyScore}
            </p>
          </div>
          <div className="text-center">
            <p className="text-xs text-muted-foreground mb-1">Destination</p>
            <p className="text-xs font-medium text-foreground truncate" title={destName}>
              {destName.split(',')[0]}
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-2 px-3 sm:px-4 pb-3 sm:pb-4">
          <button
            onClick={handleShare}
            disabled={sharing}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl bg-secondary text-foreground text-sm font-medium hover:bg-secondary/80 transition-colors"
          >
            <Share2 className="w-4 h-4" />
            Share Location
          </button>
          <a
            href="tel:911"
            className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-lumos-danger/20 text-lumos-danger text-sm font-medium hover:bg-lumos-danger/30 transition-colors"
          >
            <Phone className="w-4 h-4" />
            911
          </a>
        </div>
      </div>
    </motion.div>
  );
};

export default WalkWithMe;
