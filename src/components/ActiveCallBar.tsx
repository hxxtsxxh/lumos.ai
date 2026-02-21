import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence, useDragControls } from 'framer-motion';
import {
  PhoneOff, Send, MapPin, CheckCircle2, Loader2, GripHorizontal,
} from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { sendEmergencyCallUpdate, endEmergencyCall, reverseGeocode } from '@/lib/api';
import { rtdb } from '@/lib/firebase';
import { ref, onValue } from 'firebase/database';
import { toast } from 'sonner';

interface ActiveCallBarProps {
  callId: string;
  elapsed: number;
  onEnd: () => void;
  lat: number;
  lng: number;
}

/** Tailwind `md` breakpoint in px */
const MD_BREAKPOINT = 768;

function useIsMobile() {
  const [mobile, setMobile] = useState(
    typeof window !== 'undefined' ? window.innerWidth < MD_BREAKPOINT : false,
  );
  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${MD_BREAKPOINT - 1}px)`);
    const handler = (e: MediaQueryListEvent) => setMobile(e.matches);
    mq.addEventListener('change', handler);
    setMobile(mq.matches);
    return () => mq.removeEventListener('change', handler);
  }, []);
  return mobile;
}

export default function ActiveCallBar({ callId, elapsed, onEnd, lat, lng }: ActiveCallBarProps) {
  const [updateText, setUpdateText] = useState('');
  const [sending, setSending] = useState(false);
  const [sentCount, setSentCount] = useState(0);
  const [showSent, setShowSent] = useState(false);
  const [currentLat, setCurrentLat] = useState(lat);
  const [currentLng, setCurrentLng] = useState(lng);
  const locationIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const sentTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const constraintsRef = useRef<HTMLDivElement>(null);
  const dragControls = useDragControls();
  const isMobile = useIsMobile();

  // 30-second GPS tracker — sends location + address to VAPI agent
  useEffect(() => {
    const sendLocation = () => {
      if (!navigator.geolocation) return;
      navigator.geolocation.getCurrentPosition(
        async (pos) => {
          const { latitude, longitude } = pos.coords;
          setCurrentLat(latitude);
          setCurrentLng(longitude);
          // Reverse geocode to get a readable address
          const addr = await reverseGeocode(latitude, longitude);
          const locText = addr
            ? `${addr} (${latitude.toFixed(4)}, ${longitude.toFixed(4)})`
            : `${latitude.toFixed(4)}, ${longitude.toFixed(4)}`;
          const msg = `LOCATION UPDATE: Caller is now at ${locText}.`;
          sendEmergencyCallUpdate(callId, msg).catch(() => {});
        },
        () => {},
        { enableHighAccuracy: true, maximumAge: 15000, timeout: 5000 }
      );
    };

    sendLocation();
    locationIntervalRef.current = setInterval(sendLocation, 30_000);

    return () => {
      if (locationIntervalRef.current) clearInterval(locationIntervalRef.current);
    };
  }, [callId]);

  // Prevent screen sleep during active call
  useEffect(() => {
    let wakeLock: WakeLockSentinel | null = null;
    const acquire = async () => {
      try {
        wakeLock = await navigator.wakeLock.request('screen');
      } catch {
        // Wake Lock API not supported or permission denied
      }
    };
    acquire();
    return () => {
      wakeLock?.release();
    };
  }, []);

  // Cleanup sent timer
  useEffect(() => {
    return () => {
      if (sentTimerRef.current) clearTimeout(sentTimerRef.current);
    };
  }, []);

  // Listen for RTDB call status — auto-close when agent or backend ends call
  useEffect(() => {
    const statusRef = ref(rtdb, `calls/${callId}/status`);
    const unsubscribe = onValue(statusRef, (snap) => {
      const status = snap.val();
      if (status === 'ended') {
        toast.info('Call ended by operator');
        onEnd();
      }
    });
    return () => unsubscribe();
  }, [callId, onEnd]);

  const handleSend = async () => {
    const text = updateText.trim();
    if (!text || sending) return;
    setSending(true);
    setUpdateText('');
    try {
      await sendEmergencyCallUpdate(callId, text);
      setSentCount((c) => c + 1);
      setShowSent(true);
      if (sentTimerRef.current) clearTimeout(sentTimerRef.current);
      sentTimerRef.current = setTimeout(() => setShowSent(false), 800);
      inputRef.current?.focus();
    } catch {
      toast.error('Failed to send update');
      setUpdateText(text); // restore text on failure
    } finally {
      setSending(false);
    }
  };

  const handleEnd = () => {
    // Close immediately — don't wait for the API
    onEnd();
    toast.info('Ending call...');
    endEmergencyCall(callId).catch(() => {
      toast.error('Could not fully end call on server');
    });
  };

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  return (
    <>
      {/* Drag boundary — desktop only */}
      {!isMobile && (
        <div ref={constraintsRef} className="fixed inset-0 z-40 pointer-events-none" />
      )}

      <motion.div
        /* Desktop: draggable from top, centered */
        /* Mobile: fixed to bottom, full width, no drag */
        {...(!isMobile
          ? {
              drag: true,
              dragControls,
              dragListener: false,
              dragConstraints: constraintsRef,
              dragElastic: 0.1,
              dragMomentum: false,
              style: { touchAction: 'none' as const },
            }
          : {})}
        initial={isMobile ? { y: 80, opacity: 0 } : { y: -80, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={isMobile ? { y: 80, opacity: 0 } : { y: -80, opacity: 0 }}
        className={
          isMobile
            ? 'fixed bottom-0 inset-x-0 z-50'
            : 'fixed top-16 left-1/2 -translate-x-1/2 z-50 w-[95vw] max-w-lg cursor-default'
        }
      >
        <div
          className={`bg-red-950/95 backdrop-blur-xl border-red-500/40 shadow-2xl shadow-red-900/30 ${
            isMobile
              ? 'rounded-t-2xl border-t px-3 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]'
              : 'rounded-2xl border px-4 py-3'
          }`}
        >
          {/* Drag handle — desktop only */}
          {!isMobile && (
            <div
              onPointerDown={(e) => dragControls.start(e)}
              className="flex justify-center -mt-1 mb-1 cursor-grab active:cursor-grabbing touch-none select-none"
            >
              <GripHorizontal className="w-5 h-5 text-red-500/50" />
            </div>
          )}

          {/* Row 1: status + duration + end */}
          <div className="flex items-center justify-between gap-2 sm:gap-3 mb-2">
            <div className="flex items-center gap-1.5 sm:gap-2 min-w-0">
              <span className="relative flex h-3 w-3 flex-shrink-0">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500" />
              </span>
              <span className="text-xs sm:text-sm font-semibold text-red-200 truncate">
                {isMobile ? 'EMERGENCY' : 'EMERGENCY CALL'}
              </span>
            </div>
            <span className="text-base sm:text-lg font-mono font-bold text-white tabular-nums flex-shrink-0">
              {formatTime(elapsed)}
            </span>
            <Button
              size="sm"
              variant="destructive"
              onClick={handleEnd}
              className="gap-1 sm:gap-1.5 flex-shrink-0 h-8 sm:h-9 px-2.5 sm:px-3"
            >
              <PhoneOff className="w-4 h-4" />
              <span className="text-xs sm:text-sm">End</span>
            </Button>
          </div>

          {/* Row 2: live location + sent count */}
          <div className="flex items-center justify-between text-[10px] sm:text-xs text-red-300 mb-2">
            <div className="flex items-center gap-1 sm:gap-1.5 min-w-0">
              <MapPin className="w-3 h-3 flex-shrink-0" />
              <span className="truncate">
                {currentLat.toFixed(4)}, {currentLng.toFixed(4)} · 30s
              </span>
            </div>
            {sentCount > 0 && (
              <span className="text-red-400/80 text-[10px] font-medium flex-shrink-0">
                {sentCount} msg{sentCount !== 1 ? 's' : ''} sent
              </span>
            )}
          </div>

          {/* Row 3: input + inline confirmation */}
          <div className="relative">
            <div className="flex gap-1.5 sm:gap-2">
              <Input
                ref={inputRef}
                value={updateText}
                onChange={(e) => setUpdateText(e.target.value)}
                placeholder="Message to operator..."
                className="bg-red-200 border-red-500/30 text-black placeholder:text-red-900/40 text-sm h-9"
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleSend();
                  }
                }}
              />
              <Button
                size="icon"
                onClick={handleSend}
                disabled={!updateText.trim() || sending}
                className="bg-emerald-600 hover:bg-emerald-500 text-white flex-shrink-0 h-9 w-9 transition-colors disabled:bg-red-800/40"
              >
                {sending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </Button>
            </div>

            {/* Inline "Sent" confirmation banner */}
            <AnimatePresence>
              {showSent && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ duration: 0.15 }}
                  className="absolute inset-0 flex items-center justify-center bg-emerald-600/90 rounded-lg pointer-events-none"
                >
                  <CheckCircle2 className="w-4 h-4 text-white mr-1.5" />
                  <span className="text-sm font-medium text-white">Sent to operator</span>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </motion.div>
    </>
  );
}
