// Lumos API Configuration
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Mapbox Configuration — set VITE_MAPBOX_TOKEN in your .env file
export const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || '';

// Google Maps API — set VITE_GOOGLE_MAPS_API_KEY in your .env file
export const GOOGLE_MAPS_API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '';

if (!MAPBOX_TOKEN) console.warn('Missing VITE_MAPBOX_TOKEN — map will not render.');
if (!GOOGLE_MAPS_API_KEY) console.warn('Missing VITE_GOOGLE_MAPS_API_KEY — geocoding may fail.');
