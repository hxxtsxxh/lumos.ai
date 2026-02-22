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
  demoPhoneNumber: string;
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
  demoPhoneNumber: '',
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

  // On mount or user change, try to load from Firestore (prefer cloud data)
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
