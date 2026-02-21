import {
  collection,
  addDoc,
  query,
  where,
  orderBy,
  getDocs,
  deleteDoc,
  doc,
  serverTimestamp,
} from 'firebase/firestore';
import { db } from '@/lib/firebase';
import type { SafetyData, TravelParams } from '@/types/safety';

export interface SavedReport {
  id: string;
  userId: string;
  locationName: string;
  lat: number;
  lng: number;
  safetyIndex: number;
  riskLevel: string;
  params: TravelParams;
  data: SafetyData;
  createdAt: Date;
}

const COLLECTION = 'saved_reports';

export async function saveReport(
  userId: string,
  locationName: string,
  lat: number,
  lng: number,
  params: TravelParams,
  data: SafetyData
): Promise<string> {
  const docRef = await addDoc(collection(db, COLLECTION), {
    userId,
    locationName,
    lat,
    lng,
    safetyIndex: data.safetyIndex,
    riskLevel: data.riskLevel,
    params,
    data,
    createdAt: serverTimestamp(),
  });
  return docRef.id;
}

export async function getUserReports(userId: string): Promise<SavedReport[]> {
  const q = query(
    collection(db, COLLECTION),
    where('userId', '==', userId),
    orderBy('createdAt', 'desc')
  );
  const snapshot = await getDocs(q);
  return snapshot.docs.map((d) => ({
    id: d.id,
    ...d.data(),
    createdAt: d.data().createdAt?.toDate() || new Date(),
  })) as SavedReport[];
}

export async function deleteReport(reportId: string): Promise<void> {
  await deleteDoc(doc(db, COLLECTION, reportId));
}
