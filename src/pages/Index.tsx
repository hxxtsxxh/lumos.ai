import { useState, useCallback, useRef, useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import mapboxgl from 'mapbox-gl';
import GlobeView, { flyToLocation, pauseGlobeRotation } from '@/components/GlobeView';
import RouteSearchBar, { type SearchMode } from '@/components/RouteSearchBar';
import ParameterPanel from '@/components/ParameterPanel';
import SafetyDashboard from '@/components/SafetyDashboard';
import LumosLogo from '@/components/LumosLogo';
import HourlyRiskChart from '@/components/HourlyRiskChart';
import AISafetyTips from '@/components/AISafetyTips';
import EmergencyResources from '@/components/EmergencyResources';
import UserMenu from '@/components/UserMenu';
import ShareReport from '@/components/ShareReport';
import SavedReportsPanel from '@/components/SavedReportsPanel';
import NearbyPOIs from '@/components/NearbyPOIs';
import HistoricalTrends from '@/components/HistoricalTrends';
import ReportIncident from '@/components/ReportIncident';
import ExportReport from '@/components/ExportReport';
import ThemeToggle from '@/components/ThemeToggle';
import RouteSafetyPanel from '@/components/RouteSafetyPanel';
import HeatmapLegend from '@/components/HeatmapLegend';
import WalkWithMe from '@/components/WalkWithMe';

import SafetyChatWidget from '@/components/SafetyChatWidget';

import { EmergencyCallModal } from '@/components/EmergencyCallModal';

import { geocodeLocation, fetchSafetyScore, fetchRouteAnalysis, fetchCitizenHotspots, type FullSafetyResponse, type HeatmapPoint } from '@/lib/api';
import { useTheme } from '@/hooks/useTheme';
import {
  addCrimeHeatmap,
  removeCrimeHeatmap,
  addCitizenHeatmap,
  removeCitizenHeatmap,
  addRouteToMap,
  removeRouteFromMap,
  restoreMapLayers,
  updateUserMarker,
  removeUserMarker,
  addPOIMarkers,
  removePOIMarkers,
  showPOIPopupAt,
  setCenterMarker,
  removeCenterMarker,
  setDestinationMarker,
  clearAllMapData,
  addSearchCenterMarker,
  removeSearchCenterMarker,
  type HeatmapDisplayMode,
} from '@/lib/heatmap';
import { saveReport, type SavedReport } from '@/lib/savedReports';
import { useAuth } from '@/hooks/useAuth';
import { toast } from 'sonner';
import { Bookmark, Layers, LocateFixed, Radio, RefreshCw, CircleDot, Sparkles, MapPin, BarChart3, Phone, AlertCircle, ChevronUp, ChevronDown, Map } from 'lucide-react';
import type { TravelParams, RouteAnalysisData } from '@/types/safety';

type ActivePanel = 'tips' | 'pois' | 'trends' | 'emergency' | 'report' | null;

type AppState = 'landing' | 'loading' | 'results';

/** Format incident date for tooltip (e.g. "2024-01-15T12:00:00" → "Jan 15, 2024") */
function formatIncidentDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return dateStr;
  }
}

const Index = () => {
  const { user } = useAuth();
  const theme = useTheme();
  const isLight = theme === 'light';
  const [appState, setAppState] = useState<AppState>('landing');
  const [safetyData, setSafetyData] = useState<FullSafetyResponse | null>(null);
  const [locationName, setLocationName] = useState('');
  const [locationCoords, setLocationCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [heatmapMode, setHeatmapMode] = useState<'density' | 'hotspots'>('density');
  const [savedPanelOpen, setSavedPanelOpen] = useState(false);
  const [stateAbbr, setStateAbbr] = useState('');
  const [activePanel, setActivePanel] = useState<ActivePanel>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const originPrefillRef = useRef<((name: string) => void) | null>(null);

  // Route-specific state
  const [searchMode, setSearchMode] = useState<SearchMode>('single');
  const [routeData, setRouteData] = useState<RouteAnalysisData | null>(null);
  const [originName, setOriginName] = useState('');
  const [destName, setDestName] = useState('');
  const [destCoords, setDestCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [isWalking, setIsWalking] = useState(false);
  const [currentLocationText, setCurrentLocationText] = useState('');
  const [isLocating, setIsLocating] = useState(false);

  // Citizen live-incident heatmap state
  const [showCitizenHeatmap, setShowCitizenHeatmap] = useState(true);
  const [citizenIncidents, setCitizenIncidents] = useState<HeatmapPoint[] | null>(null);

  // Route-mode heatmap data (crime + citizen along the route)
  const [routeHeatmapPoints, setRouteHeatmapPoints] = useState<HeatmapPoint[] | null>(null);
  const [routeHeatmapCenter, setRouteHeatmapCenter] = useState<{ lat: number; lng: number } | null>(null);

  // Mobile bottom sheet state: collapsed shows peek bar, expanded shows full panels
  const [mobilePanelOpen, setMobilePanelOpen] = useState(false);

  // Emergency call (VAPI) modal
  const [emergencyCallModalOpen, setEmergencyCallModalOpen] = useState(false);

  // Keyboard shortcut: '/' focuses search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === '/' && !['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement).tagName)) {
        e.preventDefault();
        document.querySelector<HTMLInputElement>('[data-search-input]')?.focus();
      }
      if (e.key === 'Escape' && appState === 'results') {
        resetToLanding();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [appState]);

  // Load from URL params on mount (shareable links)
  useEffect(() => {
    const url = new URL(window.location.href);
    const lat = url.searchParams.get('lat');
    const lng = url.searchParams.get('lng');
    const q = url.searchParams.get('q');
    if (lat && lng && q) {
      // Use default params for URL-based load
      const defaultParams: TravelParams = {
        peopleCount: 1,
        gender: 'prefer-not-to-say',
        timeOfTravel: new Date().toTimeString().slice(0, 5),
        duration: 60,
        mode: 'walking',
      };
      runSafetyAnalysis(parseFloat(lat), parseFloat(lng), q, defaultParams);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [params, setParams] = useState<TravelParams>({
    peopleCount: 1,
    gender: 'prefer-not-to-say',
    timeOfTravel: new Date().toTimeString().slice(0, 5),
    duration: 60,
    mode: 'walking',
  });
  const [paramsDirty, setParamsDirty] = useState(false);

  /** Register heatmap popup hover handlers on the map */
  const registerHeatmapPopup = useCallback((map: mapboxgl.Map) => {
    const popup = new mapboxgl.Popup({
      closeButton: false,
      closeOnClick: false,
      className: 'heatmap-popup'
    });

    const enterHandler = (e: mapboxgl.MapLayerMouseEvent) => {
      if (!e.features || e.features.length === 0) return;
      map.getCanvas().style.cursor = 'pointer';

      const coordinates = (e.features[0].geometry as any).coordinates.slice();
      const props = e.features[0].properties ?? {};
      const { type, weight, description } = props;
      const date = props.date ?? props.recentDate ?? '';

      while (Math.abs(e.lngLat.lng - coordinates[0]) > 180) {
        coordinates[0] += e.lngLat.lng > coordinates[0] ? 360 : -360;
      }

      const riskLevel = weight > 0.6 ? 'High Risk' : weight > 0.3 ? 'Moderate Risk' : 'Low Risk';
      const riskColor = weight > 0.6 ? '#ef4444' : weight > 0.3 ? '#f59e0b' : '#22c55e';

      const descHtml = description
        ? `<div style="font-size: 12px; color: hsl(var(--muted-foreground)); margin-top: 4px; line-height: 1.4; max-width: 240px;">${description}</div>`
        : '';

      const dateHtml = date
        ? `<div style="font-size: 11px; color: hsl(var(--muted-foreground)); margin-top: 2px;">Most recent: ${formatIncidentDate(date)}</div>`
        : '';

      popup
        .setLngLat(coordinates as [number, number])
        .setHTML(`
          <div style="padding: 6px 8px; font-family: system-ui, sans-serif; color: hsl(var(--foreground));">
            <div style="font-weight: 600; font-size: 14px; margin-bottom: 2px;">${type}</div>
            <div style="font-size: 12px; color: ${riskColor}; font-weight: 500;">
              ${riskLevel} (Risk: ${Math.round(weight * 100)}%)
            </div>
            ${dateHtml}
            ${descHtml}
          </div>
        `)
        .addTo(map);
    };

    const leaveHandler = () => {
      map.getCanvas().style.cursor = '';
      popup.remove();
    };

    // Remove old listeners if the layer exists (safe to call even if not bound)
    map.off('mouseenter', 'crime-heatmap-circle-layer', enterHandler);
    map.off('mouseleave', 'crime-heatmap-circle-layer', leaveHandler);
    map.off('mouseenter', 'crime-hotspot-hit-layer', enterHandler);
    map.off('mouseleave', 'crime-hotspot-hit-layer', leaveHandler);

    map.on('mouseenter', 'crime-heatmap-circle-layer', enterHandler);
    map.on('mouseleave', 'crime-heatmap-circle-layer', leaveHandler);
    map.on('mouseenter', 'crime-hotspot-hit-layer', enterHandler);
    map.on('mouseleave', 'crime-hotspot-hit-layer', leaveHandler);

    // Citizen hotspot popup
    const citizenPopup = new mapboxgl.Popup({
      closeButton: false,
      closeOnClick: false,
      className: 'heatmap-popup',
    });

    const citizenEnterHandler = (e: mapboxgl.MapLayerMouseEvent) => {
      if (!e.features || e.features.length === 0) return;
      map.getCanvas().style.cursor = 'pointer';
      const coordinates = (e.features[0].geometry as any).coordinates.slice();
      const { type, weight } = e.features[0].properties as any;

      while (Math.abs(e.lngLat.lng - coordinates[0]) > 180) {
        coordinates[0] += e.lngLat.lng > coordinates[0] ? 360 : -360;
      }

      const severity = weight > 0.6 ? 'High' : weight > 0.3 ? 'Moderate' : 'Low';
      const sevColor = weight > 0.6 ? '#ef4444' : weight > 0.3 ? '#f59e0b' : '#a855f7';

      citizenPopup
        .setLngLat(coordinates as [number, number])
        .setHTML(`
          <div style="padding: 4px; font-family: system-ui, sans-serif; color: hsl(var(--foreground));">
            <div style="font-weight: 600; font-size: 13px; margin-bottom: 2px;">${type}</div>
            <div style="font-size: 11px; color: ${sevColor}; font-weight: 500;">
              ${severity} Severity &middot; Live Incident
            </div>
          </div>
        `)
        .addTo(map);
    };

    const citizenLeaveHandler = () => {
      map.getCanvas().style.cursor = '';
      citizenPopup.remove();
    };

    map.off('mouseenter', 'citizen-heatmap-circle-layer', citizenEnterHandler);
    map.off('mouseleave', 'citizen-heatmap-circle-layer', citizenLeaveHandler);

    map.on('mouseenter', 'citizen-heatmap-circle-layer', citizenEnterHandler);
    map.on('mouseleave', 'citizen-heatmap-circle-layer', citizenLeaveHandler);
  }, []);

  const handleMapReady = useCallback((map: mapboxgl.Map | null) => {
    mapRef.current = map;
    if (map) {
      registerHeatmapPopup(map);
    }
  }, [registerHeatmapPopup]);

  /** Restore layers after a Mapbox style reload (theme toggle) */
  const handleStyleReloaded = useCallback(() => {
    if (mapRef.current) {
      restoreMapLayers(mapRef.current);
      // Re-register heatmap popup handlers since style reload destroys layers
      registerHeatmapPopup(mapRef.current);
    }
  }, [registerHeatmapPopup]);

  /** Reset everything: clear all markers/layers then fluid fly back to globe */
  const resetToLanding = useCallback(() => {
    setAppState('landing');
    setSafetyData(null);
    setRouteData(null);
    setRouteHeatmapPoints(null);
    setRouteHeatmapCenter(null);
    setLocationCoords(null);
    setDestCoords(null);
    setIsWalking(false);
    setIsSearching(false);
    setSearchMode('single');
    setCitizenIncidents(null);
    window.history.replaceState({}, '', window.location.pathname);
    const map = mapRef.current;
    if (map) {
      removeCrimeHeatmap(map);
      removeCitizenHeatmap(map);
      removeRouteFromMap(map);
      removeUserMarker();
      removePOIMarkers(map);
      removeSearchCenterMarker();
      clearAllMapData();
      if (map.dragPan && !map.dragPan.isEnabled()) map.dragPan.enable();
      if (map.touchZoomRotate && !map.touchZoomRotate.isEnabled()) map.touchZoomRotate.enable();
      requestAnimationFrame(() => {
        map.flyTo({
          center: [0, 20],
          zoom: 1.5,
          pitch: 0,
          bearing: 0,
          duration: 2800,
          essential: true,
          easing: (t: number) => 1 - Math.pow(1 - t, 3),
        });
      });
    }
  }, []);

  // ─── Single-location analysis ───
  const runSafetyAnalysis = useCallback(
    async (lat: number, lng: number, name: string, travelParams: TravelParams) => {
      setIsSearching(true);
      setAppState('loading');
      setLocationName(name);
      setLocationCoords({ lat, lng });
      setRouteData(null);
      setRouteHeatmapPoints(null);
      setRouteHeatmapCenter(null);

      try {
        if (mapRef.current) {
          try {
            removeRouteFromMap(mapRef.current);
          } catch { /* map style may not be loaded yet */ }
          flyToLocation(mapRef.current, lat, lng);
        }

        const data = await fetchSafetyScore(lat, lng, travelParams, name);
        setSafetyData(data);
        setAppState('results');
        setParamsDirty(false);

        // Extract state abbreviation
        const parts = name.split(',').map((s: string) => s.trim());
        const stateStr = parts.length >= 2 ? parts[parts.length - 2] : '';
        const stateMatch = stateStr.match(/\b([A-Z]{2})\b/);
        if (stateMatch) setStateAbbr(stateMatch[1]);

        // Update URL
        const url = new URL(window.location.href);
        url.searchParams.set('q', name);
        url.searchParams.set('lat', lat.toFixed(4));
        url.searchParams.set('lng', lng.toFixed(4));
        window.history.replaceState({}, '', url.toString());

        // Add search center marker + heatmap after map style is ready
        if (mapRef.current) {
          const map = mapRef.current;
          const points = data.heatmapPoints?.length
            ? data.heatmapPoints
            : [{ lat, lng, weight: 0.15, type: 'Area' }];
          const addLayersWhenReady = () => {
            try {
              addSearchCenterMarker(map, lat, lng);
              if (showHeatmap) addCrimeHeatmap(map, lat, lng, points, heatmapMode);
              setCenterMarker(map, lat, lng, name);
              if (data.nearbyPOIs?.length) addPOIMarkers(map, data.nearbyPOIs);
            } catch (e) {
              console.warn('Heatmap render deferred:', e);
            }
          };
          if (map.isStyleLoaded()) {
            addLayersWhenReady();
          } else {
            map.once('style.load', addLayersWhenReady);
          }
        }

        // Fetch Citizen live incidents (non-blocking)
        const bounds = {
          lowerLatitude: lat - 0.2,
          lowerLongitude: lng - 0.2,
          upperLatitude: lat + 0.2,
          upperLongitude: lng + 0.2,
        };
        fetchCitizenHotspots(bounds).then((incidents) => {
          setCitizenIncidents(incidents);
          if (mapRef.current && showCitizenHeatmap && incidents.length > 0) {
            const map = mapRef.current;
            const addCitizen = () => addCitizenHeatmap(map, incidents);
            if (map.isStyleLoaded()) addCitizen();
            else map.once('idle', addCitizen);
          }
        });
      } catch {
        toast.error('Analysis failed', { description: 'Could not fetch safety data. Make sure the backend is running and try again.' });
        // Let the fly animation finish before resetting, so the transition isn't jarring
        const map = mapRef.current;
        if (map) {
          const doReset = () => {
            setAppState('landing');
            map.flyTo({
              center: [0, 20],
              zoom: 1.5,
              pitch: 0,
              bearing: 0,
              duration: 2000,
              essential: true,
            });
          };
          // Wait for the current fly to complete (or timeout)
          map.once('moveend', doReset);
          setTimeout(doReset, 3000);
        } else {
          setAppState('landing');
        }
      } finally {
        setIsSearching(false);
      }
    },
    [showHeatmap, showCitizenHeatmap, heatmapMode]
  );

  // ─── Route analysis (A → B) ───
  const runRouteAnalysis = useCallback(
    async (oLat: number, oLng: number, oName: string, dLat: number, dLng: number, dName: string, travelParams: TravelParams) => {
      setIsSearching(true);
      setAppState('loading');
      setLocationName(`${oName} → ${dName}`);
      setOriginName(oName);
      setDestName(dName);
      setLocationCoords({ lat: oLat, lng: oLng });
      setDestCoords({ lat: dLat, lng: dLng });
      setSafetyData(null);
      setRouteHeatmapPoints(null);
      setRouteHeatmapCenter(null);

      // Stop globe rotation so fitBounds isn't cancelled by jumpTo
      pauseGlobeRotation();

      if (mapRef.current) {
        mapRef.current.stop();
        removeCrimeHeatmap(mapRef.current);
        removeRouteFromMap(mapRef.current);
        removeCenterMarker();
      }

      try {
        if (mapRef.current) {
          try {
            removeCrimeHeatmap(mapRef.current);
            removeRouteFromMap(mapRef.current);
          } catch { /* map style may not be loaded yet */ }
        }

        const data = await fetchRouteAnalysis(oLat, oLng, dLat, dLng, travelParams, travelParams.mode);
        setRouteData(data);
        setAppState('results');
        setParamsDirty(false);

        // Fluid transition: fit the map to show both origin and destination
        if (mapRef.current) {
          const bounds = new mapboxgl.LngLatBounds();
          bounds.extend([oLng, oLat]);
          bounds.extend([dLng, dLat]);
          mapRef.current.fitBounds(bounds, { padding: 100, duration: 2200, pitch: 30 });

          // Draw route and destination marker when ready
          const drawRoute = () => {
            try {
              if (mapRef.current && data.segments && data.polyline) {
                addRouteToMap(mapRef.current, data.segments, data.polyline);
                setDestinationMarker(mapRef.current, dLat, dLng, dName);
              }
            } catch (e) {
              console.warn('Route render deferred:', e);
            }
          };
          if (mapRef.current.isStyleLoaded()) {
            drawRoute();
          } else {
            mapRef.current.once('style.load', drawRoute);
          }

          // Fetch crime heatmap and Citizen data for the route corridor so danger shows along the route
          const midLat = (oLat + dLat) / 2;
          const midLng = (oLng + dLng) / 2;
          const routeBounds = {
            lowerLatitude: Math.min(oLat, dLat) - 0.05,
            lowerLongitude: Math.min(oLng, dLng) - 0.05,
            upperLatitude: Math.max(oLat, dLat) + 0.05,
            upperLongitude: Math.max(oLng, dLng) + 0.05,
          };
          Promise.all([
            fetchSafetyScore(midLat, midLng, travelParams, `${oName} → ${dName}`).catch(() => null),
            fetchCitizenHotspots(routeBounds),
          ]).then(([safetyRes, incidents]) => {
            if (safetyRes?.heatmapPoints != null) {
              setRouteHeatmapPoints(safetyRes.heatmapPoints);
              setRouteHeatmapCenter({ lat: midLat, lng: midLng });
            }
            setCitizenIncidents(incidents);
            if (incidents?.length > 0) setShowCitizenHeatmap(true);
            const map = mapRef.current;
            if (map && safetyRes?.heatmapPoints?.length && showHeatmap) {
              addCrimeHeatmap(map, midLat, midLng, safetyRes.heatmapPoints, heatmapMode);
            }
            if (map && incidents.length > 0 && showCitizenHeatmap) {
              addCitizenHeatmap(map, incidents);
            }
          });
        }
      } catch {
        toast.error('Route analysis failed', { description: 'Could not analyze route safety. Make sure the backend is running.' });
        // Fly back to globe view gracefully
        const map = mapRef.current;
        if (map) {
          map.flyTo({
            center: [0, 20],
            zoom: 1.5,
            pitch: 0,
            bearing: 0,
            duration: 2000,
            essential: true,
          });
          map.once('moveend', () => setAppState('landing'));
        } else {
          setAppState('landing');
        }
      } finally {
        setIsSearching(false);
      }
    },
    []
  );

  // ─── Search handlers ───
  const handleSearchSingle = useCallback(
    async (query: string) => {
      const location = await geocodeLocation(query);
      if (!location) {
        toast.error('Location not found', { description: 'Try a different city or address.' });
        return;
      }
      runSafetyAnalysis(location.lat, location.lng, location.name, params);
    },
    [params, runSafetyAnalysis]
  );

  const handleSearchRoute = useCallback(
    async (originQuery: string, destQuery: string) => {
      const [origin, dest] = await Promise.all([
        geocodeLocation(originQuery),
        geocodeLocation(destQuery),
      ]);
      if (!origin) {
        toast.error('Origin not found', { description: `Could not find "${originQuery}".` });
        return;
      }
      if (!dest) {
        toast.error('Destination not found', { description: `Could not find "${destQuery}".` });
        return;
      }
      runRouteAnalysis(origin.lat, origin.lng, origin.name, dest.lat, dest.lng, dest.name, params);
    },
    [params, runRouteAnalysis]
  );

  const handleUseCurrentLocation = useCallback(async () => {
    if (!navigator.geolocation) {
      toast.error('Geolocation not supported');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude, longitude } = pos.coords;
        toast.success('Location detected', { description: `${latitude.toFixed(4)}, ${longitude.toFixed(4)}` });

        // Reverse-geocode to get a readable name
        const fallbackName = `${latitude.toFixed(4)}, ${longitude.toFixed(4)}`;
        const location = await geocodeLocation(fallbackName);
        const displayName = location?.name || fallbackName;

        // Fill the search bar text
        setCurrentLocationText(displayName);

        // In route mode, push directly into start field (fixes landing page autopopulation)
        if (searchMode === 'route') {
          originPrefillRef.current?.(displayName);
        }

        // In single mode, also trigger the analysis immediately
        if (searchMode === 'single') {
          runSafetyAnalysis(latitude, longitude, displayName, params);
        }
      },
      () => {
        toast.error('Location access denied', { description: 'Enable location permissions in your browser.' });
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }, [searchMode, params, runSafetyAnalysis]);

  // Update params only; mark dirty so user can refresh when ready
  const handleParamsChange = useCallback((newParams: TravelParams) => {
    setParams(newParams);
    if (appState === 'results') setParamsDirty(true);
  }, [appState]);

  // Apply pending param changes and re-run analysis
  const handleRefresh = useCallback(() => {
    if (appState !== 'results' || !locationCoords) return;
    if (routeData && destCoords) {
      runRouteAnalysis(locationCoords.lat, locationCoords.lng, originName, destCoords.lat, destCoords.lng, destName, params);
    } else if (locationName) {
      runSafetyAnalysis(locationCoords.lat, locationCoords.lng, locationName, params);
    }
  }, [appState, locationCoords, locationName, params, routeData, destCoords, originName, destName, runSafetyAnalysis, runRouteAnalysis]);

  // ─── Walk With Me ───
  const handleStartWalk = useCallback(() => {
    setIsWalking(true);
    toast.success('Walk tracking started', { description: 'Stay safe!' });
  }, []);

  const handleStopWalk = useCallback(() => {
    setIsWalking(false);
    if (mapRef.current) removeUserMarker();
    toast.info('Walk tracking stopped');
  }, []);

  const handleWalkPositionUpdate = useCallback((lat: number, lng: number) => {
    if (mapRef.current) updateUserMarker(mapRef.current, lat, lng);
  }, []);

  // Show my location: place marker and fly map to user (works on landing and results)
  const handleShowMyLocation = useCallback(() => {
    if (!navigator.geolocation) {
      toast.error('Geolocation not supported', { description: 'Use a browser that supports location.' });
      return;
    }
    setIsLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords;
        const map = mapRef.current;
        if (map) {
          updateUserMarker(map, latitude, longitude);
          flyToLocation(map, latitude, longitude, undefined, { duration: 1800 });
          toast.success('Showing your location', { description: 'You can see nearby safe spots and risk areas on the map.' });
        } else {
          toast.success('Location found', { description: `${latitude.toFixed(4)}, ${longitude.toFixed(4)}` });
        }
        setIsLocating(false);
      },
      () => {
        toast.error('Location unavailable', { description: 'Enable location permissions or try again.' });
        setIsLocating(false);
      },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 }
    );
  }, []);

  // ─── Save / Load ───
  const handleSaveReport = async () => {
    if (!user) {
      toast.error('Sign in to save reports');
      return;
    }
    if (!safetyData || !locationCoords) return;
    try {
      await saveReport(user.uid, locationName, locationCoords.lat, locationCoords.lng, params, safetyData);
      toast.success('Report saved!');
    } catch {
      toast.error('Failed to save report');
    }
  };

  const handleLoadReport = (report: SavedReport) => {
    setSearchMode('single');
    setRouteData(null);
    setParams(report.params);
    runSafetyAnalysis(report.lat, report.lng, report.locationName, report.params);
  };

  const toggleHeatmap = () => {
    const next = !showHeatmap;
    setShowHeatmap(next);
    if (mapRef.current) {
      if (!next) {
        removeCrimeHeatmap(mapRef.current);
      } else if (routeData && routeHeatmapCenter && routeHeatmapPoints?.length) {
        addCrimeHeatmap(mapRef.current, routeHeatmapCenter.lat, routeHeatmapCenter.lng, routeHeatmapPoints, heatmapMode);
      } else if (locationCoords && safetyData?.heatmapPoints) {
        addCrimeHeatmap(mapRef.current, locationCoords.lat, locationCoords.lng, safetyData.heatmapPoints, heatmapMode);
      }
    }
  };

  const toggleCitizenHeatmap = () => {
    const next = !showCitizenHeatmap;
    setShowCitizenHeatmap(next);
    if (mapRef.current) {
      if (!next) {
        removeCitizenHeatmap(mapRef.current);
      } else if (citizenIncidents && citizenIncidents.length > 0) {
        addCitizenHeatmap(mapRef.current, citizenIncidents);
      }
    }
  };

  const cycleHeatmapMode = () => {
    const next: HeatmapDisplayMode = heatmapMode === 'density' ? 'hotspots' : 'density';
    setHeatmapMode(next);
    if (mapRef.current && showHeatmap && locationCoords && safetyData) {
      addCrimeHeatmap(mapRef.current, locationCoords.lat, locationCoords.lng, safetyData.heatmapPoints, next);
    }
  };

  const currentHour = parseInt(params.timeOfTravel.split(':')[0], 10);
  const isRouteResults = appState === 'results' && routeData !== null;
  const isSingleResults = appState === 'results' && safetyData !== null && routeData === null;

  return (
    <div className="relative w-full h-screen overflow-hidden bg-background">
      {/* Globe background */}
      <GlobeView onMapReady={handleMapReady} onStyleReloaded={handleStyleReloaded} />

      {/* Overlay gradient for readability — minimal on mobile results so map stays visible */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            appState === 'landing'
              ? isLight
                ? 'radial-gradient(ellipse at center, transparent 30%, hsl(220 20% 97% / 0.6) 100%)'
                : 'radial-gradient(ellipse at center, transparent 30%, hsl(222 47% 4% / 0.7) 100%)'
              : appState === 'results' && window.innerWidth < 768
                ? 'none'
                : isLight
                  ? 'linear-gradient(to right, hsl(220 20% 97% / 0.9) 0%, hsl(220 20% 97% / 0.5) 50%, transparent 100%)'
                  : 'linear-gradient(to right, hsl(222 47% 4% / 0.85) 0%, hsl(222 47% 4% / 0.4) 50%, transparent 100%)',
          transition: 'background 1s ease',
        }}
      />

      {/* Header — z-30 so logo is always on top and clickable (back to home in any mode) */}
      <div className="absolute top-0 left-0 right-0 z-30 p-3 sm:p-6 flex items-center justify-between gap-2">
        <button onClick={resetToLanding} className="cursor-pointer z-30 relative flex-shrink-0" aria-label="Back to home">
          <LumosLogo size={36} />
        </button>
        <div className="flex items-center gap-1.5 sm:gap-2 overflow-x-auto scrollbar-hide flex-shrink min-w-0">
          <ThemeToggle />
          {appState !== 'loading' && (
            <motion.button
              key="show-location"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              onClick={handleShowMyLocation}
              disabled={isLocating}
              className="header-btn flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors glass-panel px-2.5 sm:px-3 py-2 rounded-xl disabled:opacity-60 flex-shrink-0"
              title="Show my location on the map"
              aria-label="Show my location"
            >
              <LocateFixed className={`w-4 h-4 ${isLocating ? 'animate-pulse' : ''}`} />
              <span className="hidden sm:inline">My location</span>
            </motion.button>
          )}
          {appState === 'results' && (
            <>
              {(isSingleResults || isRouteResults) && (
                <>
                  <motion.button
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    onClick={toggleHeatmap}
                    className={`header-btn flex items-center gap-1.5 text-sm transition-colors glass-panel px-2.5 sm:px-3 py-2 rounded-xl flex-shrink-0 ${showHeatmap ? 'text-primary' : 'text-muted-foreground hover:text-foreground'
                      }`}
                    title="Toggle crime heatmap"
                    aria-label="Toggle crime heatmap"
                    aria-pressed={showHeatmap}
                  >
                    <Layers className="w-4 h-4" />
                  </motion.button>
                  {showHeatmap && (
                    <motion.button
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      onClick={cycleHeatmapMode}
                      className="header-btn flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors glass-panel px-2.5 sm:px-3 py-2 rounded-xl flex-shrink-0"
                      title={`Switch to ${heatmapMode === 'density' ? 'hotspots' : 'density'} view`}
                      aria-label="Toggle display mode"
                    >
                      <CircleDot className="w-4 h-4" />
                      <span className="text-xs hidden sm:inline">
                        {heatmapMode === 'density' ? 'Density' : 'Hotspots'}
                      </span>
                    </motion.button>
                  )}
                  {citizenIncidents && citizenIncidents.length > 0 && (
                    <motion.button
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      onClick={toggleCitizenHeatmap}
                      className={`header-btn flex items-center gap-1.5 text-sm transition-colors glass-panel px-2.5 sm:px-3 py-2 rounded-xl flex-shrink-0 ${showCitizenHeatmap ? 'text-purple-400' : 'text-muted-foreground hover:text-foreground'
                        }`}
                      title="Toggle live incidents (Citizen)"
                      aria-label="Toggle live incidents"
                      aria-pressed={showCitizenHeatmap}
                    >
                      <Radio className="w-4 h-4" />
                    </motion.button>
                  )}
                </>
              )}
              {safetyData && (
                <>
                  <motion.button
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    onClick={handleSaveReport}
                    className="header-btn flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors glass-panel px-2.5 sm:px-3 py-2 rounded-xl flex-shrink-0 hidden xs:flex"
                    title="Save report"
                    aria-label="Save report"
                  >
                    <Bookmark className="w-4 h-4" />
                  </motion.button>
                  <span className="hidden sm:contents">
                    <ExportReport data={safetyData} locationName={locationName} params={params} />
                  </span>
                  <ShareReport data={safetyData} locationName={locationName} />
                </>
              )}
              <motion.button
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                onClick={resetToLanding}
                className="header-btn text-sm text-muted-foreground hover:text-foreground transition-colors glass-panel px-2.5 sm:px-4 py-2 rounded-xl flex-shrink-0"
                aria-label="New search"
              >
                <span className="hidden sm:inline">New Search</span>
                <RefreshCw className="w-4 h-4 sm:hidden" />
              </motion.button>
            </>
          )}
          <UserMenu onOpenSaved={() => setSavedPanelOpen(true)} />
        </div>
      </div>

      {/* Landing state */}
      {appState === 'landing' && (
        <motion.div
          key="landing"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4 }}
          className="absolute inset-0 z-10 flex flex-col items-center justify-center px-6"
        >
          <motion.h1
            className="text-4xl sm:text-5xl md:text-6xl font-display font-bold text-foreground text-center mb-3"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            Know Before You Go
          </motion.h1>
          <motion.p
            className="text-base sm:text-lg text-muted-foreground text-center mb-10 max-w-lg"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.35 }}
          >
            Real-time safety insights powered by open data and predictive analytics.
          </motion.p>
          <RouteSearchBar
            onSearchSingle={handleSearchSingle}
            onSearchRoute={handleSearchRoute}
            onUseCurrentLocation={handleUseCurrentLocation}
            isLoading={isSearching}
            mode={searchMode}
            onModeChange={setSearchMode}
            currentLocationText={currentLocationText}
            currentOriginFromLocation={searchMode === 'route' ? currentLocationText : undefined}
            onRegisterOriginPrefill={(fn) => { originPrefillRef.current = fn; }}
          />
          <motion.p
            className="text-xs text-muted-foreground/60 mt-4 keyboard-hint"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.8 }}
          >
            Press <kbd className="px-1.5 py-0.5 rounded bg-secondary text-secondary-foreground text-[10px] font-mono">/</kbd> to search &middot; <kbd className="px-1.5 py-0.5 rounded bg-secondary text-secondary-foreground text-[10px] font-mono">Esc</kbd> to reset
          </motion.p>
        </motion.div>
      )}

      {/* Loading state */}
      {appState === 'loading' && (
        <motion.div
          key="loading"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25 }}
          className="absolute inset-0 z-10 flex items-center justify-center"
        >
          <div className="glass-panel rounded-2xl px-6 sm:px-8 py-5 sm:py-6 flex items-center gap-3 sm:gap-4 mx-4 max-w-sm">
            <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin flex-shrink-0" />
            <span className="text-foreground font-light text-sm sm:text-base truncate">
              {searchMode === 'route' ? 'Analyzing route safety...' : `Analyzing ${locationName}...`}
            </span>
          </div>
        </motion.div>
      )}

      {/* Results: Single location */}
      {isSingleResults && safetyData && (
        <motion.div
          key="results-single"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5 }}
          className="absolute inset-0 z-10 pointer-events-none"
        >
          {/* ─── Desktop: side-by-side panels ─── */}
          <div className="h-full hidden lg:flex lg:flex-row">
            {/* Left panel */}
            <div className="w-full lg:w-[380px] xl:w-[420px] p-3 sm:p-6 pt-16 sm:pt-24 lg:overflow-y-auto pointer-events-auto space-y-3 sm:space-y-4 scrollbar-hide relative z-10">
              <RouteSearchBar
                onSearchSingle={handleSearchSingle}
                onSearchRoute={handleSearchRoute}
                onUseCurrentLocation={handleUseCurrentLocation}
                isLoading={isSearching}
                isMinimized
                mode={searchMode}
                onModeChange={setSearchMode}
                currentLocationText={locationName || currentLocationText}
                currentOriginFromLocation={searchMode === 'route' ? currentLocationText : undefined}
                onRegisterOriginPrefill={(fn) => { originPrefillRef.current = fn; }}
              />
              <ParameterPanel params={params} onChange={handleParamsChange} />
              <AnimatePresence>
                {paramsDirty && (
                  <motion.button
                    key="refresh-single"
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    onClick={handleRefresh}
                    disabled={isSearching}
                    className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
                  >
                    <RefreshCw className={`w-4 h-4 ${isSearching ? 'animate-spin' : ''}`} />
                    {isSearching ? 'Updating...' : 'Refresh with new parameters'}
                  </motion.button>
                )}
              </AnimatePresence>
              <HourlyRiskChart currentHour={currentHour} hourlyData={safetyData.hourlyRisk} />
            </div>

            {/* Spacer */}
            <div className="flex-1 pointer-events-none" />

            {/* Right panel */}
            <div className="w-full lg:w-[360px] xl:w-[380px] relative pointer-events-auto flex flex-col">
              <div
                className="absolute top-0 left-0 right-0 h-16 z-10 pointer-events-none"
                style={{
                  background: 'linear-gradient(to bottom, hsl(var(--background)) 0%, hsl(var(--background) / 0.97) 40%, transparent 100%)',
                }}
                aria-hidden
              />
              <div className="p-3 sm:p-6 pt-20 sm:pt-24 overflow-y-auto scrollbar-hide space-y-2.5 relative z-0 pb-safe">
                {safetyData.riskLevel === 'danger' || safetyData.safetyIndex < 45 ? (
                  <div className="rounded-lg px-3 py-2 bg-red-500/20 border border-red-500/40 text-red-600 dark:text-red-400 font-semibold text-xs flex items-center gap-2">
                    <span>High Risk Area:</span>
                    <span>{safetyData.incidentTypes[0]?.crimeLevel ?? 'High Risk'}</span>
                  </div>
                ) : null}
                {(showHeatmap || (showCitizenHeatmap && citizenIncidents?.length)) && (
                  <HeatmapLegend
                    visible={true}
                    inline
                    showCitizen={true}
                    incidentCount={safetyData?.heatmapIncidentCount ?? safetyData?.heatmapPoints?.length}
                    radiusMiles={3}
                    locationName={locationName}
                    mode={heatmapMode}
                  />
                )}
                <SafetyDashboard data={safetyData} locationName={locationName} />

                {/* Quick-access icon bar */}
                <div className="glass-panel rounded-2xl p-1.5 sm:p-2">
                  <div className="flex items-center justify-around gap-0.5">
                    {([
                      { key: 'tips' as ActivePanel, icon: Sparkles, label: 'AI Tips', color: 'text-primary', bg: 'bg-primary/20' },
                      { key: 'pois' as ActivePanel, icon: MapPin, label: 'Safe Places', color: 'text-lumos-teal', bg: 'bg-lumos-teal/20', hidden: !safetyData.nearbyPOIs?.length },
                      { key: 'trends' as ActivePanel, icon: BarChart3, label: 'Trends', color: 'text-primary', bg: 'bg-primary/20', hidden: !stateAbbr },
                      { key: 'emergency' as ActivePanel, icon: Phone, label: 'Emergency', color: 'text-lumos-danger', bg: 'bg-red-500/20' },
                      { key: 'report' as ActivePanel, icon: AlertCircle, label: 'Report', color: 'text-lumos-caution', bg: 'bg-amber-500/20', hidden: !locationCoords },
                    ] as const).filter(t => !t.hidden).map((tab) => {
                      const isActive = activePanel === tab.key;
                      return (
                        <button
                          key={tab.key}
                          onClick={() => setActivePanel(isActive ? null : tab.key)}
                          className={`flex flex-col items-center gap-0.5 sm:gap-1 px-2 sm:px-3 py-1.5 sm:py-2 rounded-xl transition-all duration-200 min-w-[48px] ${
                            isActive
                              ? `${tab.bg} ${tab.color} scale-105`
                              : 'text-muted-foreground hover:text-foreground hover:bg-secondary/50 active:bg-secondary/70'
                          }`}
                          aria-label={tab.label}
                        >
                          <tab.icon className="w-4 h-4 sm:w-5 sm:h-5" />
                          <span className={`text-[9px] sm:text-[10px] font-medium leading-none ${isActive ? tab.color : ''}`}>
                            {tab.label}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Expandable panel content */}
                <AISafetyTips data={safetyData} locationName={locationName} params={params} expanded={activePanel === 'tips'} />
                {safetyData.nearbyPOIs && safetyData.nearbyPOIs.length > 0 && (
                  <NearbyPOIs
                    pois={safetyData.nearbyPOIs}
                    expanded={activePanel === 'pois'}
                    onSelectPOI={(poi) => {
                      if (!mapRef.current) return;
                      flyToLocation(
                        mapRef.current,
                        poi.lat,
                        poi.lng,
                        () => showPOIPopupAt(mapRef.current!, poi),
                        { duration: 380 }
                      );
                    }}
                  />
                )}
                {stateAbbr && <HistoricalTrends state={stateAbbr} expanded={activePanel === 'trends'} />}
                <EmergencyResources locationName={locationName} numbers={safetyData.emergencyNumbers} expanded={activePanel === 'emergency'} />
                {activePanel === 'emergency' && locationCoords && (
                  <button
                    onClick={() => setEmergencyCallModalOpen(true)}
                    className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl bg-lumos-danger text-white font-medium hover:bg-lumos-danger/90 active:bg-lumos-danger/80 transition-colors"
                  >
                    <Phone className="w-5 h-5" />
                    Call with LUMOS AI (VAPI)
                  </button>
                )}
                {locationCoords && (
                  <ReportIncident lat={locationCoords.lat} lng={locationCoords.lng} userId={user?.uid} expanded={activePanel === 'report'} />
                )}
              </div>
            </div>
          </div>

          {/* ─── Mobile: collapsible bottom sheet ─── */}
          <div className="lg:hidden absolute inset-x-0 bottom-0 z-20 pointer-events-auto flex flex-col" style={{ top: mobilePanelOpen ? '56px' : 'auto' }}>
            {/* Peek bar — always visible */}
            <button
              onClick={() => setMobilePanelOpen(!mobilePanelOpen)}
              className="flex items-center justify-between gap-3 px-4 py-3 glass-panel rounded-t-2xl border-b border-border/30 active:bg-secondary/50 transition-colors"
              aria-label={mobilePanelOpen ? 'Collapse dashboard' : 'Expand dashboard'}
            >
              <div className="flex items-center gap-3 min-w-0">
                {/* Drag handle */}
                <div className="w-8 h-1 rounded-full bg-muted-foreground/30 flex-shrink-0 mx-auto absolute top-1.5 left-1/2 -translate-x-1/2" />
                <div className={`text-2xl font-display font-bold tabular-nums ${
                  safetyData.safetyIndex >= 70 ? 'text-lumos-safe' :
                  safetyData.safetyIndex >= 40 ? 'text-lumos-caution' : 'text-lumos-danger'
                }`}>
                  {safetyData.safetyIndex}
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-medium text-foreground truncate">{locationName}</p>
                  <p className="text-[10px] text-muted-foreground">
                    {safetyData.safetyIndex >= 70 ? 'Generally Safe' : safetyData.safetyIndex >= 40 ? 'Use Caution' : 'High Risk'}
                    {' · '}{safetyData.timeAnalysis.peakHours} peak
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                {mobilePanelOpen ? (
                  <>
                    <Map className="w-4 h-4 text-muted-foreground" />
                    <ChevronDown className="w-4 h-4 text-muted-foreground" />
                  </>
                ) : (
                  <ChevronUp className="w-5 h-5 text-muted-foreground" />
                )}
              </div>
            </button>

            {/* Expanded content */}
            {mobilePanelOpen && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex-1 overflow-y-auto bg-background/95 backdrop-blur-xl scrollbar-hide"
              >
                <div className="p-3 space-y-3 pb-safe">
                  {/* Search bar */}
                  <RouteSearchBar
                    onSearchSingle={handleSearchSingle}
                    onSearchRoute={handleSearchRoute}
                    onUseCurrentLocation={handleUseCurrentLocation}
                    isLoading={isSearching}
                    isMinimized
                    mode={searchMode}
                    onModeChange={setSearchMode}
                    currentLocationText={locationName || currentLocationText}
                    currentOriginFromLocation={searchMode === 'route' ? currentLocationText : undefined}
                    onRegisterOriginPrefill={(fn) => { originPrefillRef.current = fn; }}
                  />
                  <ParameterPanel params={params} onChange={handleParamsChange} />
                  <AnimatePresence>
                    {paramsDirty && (
                      <motion.button
                        key="refresh-single-mobile"
                        initial={{ opacity: 0, y: -8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -8 }}
                        onClick={handleRefresh}
                        disabled={isSearching}
                        className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
                      >
                        <RefreshCw className={`w-4 h-4 ${isSearching ? 'animate-spin' : ''}`} />
                        {isSearching ? 'Updating...' : 'Refresh with new parameters'}
                      </motion.button>
                    )}
                  </AnimatePresence>
                  <HourlyRiskChart currentHour={currentHour} hourlyData={safetyData.hourlyRisk} />

                  {(showHeatmap || (showCitizenHeatmap && citizenIncidents?.length)) && (
                    <HeatmapLegend
                      visible={true}
                      inline
                      showCitizen={true}
                      incidentCount={safetyData?.heatmapIncidentCount ?? safetyData?.heatmapPoints?.length}
                      radiusMiles={3}
                      locationName={locationName}
                      mode={heatmapMode}
                    />
                  )}
                  <SafetyDashboard data={safetyData} locationName={locationName} />

                  {/* Quick-access icon bar */}
                  <div className="glass-panel rounded-2xl p-1.5">
                    <div className="flex items-center justify-around gap-0.5">
                      {([
                        { key: 'tips' as ActivePanel, icon: Sparkles, label: 'AI Tips', color: 'text-primary', bg: 'bg-primary/20' },
                        { key: 'pois' as ActivePanel, icon: MapPin, label: 'Safe Places', color: 'text-lumos-teal', bg: 'bg-lumos-teal/20', hidden: !safetyData.nearbyPOIs?.length },
                        { key: 'trends' as ActivePanel, icon: BarChart3, label: 'Trends', color: 'text-primary', bg: 'bg-primary/20', hidden: !stateAbbr },
                        { key: 'emergency' as ActivePanel, icon: Phone, label: 'Emergency', color: 'text-lumos-danger', bg: 'bg-red-500/20' },
                        { key: 'report' as ActivePanel, icon: AlertCircle, label: 'Report', color: 'text-lumos-caution', bg: 'bg-amber-500/20', hidden: !locationCoords },
                      ] as const).filter(t => !t.hidden).map((tab) => {
                        const isActive = activePanel === tab.key;
                        return (
                          <button
                            key={tab.key}
                            onClick={() => setActivePanel(isActive ? null : tab.key)}
                            className={`flex flex-col items-center gap-0.5 px-2 py-1.5 rounded-xl transition-all duration-200 min-w-[48px] ${
                              isActive
                                ? `${tab.bg} ${tab.color} scale-105`
                                : 'text-muted-foreground hover:text-foreground active:bg-secondary/70'
                            }`}
                            aria-label={tab.label}
                          >
                            <tab.icon className="w-4 h-4" />
                            <span className={`text-[9px] font-medium leading-none ${isActive ? tab.color : ''}`}>
                              {tab.label}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <AISafetyTips data={safetyData} locationName={locationName} params={params} expanded={activePanel === 'tips'} />
                  {safetyData.nearbyPOIs && safetyData.nearbyPOIs.length > 0 && (
                    <NearbyPOIs
                      pois={safetyData.nearbyPOIs}
                      expanded={activePanel === 'pois'}
                      onSelectPOI={(poi) => {
                        if (!mapRef.current) return;
                        setMobilePanelOpen(false);
                        flyToLocation(
                          mapRef.current,
                          poi.lat,
                          poi.lng,
                          () => showPOIPopupAt(mapRef.current!, poi),
                          { duration: 380 }
                        );
                      }}
                    />
                  )}
                  {stateAbbr && <HistoricalTrends state={stateAbbr} expanded={activePanel === 'trends'} />}
                  <EmergencyResources locationName={locationName} numbers={safetyData.emergencyNumbers} expanded={activePanel === 'emergency'} />
                  {activePanel === 'emergency' && locationCoords && (
                    <button
                      onClick={() => setEmergencyCallModalOpen(true)}
                      className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl bg-lumos-danger text-white font-medium hover:bg-lumos-danger/90 active:bg-lumos-danger/80 transition-colors"
                    >
                      <Phone className="w-5 h-5" />
                      Call with LUMOS AI (VAPI)
                    </button>
                  )}
                  {locationCoords && (
                    <ReportIncident lat={locationCoords.lat} lng={locationCoords.lng} userId={user?.uid} expanded={activePanel === 'report'} />
                  )}
                </div>
              </motion.div>
            )}
          </div>
        </motion.div>
      )}

      {/* Emergency call modal (VAPI) — shown when user taps "Call with LUMOS AI" */}
      {locationCoords && safetyData && (
        <EmergencyCallModal
          open={emergencyCallModalOpen}
          onOpenChange={setEmergencyCallModalOpen}
          lat={locationCoords.lat}
          lng={locationCoords.lng}
          address={locationName}
          safetyScore={safetyData.safetyIndex}
        />
      )}

      {/* Results: Route */}
      {isRouteResults && routeData && (
        <motion.div
          key="results-route"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5 }}
          className="absolute inset-0 z-10 pointer-events-none"
        >
          {/* ─── Desktop: side-by-side panels ─── */}
          <div className="h-full hidden lg:flex lg:flex-row">
            {/* Left panel */}
            <div className="w-full lg:w-[380px] xl:w-[420px] p-3 sm:p-6 pt-16 sm:pt-24 lg:overflow-y-auto pointer-events-auto space-y-3 sm:space-y-4 scrollbar-hide relative z-10">
              <RouteSearchBar
                onSearchSingle={handleSearchSingle}
                onSearchRoute={handleSearchRoute}
                onUseCurrentLocation={handleUseCurrentLocation}
                isLoading={isSearching}
                isMinimized
                mode={searchMode}
                onModeChange={setSearchMode}
                currentLocationText={originName || currentLocationText}
                currentOriginFromLocation={searchMode === 'route' ? currentLocationText : undefined}
                currentDestinationText={destName}
              />
              <ParameterPanel params={params} onChange={handleParamsChange} showMode />
              <AnimatePresence>
                {paramsDirty && (
                  <motion.button
                    key="refresh-route"
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    onClick={handleRefresh}
                    disabled={isSearching}
                    className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
                  >
                    <RefreshCw className={`w-4 h-4 ${isSearching ? 'animate-spin' : ''}`} />
                    {isSearching ? 'Updating...' : 'Refresh with new parameters'}
                  </motion.button>
                )}
              </AnimatePresence>
            </div>

            {/* Spacer */}
            <div className="flex-1 pointer-events-none" />

            {/* Right panel */}
            <div className="w-full lg:w-[360px] xl:w-[380px] relative pointer-events-auto flex flex-col">
              <div
                className="absolute top-0 left-0 right-0 h-16 z-10 pointer-events-none"
                style={{
                  background: 'linear-gradient(to bottom, hsl(var(--background)) 0%, hsl(var(--background) / 0.97) 40%, transparent 100%)',
                }}
                aria-hidden
              />
              <div className="p-3 sm:p-6 pt-20 sm:pt-24 overflow-y-auto scrollbar-hide space-y-2.5 relative z-0 pb-safe">
                {(showHeatmap || (showCitizenHeatmap && citizenIncidents?.length)) && (
                  <HeatmapLegend
                    visible={true}
                    inline
                    showCitizen={true}
                    incidentCount={routeHeatmapPoints?.length ?? 0}
                    radiusMiles={3}
                    locationName={`${originName} → ${destName}`}
                    mode={heatmapMode}
                  />
                )}
                <RouteSafetyPanel
                  data={routeData}
                  originName={originName}
                  destName={destName}
                  onStartWalk={handleStartWalk}
                />
                <AISafetyTips
                  data={{
                    safetyIndex: routeData.overallSafety,
                    riskLevel: routeData.riskLevel,
                    incidentTypes: routeData.warnings.map(w => ({ type: w, probability: 0.5, icon: '⚠️' })),
                    timeAnalysis: {
                      currentRisk: 100 - routeData.overallSafety,
                      peakHours: 'N/A',
                      safestHours: 'N/A',
                    },
                    dataSources: [],
                  }}
                  locationName={locationName}
                  params={params}
                />
                <EmergencyResources locationName={destName} numbers={[
                  { label: 'Emergency', number: '911', icon: 'phone', color: 'danger' },
                  { label: 'Police (non-emergency)', number: '311', icon: 'shield', color: 'caution' },
                ]} />
              </div>
            </div>
          </div>

          {/* ─── Mobile: collapsible bottom sheet ─── */}
          <div className="lg:hidden absolute inset-x-0 bottom-0 z-20 pointer-events-auto flex flex-col" style={{ top: mobilePanelOpen ? '56px' : 'auto' }}>
            {/* Peek bar */}
            <button
              onClick={() => setMobilePanelOpen(!mobilePanelOpen)}
              className="flex items-center justify-between gap-3 px-4 py-3 glass-panel rounded-t-2xl border-b border-border/30 active:bg-secondary/50 transition-colors"
              aria-label={mobilePanelOpen ? 'Collapse dashboard' : 'Expand dashboard'}
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-8 h-1 rounded-full bg-muted-foreground/30 flex-shrink-0 mx-auto absolute top-1.5 left-1/2 -translate-x-1/2" />
                <div className={`text-2xl font-display font-bold tabular-nums ${
                  routeData.overallSafety >= 70 ? 'text-lumos-safe' :
                  routeData.overallSafety >= 40 ? 'text-lumos-caution' : 'text-lumos-danger'
                }`}>
                  {routeData.overallSafety}
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-medium text-foreground truncate">{originName} → {destName}</p>
                  <p className="text-[10px] text-muted-foreground">
                    {routeData.riskLevel === 'safe' ? 'Generally Safe' : routeData.riskLevel === 'caution' ? 'Use Caution' : 'High Risk'}
                    {' · '}{routeData.distance} · {routeData.duration}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                {mobilePanelOpen ? (
                  <>
                    <Map className="w-4 h-4 text-muted-foreground" />
                    <ChevronDown className="w-4 h-4 text-muted-foreground" />
                  </>
                ) : (
                  <ChevronUp className="w-5 h-5 text-muted-foreground" />
                )}
              </div>
            </button>

            {/* Expanded content */}
            {mobilePanelOpen && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex-1 overflow-y-auto bg-background/95 backdrop-blur-xl scrollbar-hide"
              >
                <div className="p-3 space-y-3 pb-safe">
                  <RouteSearchBar
                    onSearchSingle={handleSearchSingle}
                    onSearchRoute={handleSearchRoute}
                    onUseCurrentLocation={handleUseCurrentLocation}
                    isLoading={isSearching}
                    isMinimized
                    mode={searchMode}
                    onModeChange={setSearchMode}
                    currentLocationText={originName || currentLocationText}
                    currentOriginFromLocation={searchMode === 'route' ? currentLocationText : undefined}
                    currentDestinationText={destName}
                  />
                  <ParameterPanel params={params} onChange={handleParamsChange} showMode />
                  <AnimatePresence>
                    {paramsDirty && (
                      <motion.button
                        key="refresh-route-mobile"
                        initial={{ opacity: 0, y: -8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -8 }}
                        onClick={handleRefresh}
                        disabled={isSearching}
                        className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
                      >
                        <RefreshCw className={`w-4 h-4 ${isSearching ? 'animate-spin' : ''}`} />
                        {isSearching ? 'Updating...' : 'Refresh with new parameters'}
                      </motion.button>
                    )}
                  </AnimatePresence>
                  {(showHeatmap || (showCitizenHeatmap && citizenIncidents?.length)) && (
                    <HeatmapLegend
                      visible={true}
                      inline
                      showCitizen={true}
                      incidentCount={routeHeatmapPoints?.length ?? 0}
                      radiusMiles={3}
                      locationName={`${originName} → ${destName}`}
                      mode={heatmapMode}
                    />
                  )}
                  <RouteSafetyPanel
                    data={routeData}
                    originName={originName}
                    destName={destName}
                    onStartWalk={handleStartWalk}
                  />
                  <AISafetyTips
                    data={{
                      safetyIndex: routeData.overallSafety,
                      riskLevel: routeData.riskLevel,
                      incidentTypes: routeData.warnings.map(w => ({ type: w, probability: 0.5, icon: '⚠️' })),
                      timeAnalysis: {
                        currentRisk: 100 - routeData.overallSafety,
                        peakHours: 'N/A',
                        safestHours: 'N/A',
                      },
                      dataSources: [],
                    }}
                    locationName={locationName}
                    params={params}
                  />
                  <EmergencyResources locationName={destName} numbers={[
                    { label: 'Emergency', number: '911', icon: 'phone', color: 'danger' },
                    { label: 'Police (non-emergency)', number: '311', icon: 'shield', color: 'caution' },
                  ]} />
                </div>
              </motion.div>
            )}
          </div>
        </motion.div>
      )}

      {/* Walk With Me overlay */}
      <AnimatePresence>
        {isWalking && destCoords && routeData && (
          <WalkWithMe
            destLat={destCoords.lat}
            destLng={destCoords.lng}
            destName={destName}
            routeSafetyScore={routeData.overallSafety}
            onStop={handleStopWalk}
            onPositionUpdate={handleWalkPositionUpdate}
          />
        )}
      </AnimatePresence>

      {/* Saved Reports Drawer */}
      <SavedReportsPanel
        isOpen={savedPanelOpen}
        onClose={() => setSavedPanelOpen(false)}
        onLoadReport={handleLoadReport}
      />

      {/* Safety Chat Widget */}
      <SafetyChatWidget
        locationName={locationName}
        safetyData={safetyData}
        routeData={routeData}
        params={params}
      />

    </div>
  );
};

export default Index;
