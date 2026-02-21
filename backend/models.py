"""Lumos Backend — Pydantic Models"""

from typing import Optional
from pydantic import BaseModel, Field


class SafetyRequest(BaseModel):
    lat: float
    lng: float
    peopleCount: int = 1
    gender: str = "prefer-not-to-say"
    timeOfTravel: str = "12:00"
    duration: int = 60
    locationName: Optional[str] = ""


class RouteRequest(BaseModel):
    originLat: float
    originLng: float
    destLat: float
    destLng: float
    peopleCount: int = 1
    gender: str = "prefer-not-to-say"
    timeOfTravel: str = "12:00"
    mode: str = "walking"  # walking, driving, transit


class UserReport(BaseModel):
    lat: float
    lng: float
    category: str  # unsafe_area, poor_lighting, harassment, theft, other
    description: str = ""
    severity: int = Field(default=3, ge=1, le=5)


class IncidentType(BaseModel):
    type: str
    probability: float
    icon: str
    crimeLevel: str = ""  # e.g. "Low", "Moderate", "High" — overall crime context


class TimeAnalysis(BaseModel):
    currentRisk: float
    peakHours: str
    safestHours: str


class DataSource(BaseModel):
    name: str
    lastUpdated: str
    recordCount: int


class HourlyRisk(BaseModel):
    hour: str
    risk: float


class HeatmapPoint(BaseModel):
    lat: float
    lng: float
    weight: float
    type: str = "Unknown"
    description: str = ""
    date: Optional[str] = None
    source: str = ""


class NearbyPOI(BaseModel):
    name: str
    type: str  # police, hospital, fire_station
    lat: float
    lng: float
    distance: float  # meters
    icon: str
    address: str = ""


class RouteSegment(BaseModel):
    startLat: float
    startLng: float
    endLat: float
    endLng: float
    safetyScore: int
    riskLevel: str


class HistoricalDataPoint(BaseModel):
    year: int
    violentCrime: int
    propertyCrime: int
    total: int
    population: int
    ratePerCapita: float


class WeatherInfo(BaseModel):
    condition: str          # e.g. "Rain", "Clear", "Snow"
    description: str = ""   # e.g. "light rain", "clear sky"
    icon: str = "01d"       # OWM icon code
    temp_celsius: float | None = None
    humidity: int | None = None
    wind_speed: float | None = None  # m/s
    alert_count: int = 0


class LiveIncident(BaseModel):
    type: str
    date: str = ""
    lat: float = 0.0
    lng: float = 0.0
    distance_miles: float = 0.0
    source: str = ""
    severity: str = ""
    headline: str = ""


class SafetyResponse(BaseModel):
    safetyIndex: int
    riskLevel: str
    incidentTypes: list[IncidentType]
    timeAnalysis: TimeAnalysis
    dataSources: list[DataSource]
    hourlyRisk: list[HourlyRisk]
    heatmapPoints: list[HeatmapPoint]
    heatmapIncidentCount: int = 0
    emergencyNumbers: list[dict]
    nearbyPOIs: list[NearbyPOI] = []
    weather: WeatherInfo | None = None
    liveIncidents: list[LiveIncident] = []
    sentimentSummary: str = ""
    neighborhoodContext: str = ""


class RouteResponse(BaseModel):
    overallSafety: int
    riskLevel: str
    segments: list[RouteSegment]
    polyline: list[list[float]]  # [[lat, lng], ...]
    warnings: list[str]
    estimatedDuration: str
    estimatedDistance: str
    # Rich data (optional — won't break existing clients)
    incidentTypes: list[IncidentType] = []
    timeAnalysis: Optional[TimeAnalysis] = None
    hourlyRisk: list[HourlyRisk] = []
    dataSources: list[DataSource] = []


class HistoricalResponse(BaseModel):
    state: str
    data: list[HistoricalDataPoint]
    trend: str  # increasing, decreasing, stable


class UserReportResponse(BaseModel):
    id: str
    status: str


class AISafetyTipsRequest(BaseModel):
    locationName: str
    safetyIndex: float
    incidentTypes: list[str] = []
    timeOfTravel: str = "12:00"
    peopleCount: int = 1
    gender: str = "prefer-not-to-say"
    liveIncidentSummary: str = ""
    nearbyPOIs: list[str] = []
    neighborhoodContext: str = ""
    sentimentSummary: str = ""
