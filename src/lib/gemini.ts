import { API_BASE_URL } from '@/lib/config';

export interface AISafetyTip {
  title: string;
  description: string;
  priority: 'high' | 'medium' | 'low';
}

export interface EnrichedTipsContext {
  liveIncidentSummary?: string;
  nearbyPOIs?: string[];
  neighborhoodContext?: string;
  sentimentSummary?: string;
}

/**
 * Generate AI safety tips via backend proxy (keeps API key server-side).
 * Falls back to static tips on failure.
 */
export async function generateSafetyTips(
  locationName: string,
  safetyIndex: number,
  incidentTypes: string[],
  timeOfTravel: string,
  peopleCount: number,
  gender: string,
  enrichedContext?: EnrichedTipsContext
): Promise<AISafetyTip[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/ai-tips`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        locationName,
        safetyIndex,
        incidentTypes,
        timeOfTravel,
        peopleCount,
        gender,
        liveIncidentSummary: enrichedContext?.liveIncidentSummary ?? '',
        nearbyPOIs: enrichedContext?.nearbyPOIs ?? [],
        neighborhoodContext: enrichedContext?.neighborhoodContext ?? '',
        sentimentSummary: enrichedContext?.sentimentSummary ?? '',
      }),
    });
    if (!res.ok) throw new Error(`AI tips request failed: ${res.status}`);
    const data = await res.json();
    const tips: AISafetyTip[] = data.tips || [];
    return tips.slice(0, 4);
  } catch (err) {
    console.warn('AI tips unavailable, using fallback tips', err);
    return getFallbackTips(safetyIndex, incidentTypes);
  }
}

function getFallbackTips(safetyIndex: number, incidentTypes: string[]): AISafetyTip[] {
  const tips: AISafetyTip[] = [
    {
      title: 'Stay Aware of Surroundings',
      description: 'Keep your head up, phone away, and maintain awareness especially in unfamiliar areas.',
      priority: 'high',
    },
    {
      title: 'Share Your Location',
      description: 'Let someone you trust know your travel plans and share live location via your phone.',
      priority: 'medium',
    },
  ];

  if (safetyIndex < 50) {
    tips.push({
      title: 'Travel in Groups',
      description: 'This area has elevated risk. Traveling with others significantly reduces vulnerability.',
      priority: 'high',
    });
  }

  if (incidentTypes.some((t) => t.toLowerCase().includes('theft'))) {
    tips.push({
      title: 'Secure Valuables',
      description: 'Keep bags zipped and close to your body. Avoid displaying expensive devices openly.',
      priority: 'medium',
    });
  }

  if (incidentTypes.some((t) => t.toLowerCase().includes('vehicle'))) {
    tips.push({
      title: 'Vehicle Safety',
      description: 'Don\'t leave valuables visible in your car. Park in well-lit, populated areas.',
      priority: 'medium',
    });
  }

  tips.push({
    title: 'Emergency Contacts',
    description: 'Save local emergency numbers. In the US, dial 911. Have a charged phone at all times.',
    priority: 'low',
  });

  return tips.slice(0, 4);
}
