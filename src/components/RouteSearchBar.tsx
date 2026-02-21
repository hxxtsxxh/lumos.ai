import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, MapPin, Loader2, Navigation, LocateFixed, ArrowLeftRight, Route } from 'lucide-react';
import { fetchAutocomplete } from '@/lib/api';

export type SearchMode = 'single' | 'route';

interface RouteSearchBarProps {
  onSearchSingle: (query: string) => void;
  onSearchRoute: (origin: string, destination: string) => void;
  onUseCurrentLocation?: () => void;
  isLoading?: boolean;
  isMinimized?: boolean;
  mode: SearchMode;
  onModeChange: (mode: SearchMode) => void;
  /** Prefill origin (e.g. when viewing a place or route result) */
  currentLocationText?: string;
  /** When in route mode, use this to autopopulate the start field (e.g. from "Use current location") */
  currentOriginFromLocation?: string;
  /** Optional: register a callback so parent can push current location display name into start field (used on landing in route mode) */
  onRegisterOriginPrefill?: (setOriginFromLocation: ((name: string) => void) | null) => void;
  /** Prefill destination when viewing route result so it doesn't reset to placeholder */
  currentDestinationText?: string;
}

const defaultSuggestions: Array<{ label: string; icon: string }> = [];

const destinationQuickOptions = [
  { label: 'Restaurant', icon: '🍽️' },
  { label: 'Coffee shop', icon: '☕' },
  { label: 'Park', icon: '🌳' },
  { label: 'Museum', icon: '🏛️' },
  { label: 'Shopping center', icon: '🛒' },
  { label: 'Transit station', icon: '🚉' },
];

const RouteSearchBar = ({
  onSearchSingle,
  onSearchRoute,
  onUseCurrentLocation,
  isLoading = false,
  isMinimized = false,
  mode,
  onModeChange,
  currentLocationText,
  currentOriginFromLocation,
  onRegisterOriginPrefill,
  currentDestinationText,
}: RouteSearchBarProps) => {
  const [origin, setOrigin] = useState('');
  const [destination, setDestination] = useState('');
  const [query, setQuery] = useState(''); // single mode
  const [activeField, setActiveField] = useState<'origin' | 'destination' | 'single' | null>(null);
  const [suggestions, setSuggestions] = useState<Array<{ description: string; placeId: string }>>([]);
  const [isAutocompleting, setIsAutocompleting] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const originRef = useRef<HTMLInputElement>(null);
  const destRef = useRef<HTMLInputElement>(null);
  const singleRef = useRef<HTMLInputElement>(null);

  const activeValue = activeField === 'origin' ? origin : activeField === 'destination' ? destination : query;

  // Fill single search query when parent passes current location text
  useEffect(() => {
    if (currentLocationText && mode === 'single') {
      setQuery(currentLocationText);
    }
  }, [currentLocationText, mode]);

  // In route mode, autopopulate start field when parent provides current location (e.g. "Use current location" clicked)
  useEffect(() => {
    if (mode === 'route' && currentOriginFromLocation != null && currentOriginFromLocation !== '') {
      setOrigin(currentOriginFromLocation);
    }
  }, [mode, currentOriginFromLocation]);

  // Let parent push current location into start field (fixes landing page when "Use current location" is clicked in route mode)
  useEffect(() => {
    if (mode === 'route' && onRegisterOriginPrefill) {
      onRegisterOriginPrefill(setOrigin);
      return () => onRegisterOriginPrefill(null);
    }
  }, [mode, onRegisterOriginPrefill]);

  // Keep destination in sync when viewing route result so it doesn't revert to placeholder
  useEffect(() => {
    if (mode === 'route' && currentDestinationText) {
      setDestination(currentDestinationText);
    }
  }, [mode, currentDestinationText]);

  // Debounced autocomplete — shorter delay (150ms) so options feel responsive
  useEffect(() => {
    if (!activeValue || activeValue.length < 2) {
      setSuggestions([]);
      return;
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setIsAutocompleting(true);
      const results = await fetchAutocomplete(activeValue);
      setSuggestions(results);
      setIsAutocompleting(false);
    }, 150);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [activeValue]);

  const handleSelectSuggestion = useCallback((text: string) => {
    if (activeField === 'origin') {
      setOrigin(text);
      // Auto-focus destination
      setTimeout(() => destRef.current?.focus(), 100);
    } else if (activeField === 'destination') {
      setDestination(text);
    } else {
      setQuery(text);
      onSearchSingle(text);
    }
    setSuggestions([]);
    setActiveField(null);
  }, [activeField, onSearchSingle]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (mode === 'single' && query.trim()) {
      onSearchSingle(query.trim());
    } else if (mode === 'route' && origin.trim() && destination.trim()) {
      onSearchRoute(origin.trim(), destination.trim());
    }
  };

  const swapOriginDest = () => {
    const tmp = origin;
    setOrigin(destination);
    setDestination(tmp);
  };

  const showSuggestions = activeField && activeValue.length >= 2 && suggestions.length > 0;
  const showSuggestionsLoading = activeField && activeValue.length >= 2 && isAutocompleting;
  const showDefaults = activeField && !activeValue && !isMinimized && defaultSuggestions.length > 0;
  const showDestinationDefaults = mode === 'route' && activeField === 'destination' && !destination && !isMinimized;

  const isDropdownOpen = showSuggestions || showSuggestionsLoading || (showDefaults && !showDestinationDefaults) || showDestinationDefaults;

  return (
    <motion.div
      layout
      className={`w-full ${isMinimized ? 'max-w-md' : 'max-w-[620px]'} mx-auto px-1 sm:px-0`}
      initial={false}
    >
      {/* Mode toggle pills */}
      {!isMinimized && (
        <div className="flex items-center justify-center gap-2 mb-4">
          <button
            type="button"
            onClick={() => onModeChange('single')}
            className={`px-5 py-2 rounded-full text-xs font-medium transition-all duration-200 ${mode === 'single'
                ? 'bg-primary/15 text-primary border border-primary/30'
                : 'bg-secondary/40 text-muted-foreground hover:text-foreground hover:bg-secondary/70 border border-transparent'
              }`}
            aria-pressed={mode === 'single'}
          >
            <MapPin className="w-3.5 h-3.5 inline mr-1.5 -mt-[1px]" />
            Check a Place
          </button>
          <button
            type="button"
            onClick={() => onModeChange('route')}
            className={`px-5 py-2 rounded-full text-xs font-medium transition-all duration-200 ${mode === 'route'
                ? 'bg-primary/15 text-primary border border-primary/30'
                : 'bg-secondary/40 text-muted-foreground hover:text-foreground hover:bg-secondary/70 border border-transparent'
              }`}
            aria-pressed={mode === 'route'}
          >
            <Navigation className="w-3.5 h-3.5 inline mr-1.5 -mt-[1px]" />
            Plan a Route
          </button>
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <AnimatePresence mode="wait">
          {mode === 'single' ? (
            <motion.div
              key="single"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className={`search-bar-container relative transition-all duration-300 ${
                isMinimized ? 'rounded-full' : isDropdownOpen ? 'rounded-t-[28px] rounded-b-none' : 'rounded-full'
              } ${activeField === 'single' ? 'search-bar-focused' : ''}`}
            >
              <div className={`flex items-center ${isMinimized ? 'px-3 sm:px-4 py-2.5' : 'px-4 sm:px-6 py-3 sm:py-3.5'}`}>
                <Search className={`${isMinimized ? 'w-4 h-4' : 'w-5 h-5'} text-muted-foreground mr-2 sm:mr-3 flex-shrink-0`} />
                <input
                  ref={singleRef}
                  data-search-input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onFocus={() => setActiveField('single')}
                  onBlur={() => setTimeout(() => setActiveField(null), 200)}
                  placeholder="Search a city, address, or place..."
                  className={`flex-1 bg-transparent text-foreground placeholder:text-muted-foreground/70 outline-none ${isMinimized ? 'text-sm' : 'text-sm sm:text-base'} font-normal min-w-0`}
                  aria-label="Search location"
                  autoComplete="off"
                />
                {isMinimized && currentLocationText && (
                  <button
                    type="button"
                    onClick={() => onModeChange('route')}
                    className="p-2 rounded-full text-muted-foreground hover:text-foreground hover:bg-secondary/60 transition-colors"
                    title="Plan route from this city"
                    aria-label="Plan route from this city"
                  >
                    <Route className="w-4 h-4" />
                  </button>
                )}
                <div className="flex items-center gap-1 ml-2">
                  {onUseCurrentLocation && !isMinimized && (
                    <button
                      type="button"
                      onClick={onUseCurrentLocation}
                      className="p-2 rounded-full text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors"
                      title="Use current location"
                      aria-label="Use current location"
                    >
                      <LocateFixed className="w-[18px] h-[18px]" />
                    </button>
                  )}
                  {!isMinimized && (
                    <div className="w-px h-6 bg-border/60 mx-1" />
                  )}
                  {isLoading || isAutocompleting ? (
                    <div className="p-2">
                      <Loader2 className="w-5 h-5 text-primary animate-spin" />
                    </div>
                  ) : (
                    <button
                      type="submit"
                      className={`${isMinimized ? 'p-1.5' : 'p-2'} rounded-full text-primary hover:bg-primary/10 transition-colors`}
                      aria-label="Search"
                    >
                      <Search className={`${isMinimized ? 'w-4 h-4' : 'w-5 h-5'}`} />
                    </button>
                  )}
                </div>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="route"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className={`search-bar-container relative transition-all duration-300 ${
                isMinimized ? 'rounded-2xl' : isDropdownOpen ? 'rounded-t-[24px] rounded-b-none' : 'rounded-[24px]'
              } ${activeField ? 'search-bar-focused' : ''}`}
            >
              {/* Origin field */}
              <div className={`flex items-center ${isMinimized ? 'px-3 sm:px-4 py-2' : 'px-4 sm:px-6 py-2.5 sm:py-3'}`}>
                <div className="w-5 h-5 rounded-full border-2 border-lumos-safe mr-3 flex-shrink-0 flex items-center justify-center">
                  <div className="w-2 h-2 rounded-full bg-lumos-safe" />
                </div>
                <input
                  ref={originRef}
                  data-search-input
                  type="text"
                  value={origin}
                  onChange={(e) => setOrigin(e.target.value)}
                  onFocus={() => setActiveField('origin')}
                  onBlur={() => setTimeout(() => setActiveField(null), 200)}
                  placeholder="Starting point..."
                  className="flex-1 bg-transparent text-foreground placeholder:text-muted-foreground/70 outline-none text-sm sm:text-[15px] font-normal min-w-0"
                  aria-label="Starting point"
                  autoComplete="off"
                />
                {onUseCurrentLocation && !origin && (
                  <button
                    type="button"
                    onClick={onUseCurrentLocation}
                    className="p-1.5 rounded-full hover:bg-primary/10 text-muted-foreground hover:text-primary transition-colors"
                    title="Use current location"
                  >
                    <LocateFixed className="w-4 h-4" />
                  </button>
                )}
              </div>

              {/* Divider with swap */}
              <div className="flex items-center px-4 sm:px-6">
                <div className="flex-1 border-t border-border/30" />
                <button
                  type="button"
                  onClick={swapOriginDest}
                  className="mx-2 p-1.5 rounded-full hover:bg-secondary/80 text-muted-foreground hover:text-foreground transition-colors"
                  title="Swap origin and destination"
                >
                  <ArrowLeftRight className="w-3.5 h-3.5" />
                </button>
                <div className="flex-1 border-t border-border/30" />
              </div>

              {/* Destination field */}
              <div className={`flex items-center ${isMinimized ? 'px-3 sm:px-4 py-2' : 'px-4 sm:px-6 py-2.5 sm:py-3'}`}>
                <div className="w-5 h-5 mr-3 flex-shrink-0 flex items-center justify-center text-lumos-danger">
                  <MapPin className="w-5 h-5" />
                </div>
                <input
                  ref={destRef}
                  type="text"
                  value={destination}
                  onChange={(e) => setDestination(e.target.value)}
                  onFocus={() => setActiveField('destination')}
                  onBlur={() => setTimeout(() => setActiveField(null), 200)}
                  placeholder="Where are you going?"
                  className="flex-1 bg-transparent text-foreground placeholder:text-muted-foreground/70 outline-none text-sm sm:text-[15px] font-normal min-w-0"
                  aria-label="Destination"
                  autoComplete="off"
                />
                {isLoading || isAutocompleting ? (
                  <div className="p-2">
                    <Loader2 className="w-5 h-5 text-primary animate-spin" />
                  </div>
                ) : (
                  <button
                    type="submit"
                    disabled={!origin.trim() || !destination.trim()}
                    className="p-2 rounded-full text-primary hover:bg-primary/10 transition-colors disabled:opacity-30 disabled:hover:bg-transparent"
                    aria-label="Analyze route"
                  >
                    <Navigation className="w-5 h-5" />
                  </button>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </form>

      <AnimatePresence>
        {/* Loading state while fetching suggestions — dropdown opens immediately */}
        {showSuggestionsLoading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="search-dropdown-container rounded-b-[24px] z-50 relative"
            role="status"
            aria-live="polite"
          >
            <div className="border-t border-border/20 mx-4" />
            <div className="flex items-center gap-3 px-6 py-3 text-muted-foreground">
              <Loader2 className="w-4 h-4 animate-spin flex-shrink-0" />
              <span className="text-sm">Searching...</span>
            </div>
          </motion.div>
        )}

        {/* Live autocomplete results */}
        {showSuggestions && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="search-dropdown-container rounded-b-[24px] z-50 relative"
            role="listbox"
          >
            <div className="border-t border-border/20 mx-4" />
            <div className="py-2">
              {suggestions.map((s) => (
                <button
                  key={s.placeId || s.description}
                  type="button"
                  role="option"
                  onMouseDown={() => handleSelectSuggestion(s.description)}
                  className="w-full flex items-center gap-3 px-6 py-2.5 text-left hover:bg-secondary/50 transition-colors text-foreground group"
                >
                  <MapPin className="w-4 h-4 text-muted-foreground/60 group-hover:text-primary flex-shrink-0 transition-colors" />
                  <span className="text-sm font-normal">{s.description}</span>
                </button>
              ))}
            </div>
          </motion.div>
        )}

        {/* Default suggestions when empty (single or origin) */}
        {showDefaults && !showDestinationDefaults && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="search-dropdown-container rounded-b-[24px] z-50 relative"
            role="listbox"
          >
            <div className="border-t border-border/20 mx-4" />
            <p className="text-[11px] text-muted-foreground/60 uppercase tracking-wider px-6 pt-3 pb-1 font-medium">Popular cities</p>
            <div className="pb-2">
              {defaultSuggestions.map((s) => (
                <button
                  key={s.label}
                  type="button"
                  role="option"
                  onMouseDown={() => handleSelectSuggestion(s.label)}
                  className="w-full flex items-center gap-3 px-6 py-2.5 text-left hover:bg-secondary/50 transition-colors text-foreground group"
                >
                  <span className="text-base">{s.icon}</span>
                  <span className="text-sm font-normal">{s.label}</span>
                </button>
              ))}
            </div>
          </motion.div>
        )}

        {/* "Where are you going?" quick options when destination is focused and empty */}
        {showDestinationDefaults && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="search-dropdown-container rounded-b-[24px] z-50 relative"
            role="listbox"
          >
            <div className="border-t border-border/20 mx-4" />
            <p className="text-[11px] text-muted-foreground/60 uppercase tracking-wider px-6 pt-3 pb-1 font-medium">Suggestions</p>
            <div className="pb-2">
              {destinationQuickOptions.map((s) => (
                <button
                  key={s.label}
                  type="button"
                  role="option"
                  onMouseDown={() => handleSelectSuggestion(s.label)}
                  className="w-full flex items-center gap-3 px-6 py-2.5 text-left hover:bg-secondary/50 transition-colors text-foreground group"
                >
                  <span className="text-base">{s.icon}</span>
                  <span className="text-sm font-normal">{s.label}</span>
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

export default RouteSearchBar;
