import { useState, useEffect, useRef } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { PhoneOff, Send, AlertTriangle } from 'lucide-react';
import { startEmergencyCall, sendEmergencyCallUpdate, endEmergencyCall } from '@/lib/api';
import { toast } from 'sonner';

const INCIDENT_TYPES = [
  { value: 'being_followed', label: 'Being followed' },
  { value: 'witnessed_crime', label: 'Witnessed crime' },
  { value: 'medical_emergency', label: 'Medical emergency' },
  { value: 'assault', label: 'Assault / threat' },
  { value: 'unsafe_situation', label: 'Unsafe situation' },
  { value: 'other', label: 'Other' },
];

const SEVERITIES = [
  { value: 'CRITICAL', label: 'Critical' },
  { value: 'HIGH', label: 'High' },
  { value: 'MEDIUM', label: 'Medium' },
];

interface EmergencyCallModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  lat: number;
  lng: number;
  address?: string;
  safetyScore?: number;
  callerName?: string;
  movementDirection?: string;
  movementSpeed?: string;
  demoPhoneNumber?: string;
}

function EmergencyCallModal({
  open,
  onOpenChange,
  lat,
  lng,
  address = '',
  safetyScore = 0,
  callerName: initialName = '',
  movementDirection,
  movementSpeed,
  demoPhoneNumber,
}: EmergencyCallModalProps) {
  const [step, setStep] = useState<'form' | 'countdown' | 'active'>('form');
  const [name, setName] = useState(initialName);
  const [age, setAge] = useState('');
  const [incidentType, setIncidentType] = useState('being_followed');
  const [severity, setSeverity] = useState('HIGH');
  const [notes, setNotes] = useState('');
  const [countdown, setCountdown] = useState(10);
  const [callId, setCallId] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const [updateText, setUpdateText] = useState('');
  const [sending, setSending] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const locationIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (initialName) setName(initialName);
  }, [initialName]);

  useEffect(() => {
    if (step === 'active' && callId) {
      timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
      return () => {
        if (timerRef.current) clearInterval(timerRef.current);
      };
    }
  }, [step, callId]);

  // Every 30 seconds, send current location to the operator via the assistant
  useEffect(() => {
    if (step !== 'active' || !callId) return;

    const sendLocationUpdate = () => {
      if (!navigator.geolocation) return;
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const { latitude, longitude } = pos.coords;
          const message = `LOCATION UPDATE: The caller's current coordinates are ${latitude.toFixed(6)}, ${longitude.toFixed(6)}.`;
          sendEmergencyCallUpdate(callId, message).catch(() => {
            // Ignore errors (e.g. call may have ended)
          });
        },
        () => {},
        { enableHighAccuracy: true, maximumAge: 15000, timeout: 5000 }
      );
    };

    // First update after 30s, then every 30s
    locationIntervalRef.current = setInterval(sendLocationUpdate, 30_000);

    return () => {
      if (locationIntervalRef.current) {
        clearInterval(locationIntervalRef.current);
        locationIntervalRef.current = null;
      }
    };
  }, [step, callId]);

  useEffect(() => {
    if (step !== 'countdown') return;
    if (countdown <= 0) {
      handleStartCall();
      return;
    }
    const t = setInterval(() => setCountdown((c) => c - 1), 1000);
    return () => clearInterval(t);
  }, [step, countdown]);

  const handleStartCall = async () => {
    setStep('active');
    console.log('[EmergencyCallModal] Starting call…', { lat, lng, incidentType, severity });
    try {
      const res = await startEmergencyCall({
        callerName: name || 'Caller',
        callerAge: age || undefined,
        lat,
        lng,
        address: address || undefined,
        safetyScore,
        incidentType,
        severity,
        userNotes: notes || undefined,
        movementDirection,
        movementSpeed,
        demoPhoneNumber: demoPhoneNumber || undefined,
      });
      setCallId(res.callId);
      console.log('[EmergencyCallModal] Call started', { callId: res.callId });
      toast.success('Emergency call started', {
        description: 'LUMOS AI is speaking to the operator on your behalf.',
      });
    } catch (e) {
      console.error('[EmergencyCallModal] startEmergencyCall failed', e);
      const msg =
        e instanceof Error
          ? e.message
          : typeof (e as { message?: string })?.message === 'string'
            ? (e as { message: string }).message
            : 'Check Firebase Functions and VAPI config.';
      toast.error('Could not start call', { description: msg });
      setStep('form');
    }
  };

  const handleSubmitForm = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      toast.error('Please enter your name');
      return;
    }
    setCountdown(10);
    setStep('countdown');
  };

  const handleSendUpdate = async () => {
    const text = updateText.trim();
    if (!text || !callId || sending) return;
    setSending(true);
    try {
      await sendEmergencyCallUpdate(callId, text);
      setUpdateText('');
      toast.success('Update sent to operator');
    } catch {
      toast.error('Failed to send update');
    } finally {
      setSending(false);
    }
  };

  const handleEndCall = async () => {
    if (!callId) {
      onOpenChange(false);
      return;
    }
    try {
      await endEmergencyCall(callId);
      toast.info('Call ended');
    } catch {
      toast.error('Could not end call from app');
    }
    setCallId('');
    setStep('form');
    setElapsed(0);
    onOpenChange(false);
  };

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  const handleClose = () => {
    if (step === 'countdown') {
      setStep('form');
      setCountdown(10);
    } else if (step === 'active' && callId) {
      handleEndCall();
    } else {
      onOpenChange(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-lumos-danger" />
            {step === 'form' && 'Call Emergency Services'}
            {step === 'countdown' && 'Calling in…'}
            {step === 'active' && 'Call Active'}
          </DialogTitle>
          <DialogDescription>
            {step === 'form' &&
              'LUMOS AI will call and speak to the operator on your behalf. Confirm details below.'}
            {step === 'countdown' &&
              'Cancel by closing this dialog. Call will start automatically.'}
            {step === 'active' && 'Send updates to relay to the operator. Stay on the line.'}
          </DialogDescription>
        </DialogHeader>

        {step === 'form' && (
          <form onSubmit={handleSubmitForm} className="space-y-4">
            <div>
              <Label htmlFor="name">Your name *</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Name"
                className="mt-1"
              />
            </div>
            <div>
              <Label htmlFor="age">Age (optional)</Label>
              <Input
                id="age"
                value={age}
                onChange={(e) => setAge(e.target.value)}
                placeholder="e.g. 28"
                className="mt-1"
              />
            </div>
            <div>
              <Label>Incident type</Label>
              <Select value={incidentType} onValueChange={setIncidentType}>
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {INCIDENT_TYPES.map((o) => (
                    <SelectItem key={o.value} value={o.value}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Severity</Label>
              <Select value={severity} onValueChange={setSeverity}>
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SEVERITIES.map((o) => (
                    <SelectItem key={o.value} value={o.value}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="notes">Notes (optional)</Label>
              <Textarea
                id="notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Any details to relay to the operator"
                className="mt-1 resize-none"
                rows={2}
              />
            </div>
            <div className="flex gap-2 pt-2">
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button type="submit" className="bg-lumos-danger hover:bg-lumos-danger/90">
                Start call (10s countdown)
              </Button>
            </div>
          </form>
        )}

        {step === 'countdown' && (
          <div className="py-8 text-center">
            <p className="text-4xl font-mono font-bold text-lumos-danger">{countdown}</p>
            <p className="text-sm text-muted-foreground mt-2">Closing this cancels the call</p>
          </div>
        )}

        {step === 'active' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between rounded-xl bg-secondary/50 px-4 py-3">
              <span className="text-sm text-muted-foreground">Duration</span>
              <span className="text-xl font-mono font-semibold">{formatTime(elapsed)}</span>
            </div>
            <p className="text-xs text-muted-foreground">
              Type an update below to relay to the operator (e.g. &quot;moved to 3rd floor stairwell&quot;).
              Your location is sent to the operator every 30 seconds.
            </p>
            <div className="flex gap-2">
              <Input
                value={updateText}
                onChange={(e) => setUpdateText(e.target.value)}
                placeholder="Update for operator…"
                onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleSendUpdate())}
              />
              <Button
                type="button"
                size="icon"
                variant="secondary"
                onClick={handleSendUpdate}
                disabled={!updateText.trim() || sending}
              >
                <Send className="w-4 h-4" />
              </Button>
            </div>
            <Button
              variant="destructive"
              className="w-full"
              onClick={handleEndCall}
            >
              <PhoneOff className="w-4 h-4 mr-2" />
              End call
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export { EmergencyCallModal };
export default EmergencyCallModal;
