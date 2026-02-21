# LUMOS Emergency System Rework — Complete Implementation Guide

## Executive Summary

This document details a full rework of the LUMOS emergency call system. The goals are:

1. **One-tap 911**: Clicking "Emergency (US) 911" in the `EmergencyResources` grid immediately initiates the VAPI call — no separate button, no modal form, no 10-second countdown.
2. **Emergency Profile**: A persistent "Emergency Info" button in the top-right header nav lets users pre-configure their name, age, medical conditions, and emergency contacts. This data is stored in `localStorage` (and optionally synced to Firestore for signed-in users) so VAPI always has it.
3. **Live Location Tracking**: The app tracks the user's GPS every 30 seconds while a call is active and feeds updated coordinates to the VAPI agent so the "operator" always has the victim's current location.
4. **Minimal Active-Call UI**: Instead of a blocking modal, show a slim floating call-status bar at the top/bottom of the screen with duration, a text-update input, and an "End Call" button — the user can still use the map.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Part 1 — Emergency Profile System](#part-1--emergency-profile-system)
- [Part 2 — One-Tap VAPI Call from Emergency Grid](#part-2--one-tap-vapi-call-from-emergency-grid)
- [Part 3 — Active-Call Floating Bar (replaces modal)](#part-3--active-call-floating-bar-replaces-modal)
- [Part 4 — Live Location Tracking During Call](#part-4--live-location-tracking-during-call)
- [Part 5 — VAPI Agent / Firebase Function Changes](#part-5--vapi-agent--firebase-function-changes)
- [Part 6 — File-by-File Changelist](#part-6--file-by-file-changelist)
- [Part 7 — Data Flow Diagrams](#part-7--data-flow-diagrams)
- [Part 8 — Testing Checklist](#part-8--testing-checklist)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND (React)                      │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Emergency    │  │ Emergency    │  │ Active Call   │  │
│  │ Profile      │  │ Resources    │  │ Bar           │  │
│  │ (header btn) │  │ (911 grid)   │  │ (floating)    │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘  │
│         │                  │                   │          │
│         ▼                  ▼                   │          │
│  ┌─────────────────────────────────────────┐   │          │
│  │     useEmergencyProfile() hook          │   │          │
│  │  - localStorage read/write              │   │          │
│  │  - Firestore sync (signed-in)           │   │          │
│  └──────────────────┬──────────────────────┘   │          │
│                      │                          │          │
│         ┌────────────┴────────────┐             │          │
│         ▼                         ▼             ▼          │
│  ┌─────────────┐           ┌──────────────────────────┐  │
│  │ Profile     │           │ useEmergencyCall() hook   │  │
│  │ Modal       │           │  - startEmergencyCall()   │  │
│  │ (settings)  │           │  - sendEmergencyCallUpdate│  │
│  └─────────────┘           │  - endEmergencyCall()     │  │
│                             │  - 30s GPS tracker        │  │
│                             └────────────┬─────────────┘  │
│                                           │                │
└───────────────────────────────────────────┼────────────────┘
                                            │
                                            ▼
                              ┌──────────────────────┐
                              │  Firebase Functions   │
                              │  - startEmergencyCall │
                              │  - emergencyCallMsg   │
                              │  - emergencyCallEnd   │
                              │  - vapiLlm (Gemini)   │
                              └──────────┬───────────┘
                                          │
                                          ▼
                              ┌──────────────────────┐
                              │  VAPI API             │
                              │  → Phone call to      │
                              │    demo 911 number    │
                              └──────────────────────┘
```

---

## Part 1 — Emergency Profile System

### 1.1 What It Is

A new **"Emergency Info"** button sits in the top-right header alongside ThemeToggle, My Location, and UserMenu. Clicking it opens a small modal/drawer where the user sets:

| Field | Type | Required | Example |
|-------|------|----------|---------|
| Full name | text | Yes | "Heet Shah" |
| Age | number | No | 21 |
| Medical conditions | text | No | "asthma, peanut allergy" |
| Emergency contact name | text | No | "Mom" |
| Emergency contact phone | tel | No | "+1-555-123-4567" |
| Default incident type | select | No | "being_followed" |
| Default severity | select | No | "HIGH" |

### 1.2 Storage Strategy

```
localStorage key: "lumos_emergency_profile"
Value: JSON string of EmergencyProfile
```

For signed-in users, optionally mirror to Firestore at `users/{uid}/settings/emergencyProfile` so it persists across devices. On app load, prefer Firestore data if it exists, else fall back to localStorage.

### 1.3 New Files

#### `src/hooks/useEmergencyProfile.ts`

```typescript
import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { db } from '@/lib/firebase';
import { doc, getDoc, setDoc } from 'firebase/firestore';

export interface EmergencyProfile {
  name: string;
  age: string;
  medicalConditions: string;
  emergencyContactName: string;
  emergencyContactPhone: string;
  defaultIncidentType: string;
  defaultSeverity: string;
}

const STORAGE_KEY = 'lumos_emergency_profile';

const DEFAULT_PROFILE: EmergencyProfile = {
  name: '',
  age: '',
  medicalConditions: '',
  emergencyContactName: '',
  emergencyContactPhone: '',
  defaultIncidentType: 'being_followed',
  defaultSeverity: 'HIGH',
};

export function useEmergencyProfile() {
  const { user } = useAuth();
  const [profile, setProfileState] = useState<EmergencyProfile>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? { ...DEFAULT_PROFILE, ...JSON.parse(stored) } : DEFAULT_PROFILE;
    } catch {
      return DEFAULT_PROFILE;
    }
  });
  const [isLoaded, setIsLoaded] = useState(false);

  // On mount or user change, try to load from Firestore
  useEffect(() => {
    if (!user?.uid) {
      setIsLoaded(true);
      return;
    }
    const load = async () => {
      try {
        const snap = await getDoc(doc(db, 'users', user.uid, 'settings', 'emergencyProfile'));
        if (snap.exists()) {
          const firestoreProfile = { ...DEFAULT_PROFILE, ...snap.data() } as EmergencyProfile;
          setProfileState(firestoreProfile);
          localStorage.setItem(STORAGE_KEY, JSON.stringify(firestoreProfile));
        }
      } catch {
        // Firestore unavailable; localStorage data is fine
      }
      setIsLoaded(true);
    };
    load();
  }, [user?.uid]);

  const setProfile = useCallback(
    async (updates: Partial<EmergencyProfile>) => {
      const next = { ...profile, ...updates };
      setProfileState(next);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));

      // Sync to Firestore if signed in
      if (user?.uid) {
        try {
          await setDoc(
            doc(db, 'users', user.uid, 'settings', 'emergencyProfile'),
            next,
            { merge: true }
          );
        } catch {
          // Silent fail; local copy is the source of truth
        }
      }
    },
    [profile, user?.uid]
  );

  const isProfileComplete = Boolean(profile.name.trim());

  return { profile, setProfile, isProfileComplete, isLoaded };
}
```

#### `src/components/EmergencyProfileModal.tsx`

A dialog that lets the user fill in / edit their emergency profile. Opened from the header button.

```tsx
import { useState, useEffect } from 'react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { toast } from 'sonner';
import type { EmergencyProfile } from '@/hooks/useEmergencyProfile';

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

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  profile: EmergencyProfile;
  onSave: (updates: Partial<EmergencyProfile>) => void;
}

export default function EmergencyProfileModal({ open, onOpenChange, profile, onSave }: Props) {
  const [form, setForm] = useState(profile);

  useEffect(() => {
    if (open) setForm(profile);
  }, [open, profile]);

  const handleSave = () => {
    if (!form.name.trim()) {
      toast.error('Name is required for emergency calls');
      return;
    }
    onSave(form);
    toast.success('Emergency profile saved');
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Emergency Profile</DialogTitle>
          <DialogDescription>
            This information is sent to the 911 operator when you tap Emergency.
            It is stored locally on your device.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label htmlFor="ep-name">Full name *</Label>
            <Input
              id="ep-name" value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Your full name" className="mt-1"
            />
          </div>
          <div>
            <Label htmlFor="ep-age">Age</Label>
            <Input
              id="ep-age" value={form.age}
              onChange={(e) => setForm({ ...form, age: e.target.value })}
              placeholder="e.g. 21" className="mt-1"
            />
          </div>
          <div>
            <Label htmlFor="ep-med">Medical conditions</Label>
            <Textarea
              id="ep-med" value={form.medicalConditions}
              onChange={(e) => setForm({ ...form, medicalConditions: e.target.value })}
              placeholder="Allergies, medications, etc." className="mt-1 resize-none" rows={2}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="ep-ec-name">Emergency contact</Label>
              <Input
                id="ep-ec-name" value={form.emergencyContactName}
                onChange={(e) => setForm({ ...form, emergencyContactName: e.target.value })}
                placeholder="Name" className="mt-1"
              />
            </div>
            <div>
              <Label htmlFor="ep-ec-phone">Phone</Label>
              <Input
                id="ep-ec-phone" value={form.emergencyContactPhone}
                onChange={(e) => setForm({ ...form, emergencyContactPhone: e.target.value })}
                placeholder="+1-555-..." className="mt-1"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Default incident type</Label>
              <Select value={form.defaultIncidentType} onValueChange={(v) => setForm({ ...form, defaultIncidentType: v })}>
                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {INCIDENT_TYPES.map((o) => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Default severity</Label>
              <Select value={form.defaultSeverity} onValueChange={(v) => setForm({ ...form, defaultSeverity: v })}>
                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {SEVERITIES.map((o) => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex gap-2 pt-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button onClick={handleSave} className="bg-primary">Save Profile</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

### 1.4 Header Button

In `src/pages/Index.tsx`, add a heart/shield icon button that opens the profile modal. It sits right before `<UserMenu>`:

```tsx
import { Heart } from 'lucide-react'; // or ShieldCheck
import EmergencyProfileModal from '@/components/EmergencyProfileModal';
import { useEmergencyProfile } from '@/hooks/useEmergencyProfile';

// Inside Index component:
const { profile: emergencyProfile, setProfile: setEmergencyProfile, isProfileComplete } = useEmergencyProfile();
const [emergencyProfileOpen, setEmergencyProfileOpen] = useState(false);

// In the header bar, before <UserMenu>:
<motion.button
  initial={{ opacity: 0 }}
  animate={{ opacity: 1 }}
  onClick={() => setEmergencyProfileOpen(true)}
  className={`header-btn flex items-center gap-1.5 text-sm transition-colors glass-panel px-2.5 sm:px-3 py-2 rounded-xl flex-shrink-0 ${
    isProfileComplete
      ? 'text-lumos-safe'
      : 'text-lumos-danger animate-pulse'
  }`}
  title="Emergency profile"
  aria-label="Emergency profile"
>
  <Heart className="w-4 h-4" />
  <span className="hidden sm:inline text-xs">
    {isProfileComplete ? 'Emergency Info' : 'Set Emergency Info'}
  </span>
</motion.button>

// And render the modal at the bottom of the component:
<EmergencyProfileModal
  open={emergencyProfileOpen}
  onOpenChange={setEmergencyProfileOpen}
  profile={emergencyProfile}
  onSave={setEmergencyProfile}
/>
```

The button pulses red when the profile is incomplete to nudge the user to fill it in.

---

## Part 2 — One-Tap VAPI Call from Emergency Grid

### 2.1 Current Flow (Remove This)

```
Click "Emergency" tab → see numbers grid → click separate "Call with LUMOS AI (VAPI)" button
  → modal opens → fill form → 10s countdown → call starts
```

### 2.2 New Flow

```
Click "Emergency" tab → see numbers grid
  → tap the "Emergency (US) 911" card
    → if profile incomplete: toast "Set your Emergency Info first" + open profile modal
    → if profile complete: immediately start VAPI call (no countdown, no form)
    → show floating active-call bar
```

### 2.3 Changes to `EmergencyResources.tsx`

The 911 card needs an `onClick` handler that **does not** navigate to `tel:911` but instead fires the VAPI call. Other numbers (311, 988, etc.) keep their `tel:` links.

```tsx
// EmergencyResources.tsx — updated props
interface EmergencyResourcesProps {
  locationName: string;
  numbers?: EmergencyNumber[];
  expanded?: boolean;
  onCall911?: () => void; // NEW — fires VAPI call
}
```

Inside the grid mapping:

```tsx
{resources.map((r) => {
  const is911 = r.number === '911';

  if (is911 && onCall911) {
    return (
      <button
        key={r.number}
        onClick={onCall911}
        className="flex items-center gap-1.5 bg-red-500/20 border border-red-500/40
                   rounded-lg px-2 sm:px-2.5 py-2 sm:py-2.5 hover:bg-red-500/30
                   active:bg-red-500/40 transition-colors group min-h-[44px]"
      >
        <r.icon className={`w-3.5 h-3.5 text-lumos-danger flex-shrink-0`} />
        <div className="min-w-0">
          <p className="text-[10px] text-muted-foreground truncate">{r.label}</p>
          <p className="text-xs font-medium text-lumos-danger">
            {r.number} · LUMOS AI
          </p>
        </div>
      </button>
    );
  }

  return (
    <a key={r.number} href={`tel:${r.number}`} className="...existing classes...">
      {/* ...existing content... */}
    </a>
  );
})}
```

### 2.4 Changes to `Index.tsx`

Remove:
- The separate "Call with LUMOS AI (VAPI)" button rendered after `<EmergencyResources>`.
- The `<EmergencyCallModal>` component and its state entirely (we replace it with the floating bar + hook).

Add:
- Pass `onCall911` to every `<EmergencyResources>` instance.
- The `onCall911` handler reads the emergency profile, checks completeness, and calls `startEmergencyCall()`.

```tsx
// In Index component:
const [activeCallId, setActiveCallId] = useState<string | null>(null);
const [callElapsed, setCallElapsed] = useState(0);

const handleCall911 = useCallback(async () => {
  if (!isProfileComplete) {
    toast.error('Please set your emergency info first', {
      action: { label: 'Set now', onClick: () => setEmergencyProfileOpen(true) },
    });
    return;
  }

  // Get current location (best effort — fall back to searched location)
  let lat = locationCoords?.lat ?? 0;
  let lng = locationCoords?.lng ?? 0;
  try {
    const pos = await new Promise<GeolocationPosition>((resolve, reject) =>
      navigator.geolocation.getCurrentPosition(resolve, reject, {
        enableHighAccuracy: true, timeout: 5000, maximumAge: 10000,
      })
    );
    lat = pos.coords.latitude;
    lng = pos.coords.longitude;
  } catch {
    // Use searched location as fallback
  }

  toast.info('Starting emergency call...', { duration: 2000 });

  try {
    const res = await startEmergencyCall({
      callerName: emergencyProfile.name,
      callerAge: emergencyProfile.age || undefined,
      lat,
      lng,
      address: locationName || undefined,
      safetyScore: safetyData?.safetyIndex ?? 0,
      incidentType: emergencyProfile.defaultIncidentType,
      severity: emergencyProfile.defaultSeverity,
      userNotes: emergencyProfile.medicalConditions
        ? `Medical: ${emergencyProfile.medicalConditions}`
        : undefined,
    });
    setActiveCallId(res.callId);
    setCallElapsed(0);
    toast.success('Emergency call started', {
      description: 'LUMOS AI is speaking to the operator.',
    });
  } catch (e) {
    toast.error('Could not start call', {
      description: e instanceof Error ? e.message : 'Check your connection',
    });
  }
}, [emergencyProfile, isProfileComplete, locationCoords, locationName, safetyData]);
```

Pass it down:

```tsx
<EmergencyResources
  locationName={locationName}
  numbers={safetyData.emergencyNumbers}
  expanded={activePanel === 'emergency'}
  onCall911={handleCall911}           // <-- NEW
/>
```

---

## Part 3 — Active-Call Floating Bar (replaces modal)

### 3.1 Why

A full-screen modal is bad UX for emergencies:
- Blocks the map (the user might need to see their surroundings).
- Requires dismissing the modal to do anything else.
- Adds friction in a high-stress moment.

Instead, show a **slim floating bar** fixed to the top or bottom of the viewport.

### 3.2 New File: `src/components/ActiveCallBar.tsx`

```tsx
import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { PhoneOff, Send, MapPin } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { sendEmergencyCallUpdate, endEmergencyCall } from '@/lib/api';
import { toast } from 'sonner';

interface ActiveCallBarProps {
  callId: string;
  elapsed: number;                       // seconds
  onEnd: () => void;
  lat: number;
  lng: number;
}

export default function ActiveCallBar({ callId, elapsed, onEnd, lat, lng }: ActiveCallBarProps) {
  const [updateText, setUpdateText] = useState('');
  const [sending, setSending] = useState(false);
  const [currentLat, setCurrentLat] = useState(lat);
  const [currentLng, setCurrentLng] = useState(lng);
  const locationIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 30-second GPS tracker — sends location to VAPI agent
  useEffect(() => {
    const sendLocation = () => {
      if (!navigator.geolocation) return;
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const { latitude, longitude } = pos.coords;
          setCurrentLat(latitude);
          setCurrentLng(longitude);
          const msg = `LOCATION UPDATE: Caller is now at ${latitude.toFixed(6)}, ${longitude.toFixed(6)}.`;
          sendEmergencyCallUpdate(callId, msg).catch(() => {});
        },
        () => {},
        { enableHighAccuracy: true, maximumAge: 15000, timeout: 5000 }
      );
    };

    // Send immediately, then every 30s
    sendLocation();
    locationIntervalRef.current = setInterval(sendLocation, 30_000);

    return () => {
      if (locationIntervalRef.current) clearInterval(locationIntervalRef.current);
    };
  }, [callId]);

  const handleSend = async () => {
    const text = updateText.trim();
    if (!text || sending) return;
    setSending(true);
    try {
      await sendEmergencyCallUpdate(callId, text);
      setUpdateText('');
      toast.success('Update sent');
    } catch {
      toast.error('Failed to send');
    } finally {
      setSending(false);
    }
  };

  const handleEnd = async () => {
    try {
      await endEmergencyCall(callId);
      toast.info('Call ended');
    } catch {
      toast.error('Could not end call');
    }
    onEnd();
  };

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  return (
    <motion.div
      initial={{ y: -80, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      exit={{ y: -80, opacity: 0 }}
      className="fixed top-16 left-1/2 -translate-x-1/2 z-50 w-[95vw] max-w-lg"
    >
      <div className="bg-red-950/95 backdrop-blur-xl border border-red-500/40 rounded-2xl px-4 py-3 shadow-2xl shadow-red-900/30">
        {/* Row 1: status + duration + end button */}
        <div className="flex items-center justify-between gap-3 mb-2">
          <div className="flex items-center gap-2">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500" />
            </span>
            <span className="text-sm font-semibold text-red-200">EMERGENCY CALL ACTIVE</span>
          </div>
          <span className="text-lg font-mono font-bold text-white tabular-nums">{formatTime(elapsed)}</span>
          <Button
            size="sm"
            variant="destructive"
            onClick={handleEnd}
            className="gap-1.5"
          >
            <PhoneOff className="w-4 h-4" />
            End
          </Button>
        </div>

        {/* Row 2: location badge */}
        <div className="flex items-center gap-1.5 text-xs text-red-300 mb-2">
          <MapPin className="w-3 h-3" />
          <span>
            Live GPS: {currentLat.toFixed(5)}, {currentLng.toFixed(5)} · updating every 30s
          </span>
        </div>

        {/* Row 3: quick update input */}
        <div className="flex gap-2">
          <Input
            value={updateText}
            onChange={(e) => setUpdateText(e.target.value)}
            placeholder="Send update to operator..."
            className="bg-red-900/50 border-red-500/30 text-white placeholder:text-red-400/60 text-sm"
            onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleSend())}
          />
          <Button
            size="icon"
            variant="secondary"
            onClick={handleSend}
            disabled={!updateText.trim() || sending}
            className="bg-red-800/60 hover:bg-red-700/60"
          >
            <Send className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </motion.div>
  );
}
```

### 3.3 Rendering in `Index.tsx`

```tsx
import ActiveCallBar from '@/components/ActiveCallBar';

// Near the bottom of the JSX, alongside other overlays:
<AnimatePresence>
  {activeCallId && (
    <ActiveCallBar
      callId={activeCallId}
      elapsed={callElapsed}
      onEnd={() => { setActiveCallId(null); setCallElapsed(0); }}
      lat={locationCoords?.lat ?? 0}
      lng={locationCoords?.lng ?? 0}
    />
  )}
</AnimatePresence>
```

And the elapsed timer in `Index.tsx`:

```tsx
useEffect(() => {
  if (!activeCallId) return;
  const interval = setInterval(() => setCallElapsed((e) => e + 1), 1000);
  return () => clearInterval(interval);
}, [activeCallId]);
```

---

## Part 4 — Live Location Tracking During Call

### 4.1 How It Works

The `ActiveCallBar` component already handles this (see the `useEffect` in section 3.2):

1. **On call start**: Immediately grab GPS and send a `LOCATION UPDATE` message to the VAPI call via `sendEmergencyCallUpdate()`.
2. **Every 30 seconds**: Re-grab GPS and send another update.
3. **On call end**: Clear the interval.

The VAPI agent receives these as injected messages and can inform the "operator":

> "The caller has moved. Their current location is 33.749, -84.388."

### 4.2 Geolocation Permissions

The app should request geolocation permission **early** (e.g., when the user first searches a location or clicks "My location"). If permission is denied during an emergency call, fall back to the last-known coordinates from the map.

### 4.3 Enhancing the Firebase Function

Currently `emergencyCallMessage` is a no-op (it returns `{ ok: true }` without actually injecting the message into the VAPI call). To make location updates actually reach the operator, you have two options:

#### Option A: VAPI Say API (Recommended)

VAPI has a [Say endpoint](https://docs.vapi.ai/api-reference/calls/say) that injects a message into an active call:

```javascript
// In functions/index.js — emergencyCallMessage
exports.emergencyCallMessage = onCall(async (request) => {
  const { callId, message } = request.data || {};
  if (!callId || !message) {
    throw new HttpsError("invalid-argument", "callId and message required");
  }

  const vapiKey = env("VAPI_API_KEY");
  if (!vapiKey) {
    throw new HttpsError("failed-precondition", "VAPI_API_KEY not set");
  }

  // Use VAPI's "say" endpoint to inject the message into the live call
  const res = await fetch(`https://api.vapi.ai/call/${callId}/say`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${vapiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message: message,
    }),
  });

  if (!res.ok) {
    const errText = await res.text();
    console.error(`VAPI say failed: ${res.status} ${errText}`);
    // Don't throw — location updates are best-effort
  }

  return { ok: true };
});
```

#### Option B: Append to System Prompt Context

If VAPI doesn't support the Say API on your plan, you can store location updates in Firestore and have the `vapiLlm` function prepend them to the conversation context on each turn:

```javascript
// In vapiLlm, before generating with Gemini:
const locationUpdates = await getLocationUpdates(callId); // from Firestore
if (locationUpdates.length > 0) {
  const locationContext = locationUpdates
    .map(u => `[${u.timestamp}] ${u.message}`)
    .join('\n');
  // Inject as a system-level context into the messages array
  messages.unshift({
    role: 'system',
    content: `Recent location updates from the caller:\n${locationContext}`,
  });
}
```

### 4.4 Location Update Display in the Call Bar

The floating call bar shows the user's current coordinates and a "updating every 30s" label so the user knows their location is being shared. This serves as both a privacy indicator and reassurance that help knows where they are.

### 4.5 Map Marker During Call

Optionally, during an active call, pulse a red marker on the map at the user's live GPS position (updated every 30s). This uses the existing `updateUserMarker()` utility from `heatmap.ts`.

---

## Part 5 — VAPI Agent / Firebase Function Changes

### 5.1 Enhanced System Prompt

Update the `firstMessage` construction in `startEmergencyCall` to include medical info and emergency contact from the profile:

```javascript
const firstMessage = [
  `You are LUMOS AI, speaking on behalf of a caller in an emergency.`,
  `Caller name: ${callerName || "Unknown"}.`,
  callerAge ? `Age: ${callerAge}.` : "",
  `Location: ${address || "Unknown"} (lat ${lat}, lng ${lng}).`,
  `Safety score at location: ${safetyScore ?? "unknown"}.`,
  `Incident type: ${incidentType || "unspecified"}. Severity: ${severity || "HIGH"}.`,
  userNotes ? `Caller notes: ${userNotes}.` : "",
  medicalConditions ? `Medical conditions: ${medicalConditions}.` : "",            // NEW
  emergencyContactName ? `Emergency contact: ${emergencyContactName}` +
    (emergencyContactPhone ? ` (${emergencyContactPhone})` : "") + "." : "",       // NEW
  movementDirection ? `Direction: ${movementDirection}.` : "",
  movementSpeed ? `Speed: ${movementSpeed}.` : "",
  `You will receive periodic LOCATION UPDATE messages with the caller's GPS coordinates. ` +
  `When you receive one, inform the operator of the caller's updated location.`,    // NEW
  `Speak clearly and concisely to the 911 operator. Answer their questions. Keep responses brief.`,
].filter(Boolean).join(" ");
```

### 5.2 Updated `EmergencyCallPayload`

Add optional fields to the payload interface:

```typescript
// In src/lib/api.ts
export interface EmergencyCallPayload {
  callerName: string;
  callerAge?: string;
  lat: number;
  lng: number;
  address?: string;
  safetyScore: number;
  incidentType: string;
  severity: string;
  userNotes?: string;
  medicalConditions?: string;         // NEW
  emergencyContactName?: string;      // NEW
  emergencyContactPhone?: string;     // NEW
  movementDirection?: string;
  movementSpeed?: string;
}
```

### 5.3 Firebase Function Payload Destructuring

Update the `startEmergencyCall` function in `functions/index.js` to read the new fields:

```javascript
const {
  callerName, callerAge, lat, lng, address, safetyScore,
  incidentType, severity, userNotes,
  medicalConditions,              // NEW
  emergencyContactName,           // NEW
  emergencyContactPhone,          // NEW
  movementDirection, movementSpeed,
} = payload;
```

---

## Part 6 — File-by-File Changelist

| File | Action | What to do |
|------|--------|------------|
| `src/hooks/useEmergencyProfile.ts` | **CREATE** | New hook for reading/writing emergency profile (localStorage + Firestore). Full code in Part 1.3. |
| `src/components/EmergencyProfileModal.tsx` | **CREATE** | New modal for editing emergency profile. Full code in Part 1.3. |
| `src/components/ActiveCallBar.tsx` | **CREATE** | New floating call-status bar with GPS tracker. Full code in Part 3.2. |
| `src/components/EmergencyResources.tsx` | **MODIFY** | Add `onCall911` prop. Make the 911 card a `<button>` that calls it instead of an `<a href="tel:911">`. Other numbers keep `tel:` links. |
| `src/pages/Index.tsx` | **MODIFY** | 1) Import new components/hooks. 2) Add emergency profile state + header button. 3) Add `handleCall911` callback. 4) Pass `onCall911` to all `<EmergencyResources>` instances. 5) Remove the separate "Call with LUMOS AI" buttons (2 of them — desktop + mobile). 6) Remove `<EmergencyCallModal>` and its state. 7) Add `<ActiveCallBar>` with `activeCallId` state. 8) Add elapsed timer `useEffect`. 9) Render `<EmergencyProfileModal>`. |
| `src/components/EmergencyCallModal.tsx` | **DELETE** | No longer needed. All its logic is replaced by `handleCall911` + `ActiveCallBar`. |
| `src/lib/api.ts` | **MODIFY** | Add `medicalConditions`, `emergencyContactName`, `emergencyContactPhone` to `EmergencyCallPayload`. |
| `functions/index.js` | **MODIFY** | 1) Destructure new payload fields in `startEmergencyCall`. 2) Add them to the system prompt. 3) Implement VAPI Say API in `emergencyCallMessage` so location updates reach the operator. |

---

## Part 7 — Data Flow Diagrams

### 7.1 One-Tap Call Flow

```
User taps "Emergency (US) 911" card
        │
        ▼
  isProfileComplete?
    ├── NO → toast("Set your Emergency Info first")
    │        → open EmergencyProfileModal
    │
    └── YES
         │
         ▼
   navigator.geolocation.getCurrentPosition()
         │
         ▼
   startEmergencyCall({
     name, age, lat, lng, address,
     safetyScore, incidentType, severity,
     medicalConditions, emergencyContact
   })
         │
         ▼
   Firebase Function: startEmergencyCall
     → builds system prompt with all profile data
     → POST https://api.vapi.ai/call
     → returns { callId }
         │
         ▼
   setActiveCallId(callId)
   → renders <ActiveCallBar>
   → starts 30s GPS interval
   → starts elapsed timer
```

### 7.2 Location Update Flow (every 30 seconds)

```
setInterval(30_000)
    │
    ▼
navigator.geolocation.getCurrentPosition()
    │
    ▼
sendEmergencyCallUpdate(callId, "LOCATION UPDATE: lat, lng")
    │
    ▼
Firebase Function: emergencyCallMessage
    │
    ▼
POST https://api.vapi.ai/call/{callId}/say
  body: { message: "The caller has moved to lat, lng" }
    │
    ▼
VAPI agent speaks updated location to the operator
```

### 7.3 User-Initiated Update Flow

```
User types "I'm in the stairwell" → presses Enter / Send
    │
    ▼
sendEmergencyCallUpdate(callId, "I'm in the stairwell")
    │
    ▼
Firebase Function: emergencyCallMessage
    │
    ▼
VAPI Say API → agent relays to operator
```

### 7.4 End Call Flow

```
User taps "End" button on ActiveCallBar
    │
    ▼
endEmergencyCall(callId)
    │
    ▼
Firebase Function: emergencyCallEnd
  → (optionally hang up VAPI call via API)
    │
    ▼
setActiveCallId(null) → ActiveCallBar unmounts
  → GPS interval cleared
  → elapsed timer cleared
```

---

## Part 8 — Testing Checklist

### 8.1 Emergency Profile

- [ ] Profile modal opens from header button.
- [ ] Saving writes to localStorage (verify in DevTools → Application → Local Storage).
- [ ] Signed-in user: data syncs to Firestore (`users/{uid}/settings/emergencyProfile`).
- [ ] Reloading the page restores profile from localStorage.
- [ ] Signing in on a new device loads from Firestore.
- [ ] Header button shows green when profile is complete, red/pulsing when incomplete.

### 8.2 One-Tap Call

- [ ] Tapping "Emergency (US) 911" with incomplete profile shows toast + opens profile modal.
- [ ] Tapping "Emergency (US) 911" with complete profile immediately starts call (no countdown, no form).
- [ ] Call starts successfully (toast confirms callId).
- [ ] `ActiveCallBar` appears at top of screen.
- [ ] Other emergency numbers (311, 988) still open the phone dialer.

### 8.3 Active Call Bar

- [ ] Shows pulsing red dot + "EMERGENCY CALL ACTIVE" label.
- [ ] Duration counter increments every second.
- [ ] User can type an update and send it (toast confirms).
- [ ] "End" button ends the call and hides the bar.
- [ ] Map is still usable behind the bar (not blocked by a modal).

### 8.4 Location Tracking

- [ ] On call start, first GPS position is obtained and sent.
- [ ] Every 30 seconds, a new position is sent (check Firebase Function logs for `emergencyCallMessage` invocations).
- [ ] The bar shows "Live GPS: lat, lng · updating every 30s".
- [ ] If geolocation is denied, falls back to searched location coordinates.
- [ ] On call end, the interval is cleared (no more updates after hanging up).

### 8.5 Firebase Functions

- [ ] `startEmergencyCall` receives `medicalConditions`, `emergencyContactName`, `emergencyContactPhone` and includes them in the system prompt.
- [ ] `emergencyCallMessage` calls VAPI Say API (check response status in logs).
- [ ] `vapiLlm` still works for multi-turn conversation with the operator.

### 8.6 Edge Cases

- [ ] No location searched yet (landing page) → `handleCall911` still works using GPS only.
- [ ] GPS not available → uses `locationCoords` from the last search.
- [ ] Network error starting call → shows toast with error message.
- [ ] Double-tapping 911 → second tap is no-op while first call is starting (add a `isStartingCall` guard).
- [ ] Call active + user navigates to a different location → bar stays visible, GPS continues.

---

## Appendix A — VAPI Say API Reference

The VAPI Say API lets you inject a spoken message into an active call:

```
POST https://api.vapi.ai/call/{callId}/say
Authorization: Bearer {VAPI_API_KEY}
Content-Type: application/json

{
  "message": "The caller has moved to 33.749, -84.388."
}
```

If this endpoint is not available on your VAPI plan, use **Option B** from Part 4.3 (Firestore context injection).

Check VAPI docs at https://docs.vapi.ai for the latest endpoint paths.

---

## Appendix B — Race Condition Guard

To prevent double-tapping from starting two calls:

```tsx
const isStartingCallRef = useRef(false);

const handleCall911 = useCallback(async () => {
  if (isStartingCallRef.current || activeCallId) return; // Already calling or call active
  isStartingCallRef.current = true;

  try {
    // ... existing logic ...
  } finally {
    isStartingCallRef.current = false;
  }
}, [/* deps */]);
```

---

## Appendix C — Optional Enhancements

### C.1 Haptic Feedback on Call Start

```tsx
if (navigator.vibrate) navigator.vibrate([100, 50, 100]); // vibrate pattern
```

### C.2 Wake Lock (Prevent Screen Sleep During Call)

```tsx
useEffect(() => {
  if (!activeCallId) return;
  let wakeLock: WakeLockSentinel | null = null;
  const acquire = async () => {
    try {
      wakeLock = await navigator.wakeLock.request('screen');
    } catch {}
  };
  acquire();
  return () => { wakeLock?.release(); };
}, [activeCallId]);
```

### C.3 Audio Feedback

Play a short tone when the call connects so the user knows it's active even if they're not looking at the screen:

```tsx
const audio = new Audio('/sounds/call-started.mp3');
audio.play().catch(() => {});
```

### C.4 Emergency Contact SMS (Future)

When a call starts, automatically send the user's emergency contact a text message with their location via Twilio or Firebase Cloud Messaging. This would require a new Firebase Function and Twilio integration.

### C.5 Persistent Call State

If the user accidentally closes the browser tab during a call, the call continues on the VAPI/phone side. On reload, check Firestore for active calls belonging to this user and re-show the `ActiveCallBar`. This requires storing `callId` + `userId` in Firestore in `startEmergencyCall`.

---

## Summary of Removals

| What | Where | Why |
|------|-------|-----|
| `EmergencyCallModal.tsx` | `src/components/` | Replaced by `handleCall911` + `ActiveCallBar` |
| `emergencyCallModalOpen` state | `Index.tsx` | No modal anymore |
| "Call with LUMOS AI (VAPI)" buttons (×2) | `Index.tsx` (desktop + mobile) | 911 card itself triggers the call |
| Form step (name/age/incident/severity/notes) | `EmergencyCallModal.tsx` | Pre-configured in Emergency Profile |
| 10-second countdown | `EmergencyCallModal.tsx` | Removed — immediate call |

## Summary of Additions

| What | Where | Purpose |
|------|-------|---------|
| `useEmergencyProfile` hook | `src/hooks/` | Read/write emergency profile from localStorage + Firestore |
| `EmergencyProfileModal` | `src/components/` | UI for editing profile |
| `ActiveCallBar` | `src/components/` | Non-blocking call status + GPS tracker |
| Header "Emergency Info" button | `Index.tsx` header | Opens profile modal |
| `onCall911` prop | `EmergencyResources.tsx` | Intercepts 911 card tap |
| VAPI Say API call | `functions/index.js` | Injects location updates into live call |
| New payload fields | `api.ts` + `functions/index.js` | Medical info + emergency contact |
