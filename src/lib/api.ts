import type { SafetyData, TravelParams, RouteAnalysisData, NearbyPOI, HistoricalTrend, UserReport } from '@/types/safety';
import { API_BASE_URL, MAPBOX_TOKEN, GOOGLE_MAPS_API_KEY } from '@/lib/config';

export interface HeatmapPoint {
  lat: number;
  lng: number;
  weight: number;
  type?: string;
  description?: string;
  date?: string;  // Most recent incident date in this cell/point
}

export interface HourlyRiskData {
  hour: string;
  risk: number;
}

export interface EmergencyNumber {
  label: string;
  number: string;
  icon: string;
  color: string;
}

export interface FullSafetyResponse extends SafetyData {
  hourlyRisk: HourlyRiskData[];
  heatmapPoints: HeatmapPoint[];
  heatmapIncidentCount?: number;
  emergencyNumbers: EmergencyNumber[];
  nearbyPOIs?: NearbyPOI[];
  weather?: import('@/types/safety').WeatherInfo;
}

export async function fetchSafetyScore(
  lat: number,
  lng: number,
  params: TravelParams,
  locationName: string = ''
): Promise<FullSafetyResponse> {
  const res = await fetch(`${API_BASE_URL}/api/safety`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lat, lng, ...params, locationName }),
  });
  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}`);
  }
  return await res.json();
}

export async function geocodeLocation(
  query: string
): Promise<{ lat: number; lng: number; name: string } | null> {
  // Primary: Google Maps Geocoding API
  try {
    const res = await fetch(
      `https://maps.googleapis.com/maps/api/geocode/json?address=${encodeURIComponent(query)}&key=${GOOGLE_MAPS_API_KEY}`
    );
    const data = await res.json();
    if (data.status === 'OK' && data.results?.length) {
      const loc = data.results[0].geometry.location;
      return { lat: loc.lat, lng: loc.lng, name: data.results[0].formatted_address };
    }
  } catch {
    // fall through to Mapbox fallback
  }

  // Fallback: Mapbox Geocoding
  try {
    const res = await fetch(
      `https://api.mapbox.com/geocoding/v5/mapbox.places/${encodeURIComponent(query)}.json?access_token=${MAPBOX_TOKEN}&limit=1`
    );
    const data = await res.json();
    if (data.features?.length) {
      const [lng, lat] = data.features[0].center;
      return { lat, lng, name: data.features[0].place_name };
    }
  } catch {
    // fall through
  }
  return null;
}

// ─── Citizen live incidents ───
export async function fetchCitizenHotspots(bounds: {
  lowerLatitude: number;
  lowerLongitude: number;
  upperLatitude: number;
  upperLongitude: number;
}): Promise<HeatmapPoint[]> {
  try {
    const params = new URLSearchParams({
      lowerLatitude: bounds.lowerLatitude.toString(),
      lowerLongitude: bounds.lowerLongitude.toString(),
      upperLatitude: bounds.upperLatitude.toString(),
      upperLongitude: bounds.upperLongitude.toString(),
      limit: '200',
    });
    const res = await fetch(`${API_BASE_URL}/api/citizen-hotspots?${params}`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.incidents || [];
  } catch {
    return [];
  }
}

// ─── Autocomplete search ───
export async function fetchAutocomplete(
  query: string
): Promise<Array<{ description: string; placeId: string }>> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/autocomplete?query=${encodeURIComponent(query)}`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.suggestions || [];
  } catch {
    return [];
  }
}

// ─── Route safety analysis ───
export async function fetchRouteAnalysis(
  originLat: number,
  originLng: number,
  destLat: number,
  destLng: number,
  params?: TravelParams,
  mode: string = 'walking'
): Promise<RouteAnalysisData> {
  const res = await fetch(`${API_BASE_URL}/api/route`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      originLat, originLng, destLat, destLng, mode,
      ...(params ? { peopleCount: params.peopleCount, gender: params.gender, timeOfTravel: params.timeOfTravel } : {}),
    }),
  });
  if (!res.ok) throw new Error(`Route analysis failed: ${res.status}`);
  return await res.json();
}

// ─── Historical crime trends ───
export async function fetchHistoricalTrends(state: string): Promise<HistoricalTrend> {
  const res = await fetch(`${API_BASE_URL}/api/historical?state=${encodeURIComponent(state)}`);
  if (!res.ok) throw new Error(`Historical data failed: ${res.status}`);
  return await res.json();
}

// ─── Nearby safe places (POIs) ───
export async function fetchNearbyPOIs(lat: number, lng: number): Promise<NearbyPOI[]> {
  const res = await fetch(`${API_BASE_URL}/api/nearby-pois?lat=${lat}&lng=${lng}`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.pois || [];
}

// ─── User reports ───
export async function submitUserReport(report: UserReport): Promise<{ id: string; status: string }> {
  // Map frontend fields to backend model
  const severityMap: Record<string, number> = { low: 2, medium: 3, high: 5 };
  const res = await fetch(`${API_BASE_URL}/api/reports`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      lat: report.lat,
      lng: report.lng,
      category: report.type,
      description: report.description,
      severity: severityMap[report.severity] ?? 3,
    }),
  });
  if (!res.ok) throw new Error(`Report submission failed: ${res.status}`);
  return await res.json();
}

export async function fetchUserReports(lat: number, lng: number, radius: number = 5): Promise<UserReport[]> {
  const res = await fetch(`${API_BASE_URL}/api/reports?lat=${lat}&lng=${lng}&radius_km=${radius}`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.reports || [];
}

// ─── Safety Chat (Conversational Q&A) ───
export async function sendSafetyChatMessage(payload: {
  message: string;
  locationName: string;
  safetyIndex: number | null;
  incidentTypes: string[];
  riskLevel: string;
  timeOfTravel: string;
  conversationHistory: { role: 'user' | 'assistant'; content: string }[];
}): Promise<{ reply: string; error: string | null }> {
  const res = await fetch(`${API_BASE_URL}/api/safety-chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Chat request failed: ${res.status}`);
  return res.json();
}
