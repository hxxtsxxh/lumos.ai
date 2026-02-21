export interface SafetyData {
  safetyIndex: number;
  riskLevel: 'safe' | 'caution' | 'danger';
  incidentTypes: IncidentType[];
  timeAnalysis: TimeAnalysis;
  dataSources: DataSource[];
}

export interface LiveIncident {
  type: string;
  date: string;
  lat: number;
  lng: number;
  distance_miles: number;
  source: string;
  severity: string;
  headline: string;
}

export interface IncidentType {
  type: string;
  probability: number;
  icon: string;
  crimeLevel?: string;
}

export interface TimeAnalysis {
  currentRisk: number;
  peakHours: string;
  safestHours: string;
}

export interface DataSource {
  name: string;
  lastUpdated: string;
  recordCount: number;
}

export interface WeatherInfo {
  condition: string;       // e.g. "Rain", "Clear", "Snow"
  description: string;     // e.g. "light rain", "clear sky"
  icon: string;            // OWM icon code e.g. "10d"
  temp_celsius: number | null;
  humidity: number | null;
  wind_speed: number | null;  // m/s
  alert_count: number;
}

export interface TravelParams {
  peopleCount: number;
  gender: 'male' | 'female' | 'mixed' | 'prefer-not-to-say';
  timeOfTravel: string;
  duration: number; // in minutes
  mode: 'walking' | 'driving' | 'transit';
}

// ─── Route Analysis ───
export interface RouteSegment {
  startLat: number;
  startLng: number;
  endLat: number;
  endLng: number;
  safetyScore: number;
  riskLevel: 'safe' | 'caution' | 'danger';
}

export interface RouteAnalysisData {
  overallSafety: number;
  riskLevel: 'safe' | 'caution' | 'danger';
  segments: RouteSegment[];
  distance: string;
  duration: string;
  polyline: number[][];  // [[lat, lng], ...]
  warnings: string[];
}

// ─── Nearby Safe Places ───
export interface NearbyPOI {
  name: string;
  type: 'police' | 'hospital' | 'fire_station';
  lat: number;
  lng: number;
  distance: number;
  address: string;
}

// ─── Historical Trends ───
export interface HistoricalDataPoint {
  year: number;
  violentCrime: number;
  propertyCrime: number;
  total: number;
}

export interface HistoricalTrend {
  state: string;
  data: HistoricalDataPoint[];
}

// ─── User Reports ───
export interface UserReport {
  id?: string;
  lat: number;
  lng: number;
  type: string;
  description: string;
  severity: 'low' | 'medium' | 'high';
  timestamp: string;
  userId?: string;
}
