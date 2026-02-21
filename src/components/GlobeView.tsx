import { useEffect, useRef, useCallback, useState } from 'react';
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';
import { MAPBOX_TOKEN } from '@/lib/config';

interface GlobeViewProps {
  onMapReady?: (map: mapboxgl.Map | null) => void;
  onStyleReloaded?: () => void;
}

function getTheme(): 'dark' | 'light' {
  if (typeof document === 'undefined') return 'dark';
  return document.documentElement.classList.contains('light') ? 'light' : 'dark';
}

const STYLES = {
  dark: 'mapbox://styles/mapbox/dark-v11',
  light: 'mapbox://styles/mapbox/light-v11',
} as const;

const FOG_CONFIG = {
  dark: {
    color: 'hsl(222, 47%, 8%)',
    'high-color': 'hsl(222, 47%, 14%)',
    'horizon-blend': 0.08,
    'space-color': 'hsl(222, 47%, 4%)',
    'star-intensity': 0.4,
  },
  light: {
    color: 'hsl(210, 40%, 96%)',
    'high-color': 'hsl(210, 40%, 80%)',
    'horizon-blend': 0.05,
    'space-color': 'hsl(210, 40%, 90%)',
    'star-intensity': 0.0,
  },
} as const;

// Module-level flag so flyToLocation can stop the rotation
let _rotationPaused = false;

export function pauseGlobeRotation() {
  _rotationPaused = true;
}

const GlobeView = ({ onMapReady, onStyleReloaded }: GlobeViewProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const initialThemeRef = useRef(true);
  const [theme, setTheme] = useState<'dark' | 'light'>(getTheme);
  const hasToken = MAPBOX_TOKEN && MAPBOX_TOKEN !== 'YOUR_MAPBOX_TOKEN_HERE';

  const initMap = useCallback(() => {
    if (!containerRef.current || mapRef.current || !hasToken) {
      if (!hasToken) onMapReady?.(null);
      return;
    }

    mapboxgl.accessToken = MAPBOX_TOKEN;

    // Read the current theme at mount time
    const currentTheme = getTheme();

    try {
      const map = new mapboxgl.Map({
        container: containerRef.current,
        style: STYLES[currentTheme],
        center: [0, 20],
        zoom: 1.5,
        projection: 'globe',
        interactive: true,
        attributionControl: false,
      });

      map.on('style.load', () => {
        map.setProjection('globe');
        map.setFog(FOG_CONFIG[currentTheme] as mapboxgl.FogSpecification);
      });

      let rafId: number;
      let lastTime = performance.now();
      const ROTATION_SPEED = 0.0012; // degrees per ms

      _rotationPaused = false;

      const rotateGlobe = (now: number) => {
        if (!map.getContainer().parentElement) return;
        // If rotation is paused (flyTo in progress), skip entirely
        if (_rotationPaused) return;
        const dt = now - lastTime;
        lastTime = now;
        if (map.getZoom() > 3) {
          rafId = requestAnimationFrame(rotateGlobe);
          return;
        }
        const center = map.getCenter();
        center.lng -= dt * ROTATION_SPEED;
        map.jumpTo({ center });
        rafId = requestAnimationFrame(rotateGlobe);
      };
      rafId = requestAnimationFrame(rotateGlobe);

      const stopRotation = () => {
        _rotationPaused = true;
        cancelAnimationFrame(rafId);
      };
      map.on('mousedown', stopRotation);
      map.on('touchstart', stopRotation);

      mapRef.current = map;
      onMapReady?.(map);

      return () => {
        cancelAnimationFrame(rafId);
        _rotationPaused = true;
        map.remove();
        mapRef.current = null;
      };
    } catch {
      onMapReady?.(null);
    }
    // Intentionally omit theme: map is created once with initial theme. Theme changes
    // are handled by the effect below (setStyle + restore viewport), not by re-creating the map.
  }, [onMapReady, hasToken]);

  useEffect(() => {
    const cleanup = initMap();
    return () => cleanup?.();
  }, [initMap]);

  // Observe <html> class changes for theme toggle
  useEffect(() => {
    const observer = new MutationObserver(() => {
      const newTheme = getTheme();
      setTheme((prev) => (prev !== newTheme ? newTheme : prev));
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

  // When theme changes after initial render: preserve viewport, swap style only
  useEffect(() => {
    // Skip the initial mount — initMap already sets the correct style
    if (initialThemeRef.current) {
      initialThemeRef.current = false;
      return;
    }
    const map = mapRef.current;
    if (!map) return;
    const center = map.getCenter();
    const zoom = map.getZoom();
    const pitch = map.getPitch();
    const bearing = map.getBearing();
    map.setStyle(STYLES[theme]);
    map.once('style.load', () => {
      map.setProjection('globe');
      // Apply fog after a short delay to ensure the projection is fully initialized.
      // This fixes stars not reappearing when switching back to dark mode.
      setTimeout(() => {
        map.setFog(FOG_CONFIG[theme] as mapboxgl.FogSpecification);
      }, 50);
      map.jumpTo({ center, zoom, pitch, bearing });
      onStyleReloaded?.();
    });
  }, [theme, onStyleReloaded]);

  return (
    <div
      ref={containerRef}
      className="absolute inset-0 w-full h-full"
      style={{
        zIndex: 0,
        background: !hasToken
          ? theme === 'dark'
            ? 'radial-gradient(ellipse at 50% 50%, hsl(222, 47%, 10%) 0%, hsl(222, 47%, 4%) 100%)'
            : 'radial-gradient(ellipse at 50% 50%, hsl(210, 40%, 96%) 0%, hsl(210, 40%, 88%) 100%)'
          : undefined,
      }}
    />
  );
};

export default GlobeView;

export function flyToLocation(
  map: mapboxgl.Map | null,
  lat: number,
  lng: number,
  onComplete?: () => void,
  options?: { duration?: number }
) {
  if (!map) return;
  _rotationPaused = true;
  map.stop();
  const duration = options?.duration ?? 2800;
  const opts = {
    center: [lng, lat] as [number, number],
    zoom: 14,
    pitch: 50,
    bearing: -20,
    duration,
    essential: true,
    easing: (t: number) => 1 - Math.pow(1 - t, 3),
  };
  if (onComplete) {
    map.once('moveend', onComplete);
  }
  map.flyTo(opts);
}
