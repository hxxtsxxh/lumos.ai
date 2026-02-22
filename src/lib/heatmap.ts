import mapboxgl from 'mapbox-gl';
import type { HeatmapPoint } from '@/lib/api';
import type { RouteSegment, NearbyPOI } from '@/types/safety';

export type HeatmapDisplayMode = 'density' | 'hotspots';

const HEATMAP_SOURCE = 'crime-heatmap';
const POI_SOURCE = 'safe-places-pois';
const HEATMAP_LAYER = 'crime-heatmap-layer';
const HEATMAP_CIRCLE_LAYER = 'crime-heatmap-circle-layer';
const CITIZEN_HEATMAP_SOURCE = 'citizen-heatmap';
const CITIZEN_HEATMAP_LAYER = 'citizen-heatmap-layer';
const CITIZEN_HEATMAP_CIRCLE_LAYER = 'citizen-heatmap-circle-layer';
const HOTSPOT_CIRCLE_LAYER = 'crime-hotspot-circle-layer';
const HOTSPOT_HIT_LAYER = 'crime-hotspot-hit-layer';
const ROUTE_SOURCE = 'route-segments';
const ROUTE_LAYER_BASE = 'route-segment-';

let _lastHeatmapData: { lat: number; lng: number; points: HeatmapPoint[]; mode: HeatmapDisplayMode } | null = null;
let _lastPOIs: NearbyPOI[] | null = null;
let _lastCitizenData: HeatmapPoint[] | null = null;
let _lastRouteSegments: RouteSegment[] | null = null;
let _lastRoutePolyline: number[][] | null = null;

let _searchCenterMarker: mapboxgl.Marker | null = null;

export function addSearchCenterMarker(map: mapboxgl.Map, lat: number, lng: number) {
  removeSearchCenterMarker();

  const el = document.createElement('div');
  el.style.cssText = `
    width: 14px; height: 14px; border-radius: 50%;
    background: hsl(217, 91%, 60%);
    border: 2.5px solid white;
    box-shadow: 0 0 0 4px hsla(217,91%,60%,0.25), 0 2px 8px rgba(0,0,0,0.3);
  `;
  _searchCenterMarker = new mapboxgl.Marker(el).setLngLat([lng, lat]).addTo(map);
}

export function removeSearchCenterMarker() {
  _searchCenterMarker?.remove();
  _searchCenterMarker = null;
}

function _addDensityLayers(map: mapboxgl.Map) {
  map.addLayer({
    id: HEATMAP_LAYER,
    type: 'heatmap',
    source: HEATMAP_SOURCE,
    paint: {
      'heatmap-weight': ['interpolate', ['linear'], ['get', 'weight'], 0, 0, 1, 1],
      'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 10, 0.5, 15, 2],
      'heatmap-color': [
        'interpolate',
        ['linear'],
        ['heatmap-density'],
        0, 'rgba(0, 0, 0, 0)',
        0.1, 'hsla(174, 62%, 47%, 0.15)',
        0.3, 'hsla(38, 92%, 55%, 0.3)',
        0.5, 'hsla(38, 92%, 55%, 0.5)',
        0.7, 'hsla(15, 80%, 55%, 0.6)',
        1.0, 'hsla(0, 72%, 55%, 0.7)',
      ],
      'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 10, 15, 15, 30],
      'heatmap-opacity': ['interpolate', ['linear'], ['zoom'], 12, 0.8, 18, 0.3],
    },
  });

  // Reference 'date' in paint so Mapbox preserves it in feature properties for tooltips
  map.addLayer({
    id: HEATMAP_CIRCLE_LAYER,
    type: 'circle',
    source: HEATMAP_SOURCE,
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 15, 15, 30],
      'circle-color': 'transparent',
      'circle-stroke-width': 0,
      'circle-opacity': ['case', ['has', 'date'], 0, 0],
    },
  });
}

function _addHotspotLayers(map: mapboxgl.Map) {
  map.addLayer({
    id: HOTSPOT_CIRCLE_LAYER,
    type: 'circle',
    source: HEATMAP_SOURCE,
    paint: {
      'circle-radius': [
        'interpolate', ['linear'], ['get', 'weight'],
        0, 4,
        0.25, 7,
        0.5, 11,
        0.75, 16,
        1, 22,
      ],
      'circle-color': [
        'interpolate', ['linear'], ['get', 'weight'],
        0, 'hsla(174, 62%, 47%, 0.45)',
        0.25, 'hsla(50, 90%, 50%, 0.55)',
        0.5, 'hsla(38, 92%, 55%, 0.65)',
        0.75, 'hsla(15, 80%, 55%, 0.75)',
        1, 'hsla(0, 72%, 55%, 0.85)',
      ],
      'circle-stroke-color': [
        'interpolate', ['linear'], ['get', 'weight'],
        0, 'hsla(174, 62%, 47%, 0.6)',
        0.5, 'hsla(38, 92%, 55%, 0.7)',
        1, 'hsla(0, 72%, 55%, 0.9)',
      ],
      'circle-stroke-width': 1.5,
      'circle-opacity': 0.85,
    },
  });

  // Transparent hit-target for hover (unique ID so it doesn't overwrite visible circles)
  // Reference 'date' in paint so Mapbox preserves it in feature properties for tooltips
  map.addLayer({
    id: HOTSPOT_HIT_LAYER,
    type: 'circle',
    source: HEATMAP_SOURCE,
    paint: {
      'circle-radius': [
        'interpolate', ['linear'], ['get', 'weight'],
        0, 6, 1, 24,
      ],
      'circle-color': 'transparent',
      'circle-stroke-width': 0,
      'circle-opacity': ['case', ['has', 'date'], 0, 0],
    },
  });
}

export function addCrimeHeatmap(map: mapboxgl.Map, _lat: number, _lng: number, points?: HeatmapPoint[], mode: HeatmapDisplayMode = 'density') {
  if (!map.isStyleLoaded()) {
    map.once('style.load', () => addCrimeHeatmap(map, _lat, _lng, points, mode));
    return;
  }

  removeCrimeHeatmap(map);

  if (!points || points.length === 0) return;

  _lastHeatmapData = { lat: _lat, lng: _lng, points, mode };

  const features: GeoJSON.Feature[] = points.map((p) => ({
    type: 'Feature',
    geometry: {
      type: 'Point',
      coordinates: [p.lng, p.lat],
    },
    properties: {
      weight: p.weight,
      type: p.type || 'Unknown Incident',
      description: p.description || '',
      date: (p as { date?: string }).date || '',
    },
  }));

  const data: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features };

  map.addSource(HEATMAP_SOURCE, {
    type: 'geojson',
    data,
    generateId: true,
  });

  if (mode === 'hotspots') {
    _addHotspotLayers(map);
  } else {
    _addDensityLayers(map);
  }
}

export function removeCrimeHeatmap(map: mapboxgl.Map) {
  if (!map.isStyleLoaded()) return;
  try {
    if (map.getLayer(HEATMAP_CIRCLE_LAYER)) map.removeLayer(HEATMAP_CIRCLE_LAYER);
    if (map.getLayer(HOTSPOT_HIT_LAYER)) map.removeLayer(HOTSPOT_HIT_LAYER);
    if (map.getLayer(HOTSPOT_CIRCLE_LAYER)) map.removeLayer(HOTSPOT_CIRCLE_LAYER);
    if (map.getLayer(HEATMAP_LAYER)) map.removeLayer(HEATMAP_LAYER);
    if (map.getSource(HEATMAP_SOURCE)) map.removeSource(HEATMAP_SOURCE);
  } catch { /* style may have been swapped */ }
}

// ─── Citizen live-incident heatmap ───

export function addCitizenHeatmap(map: mapboxgl.Map, points?: HeatmapPoint[]) {
  removeCitizenHeatmap(map);
  if (!points || points.length === 0) return;

  _lastCitizenData = points;

  const features: GeoJSON.Feature[] = points.map((p) => ({
    type: 'Feature',
    geometry: { type: 'Point', coordinates: [p.lng, p.lat] },
    properties: { weight: p.weight, type: p.type || 'Incident', ts: p.ts || 0 },
  }));

  map.addSource(CITIZEN_HEATMAP_SOURCE, {
    type: 'geojson',
    data: { type: 'FeatureCollection', features },
  });

  map.addLayer({
    id: CITIZEN_HEATMAP_LAYER,
    type: 'heatmap',
    source: CITIZEN_HEATMAP_SOURCE,
    paint: {
      'heatmap-weight': ['interpolate', ['linear'], ['get', 'weight'], 0, 0, 1, 1],
      'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 10, 0.6, 15, 2.5],
      'heatmap-color': [
        'interpolate',
        ['linear'],
        ['heatmap-density'],
        0, 'rgba(0, 0, 0, 0)',
        0.1, 'hsla(270, 60%, 60%, 0.2)',
        0.3, 'hsla(280, 70%, 50%, 0.35)',
        0.5, 'hsla(300, 75%, 50%, 0.5)',
        0.7, 'hsla(330, 80%, 50%, 0.6)',
        1.0, 'hsla(350, 85%, 50%, 0.75)',
      ],
      'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 10, 18, 15, 35],
      'heatmap-opacity': ['interpolate', ['linear'], ['zoom'], 12, 0.8, 18, 0.3],
    },
  });

  map.addLayer({
    id: CITIZEN_HEATMAP_CIRCLE_LAYER,
    type: 'circle',
    source: CITIZEN_HEATMAP_SOURCE,
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 15, 15, 30],
      'circle-color': 'transparent',
      'circle-stroke-width': 0,
    },
  });
}

export function removeCitizenHeatmap(map: mapboxgl.Map) {
  if (map.getLayer(CITIZEN_HEATMAP_CIRCLE_LAYER)) map.removeLayer(CITIZEN_HEATMAP_CIRCLE_LAYER);
  if (map.getLayer(CITIZEN_HEATMAP_LAYER)) map.removeLayer(CITIZEN_HEATMAP_LAYER);
  if (map.getSource(CITIZEN_HEATMAP_SOURCE)) map.removeSource(CITIZEN_HEATMAP_SOURCE);
}

/**
 * Re-add heatmap, POIs, and route after a style reload (e.g. theme toggle).
 */
export function restoreMapLayers(map: mapboxgl.Map) {
  if (_lastHeatmapData) {
    addCrimeHeatmap(map, _lastHeatmapData.lat, _lastHeatmapData.lng, _lastHeatmapData.points, _lastHeatmapData.mode);
  }
  if (_lastPOIs?.length) addPOIMarkers(map, _lastPOIs);
  if (_lastCitizenData) {
    addCitizenHeatmap(map, _lastCitizenData);
  }
  if (_lastRouteSegments && _lastRoutePolyline) {
    addRouteToMap(map, _lastRouteSegments, _lastRoutePolyline);
  }
}

/**
 * Draw color-coded route segments on the map, following the actual road geometry.
 */
export function addRouteToMap(map: mapboxgl.Map, segments: RouteSegment[], polyline: number[][]) {
  removeRouteFromMap(map);

  _lastRouteSegments = segments;
  _lastRoutePolyline = polyline;

  // Color route segments by danger: green = safe, amber = caution, red = danger
  const riskColor: Record<string, string> = {
    safe: '#22c55e',    // green
    caution: '#f59e0b', // amber
    danger: '#dc2626',  // red-600, more visible
  };

  // polyline is [[lat, lng], ...] — convert to [lng, lat] for Mapbox
  const polyCoords = polyline.map(([lat, lng]) => [lng, lat] as [number, number]);

  // Helper: find the index in polyCoords closest to a given [lat, lng]
  const findClosestIndex = (lat: number, lng: number, startFrom: number = 0): number => {
    let bestIdx = startFrom;
    let bestDist = Infinity;
    for (let j = startFrom; j < polyCoords.length; j++) {
      const dx = polyCoords[j][0] - lng;
      const dy = polyCoords[j][1] - lat;
      const d = dx * dx + dy * dy;
      if (d < bestDist) {
        bestDist = d;
        bestIdx = j;
      }
    }
    return bestIdx;
  };

  // Map each segment to a slice of the full polyline
  let searchFrom = 0;
  segments.forEach((seg, i) => {
    const startIdx = findClosestIndex(seg.startLat, seg.startLng, searchFrom);
    const endIdx = findClosestIndex(seg.endLat, seg.endLng, startIdx);
    searchFrom = endIdx;

    // Slice the polyline for this segment (include both endpoints)
    const sliceCoords = polyCoords.slice(startIdx, Math.max(endIdx + 1, startIdx + 2));

    // Fallback: if we only got 1 point, draw a straight line
    const coords = sliceCoords.length >= 2
      ? sliceCoords
      : [[seg.startLng, seg.startLat], [seg.endLng, seg.endLat]];

    const sourceId = `${ROUTE_SOURCE}-${i}`;
    const layerId = `${ROUTE_LAYER_BASE}${i}`;

    const geojson: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: [{
        type: 'Feature',
        geometry: {
          type: 'LineString',
          coordinates: coords,
        },
        properties: { riskLevel: seg.riskLevel, score: seg.safetyScore },
      }],
    };

    map.addSource(sourceId, { type: 'geojson', data: geojson });

    // Outline
    map.addLayer({
      id: `${layerId}-outline`,
      type: 'line',
      source: sourceId,
      paint: {
        'line-color': '#000000',
        'line-width': 8,
        'line-opacity': 0.15,
      },
      layout: { 'line-cap': 'round', 'line-join': 'round' },
    });

    // Colored line — danger segments are thicker for visibility
    const lineWidth = seg.riskLevel === 'danger' ? 6 : seg.riskLevel === 'caution' ? 5.5 : 5;
    map.addLayer({
      id: layerId,
      type: 'line',
      source: sourceId,
      paint: {
        'line-color': riskColor[seg.riskLevel] || riskColor.caution,
        'line-width': lineWidth,
        'line-opacity': 0.95,
      },
      layout: { 'line-cap': 'round', 'line-join': 'round' },
    });
  });

  // Fit map to route bounds
  if (polyline.length >= 2) {
    const bounds = new mapboxgl.LngLatBounds();
    polyline.forEach(([lat, lng]) => bounds.extend([lng, lat]));
    map.fitBounds(bounds, { padding: 80, duration: 1500, pitch: 40 });
  }
}

/**
 * Remove all route layers from the map.
 */
export function removeRouteFromMap(map: mapboxgl.Map) {
  _lastRouteSegments = null;
  _lastRoutePolyline = null;
  removeDestinationMarker();

  if (!map.isStyleLoaded()) return;
  try {
    const style = map.getStyle();
    if (style?.layers) {
      for (const layer of style.layers) {
        if (layer.id.startsWith(ROUTE_LAYER_BASE)) {
          map.removeLayer(layer.id);
        }
      }
    }
    if (style?.sources) {
      for (const srcId of Object.keys(style.sources)) {
        if (srcId.startsWith(ROUTE_SOURCE)) {
          map.removeSource(srcId);
        }
      }
    }
  } catch { /* style may have been swapped */ }
}

/**
 * Add/update a user location marker on the map.
 */
/** Center/searched location marker with hover/click tooltip */
let _centerMarker: mapboxgl.Marker | null = null;
let _centerPopup: mapboxgl.Popup | null = null;

export function setCenterMarker(map: mapboxgl.Map, lat: number, lng: number, locationName?: string) {
  const label = locationName || 'Searched location';
  if (_centerMarker) {
    _centerMarker.setLngLat([lng, lat]);
    if (_centerPopup) _centerPopup.setLngLat([lng, lat]).setHTML(`<div class="map-marker-tooltip">${escapeHtml(label)}</div>`);
    return;
  }
  const el = document.createElement('div');
  el.className = 'center-location-marker';
  el.style.cssText = `
    width: 20px; height: 20px; border-radius: 50%;
    background: hsl(38, 92%, 55%);
    border: 3px solid white;
    box-shadow: 0 0 0 2px hsl(38, 92%, 55%);
    cursor: pointer;
  `;
  const popup = new mapboxgl.Popup({
    closeButton: false,
    offset: 20,
    className: 'map-marker-popup',
  }).setLngLat([lng, lat]).setHTML(`<div class="map-marker-tooltip">${escapeHtml(label)}</div>`);
  _centerPopup = popup;
  const marker = new mapboxgl.Marker({ element: el })
    .setLngLat([lng, lat])
    .setPopup(popup)
    .addTo(map);
  el.addEventListener('mouseenter', () => popup.addTo(map));
  el.addEventListener('mouseleave', () => popup.remove());
  el.addEventListener('click', () => { popup.remove(); popup.addTo(map); });
  _centerMarker = marker;
}

function escapeHtml(s: string): string {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}
export function removeCenterMarker() {
  _centerPopup?.remove();
  _centerPopup = null;
  _centerMarker?.remove();
  _centerMarker = null;
}

/** Destination (route end) marker */
let _destMarker: mapboxgl.Marker | null = null;
let _destPopup: mapboxgl.Popup | null = null;

export function setDestinationMarker(map: mapboxgl.Map, lat: number, lng: number, label?: string) {
  const name = label || 'Destination';
  if (_destMarker) {
    _destMarker.setLngLat([lng, lat]);
    if (_destPopup) _destPopup.setLngLat([lng, lat]).setHTML(`<div class="map-marker-tooltip">${escapeHtml(name)}</div>`);
    return;
  }
  const el = document.createElement('div');
  el.className = 'destination-marker';
  el.innerHTML = `
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" fill="hsl(0, 72%, 51%)" stroke="white" stroke-width="2" stroke-linejoin="round"/>
      <circle cx="12" cy="9" r="2.5" fill="white"/>
    </svg>
  `;
  el.style.cssText = `filter: drop-shadow(0 2px 4px rgba(0,0,0,0.35)); cursor: pointer;`;
  const popup = new mapboxgl.Popup({
    closeButton: false,
    offset: 20,
    className: 'map-marker-popup',
  }).setLngLat([lng, lat]).setHTML(`<div class="map-marker-tooltip">${escapeHtml(name)}</div>`);
  _destPopup = popup;
  const marker = new mapboxgl.Marker({ element: el, anchor: 'bottom' })
    .setLngLat([lng, lat])
    .setPopup(popup)
    .addTo(map);
  el.addEventListener('mouseenter', () => popup.addTo(map));
  el.addEventListener('mouseleave', () => popup.remove());
  el.addEventListener('click', () => { popup.remove(); popup.addTo(map); });
  _destMarker = marker;
}

export function removeDestinationMarker() {
  _destPopup?.remove();
  _destPopup = null;
  _destMarker?.remove();
  _destMarker = null;
}

let _userMarker: mapboxgl.Marker | null = null;
export function updateUserMarker(map: mapboxgl.Map, lat: number, lng: number) {
  if (_userMarker) {
    _userMarker.setLngLat([lng, lat]);
  } else {
    const el = document.createElement('div');
    el.className = 'user-location-marker';
    el.innerHTML = `
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="6" r="3.5" fill="hsl(217, 91%, 55%)" stroke="white" stroke-width="2"/>
        <path d="M6 22 C6 17 8.5 14 12 14 C15.5 14 18 17 18 22" stroke="hsl(217, 91%, 55%)" stroke-width="2" stroke-linecap="round" fill="none"/>
        <path d="M6 22 C6 17 8.5 14 12 14 C15.5 14 18 17 18 22" stroke="white" stroke-width="2.2" stroke-linecap="round" fill="none" opacity="0.9"/>
      </svg>
    `;
    el.style.cssText = `filter: drop-shadow(0 2px 6px rgba(0,0,0,0.35)); cursor: default;`;
    _userMarker = new mapboxgl.Marker({ element: el, anchor: 'bottom' }).setLngLat([lng, lat]).addTo(map);
  }
}

export function removeUserMarker() {
  _userMarker?.remove();
  _userMarker = null;
}

let _poiPopup: mapboxgl.Popup | null = null;
let _poiEnterHandler: ((e: mapboxgl.MapLayerMouseEvent) => void) | null = null;
let _poiLeaveHandler: (() => void) | null = null;

/** Add safe-place POI markers (hospitals, police, etc.) to the map */
export function addPOIMarkers(map: mapboxgl.Map, pois: NearbyPOI[]) {
  removePOIMarkers(map);
  _lastPOIs = pois.length ? pois : null;
  if (!pois.length) return;

  const features: GeoJSON.Feature[] = pois.map((p) => ({
    type: 'Feature' as const,
    geometry: { type: 'Point' as const, coordinates: [p.lng, p.lat] },
    properties: { name: p.name, type: p.type, address: p.address },
  }));
  const data: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features };

  map.addSource(POI_SOURCE, { type: 'geojson', data });
  map.addLayer({
    id: 'poi-circles',
    type: 'circle',
    source: POI_SOURCE,
    paint: {
      'circle-radius': 8,
      'circle-color': '#22c55e',
      'circle-stroke-width': 2,
      'circle-stroke-color': '#fff',
    },
  });

  _poiPopup = new mapboxgl.Popup({ closeButton: false, offset: 12, className: 'map-marker-popup' });
  _poiEnterHandler = (e: mapboxgl.MapLayerMouseEvent) => {
    map.getCanvas().style.cursor = 'pointer';
    if (e.features?.[0]?.properties?.name) {
      const { name, address } = e.features[0].properties as { name: string; address?: string };
      const coords = (e.features[0].geometry as GeoJSON.Point).coordinates.slice() as [number, number];
      _poiPopup!.setLngLat(coords).setHTML(`<div class="map-marker-tooltip">${escapeHtml(name)}${address ? `<br><span class="text-muted-foreground text-xs">${escapeHtml(address)}</span>` : ''}</div>`).addTo(map);
    }
  };
  _poiLeaveHandler = () => {
    map.getCanvas().style.cursor = '';
    _poiPopup!.remove();
  };
  map.on('mouseenter', 'poi-circles', _poiEnterHandler);
  map.on('mouseleave', 'poi-circles', _poiLeaveHandler);
}

/** Show the same POI tooltip popup at the given POI (e.g. when selecting from list). */
export function showPOIPopupAt(map: mapboxgl.Map, poi: NearbyPOI): void {
  const html = `<div class="map-marker-tooltip">${escapeHtml(poi.name)}${poi.address ? `<br><span class="text-muted-foreground text-xs">${escapeHtml(poi.address)}</span>` : ''}</div>`;
  const coords: [number, number] = [poi.lng, poi.lat];
  // Mapbox Popup does not reliably support re-adding after remove(); create a new instance each time
  if (_poiPopup) _poiPopup.remove();
  new mapboxgl.Popup({ closeButton: false, offset: 12, className: 'map-marker-popup' })
    .setLngLat(coords).setHTML(html).addTo(map);
}

export function removePOIMarkers(map: mapboxgl.Map) {
  if (_poiEnterHandler) map.off('mouseenter', 'poi-circles', _poiEnterHandler);
  if (_poiLeaveHandler) map.off('mouseleave', 'poi-circles', _poiLeaveHandler);
  _poiEnterHandler = null;
  _poiLeaveHandler = null;
  _poiPopup?.remove();
  _poiPopup = null;
  if (map.getLayer('poi-circles')) map.removeLayer('poi-circles');
  if (map.getSource(POI_SOURCE)) map.removeSource(POI_SOURCE);
  _lastPOIs = null;
}

export function clearAllMapData() {
  _lastHeatmapData = null;
  _lastPOIs = null;
  _lastCitizenData = null;
  _lastRouteSegments = null;
  _lastRoutePolyline = null;
  removeCenterMarker();
  removeDestinationMarker();
}
