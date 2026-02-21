import { Share2, Copy, Check } from 'lucide-react';
import { useState } from 'react';
import type { SafetyData } from '@/types/safety';

interface ShareReportProps {
  data: SafetyData;
  locationName: string;
}

const ShareReport = ({ data, locationName }: ShareReportProps) => {
  const [copied, setCopied] = useState(false);

  const generateShareText = () => {
    const scoreLabel =
      data.safetyIndex >= 70 ? 'Generally Safe' : data.safetyIndex >= 40 ? 'Use Caution' : 'High Risk';

    const topIncidents = data.incidentTypes
      .slice(0, 3)
      .map((i) => `${i.type} (${Math.round(i.probability * 100)}%)`)
      .join(', ');

    return `🛡️ Lumos Safety Report — ${locationName}

Safety Index: ${data.safetyIndex}/100 (${scoreLabel})
Top Incidents: ${topIncidents}
Peak Risk: ${data.timeAnalysis.peakHours}
Safest Window: ${data.timeAnalysis.safestHours}

Powered by Lumos — Know Before You Go`;
  };

  const handleShare = async () => {
    const text = generateShareText();

    if (navigator.share) {
      try {
        await navigator.share({ title: `Lumos — ${locationName}`, text });
        return;
      } catch {
        // User cancelled or not supported — fall through to clipboard
      }
    }

    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleShare}
      className="header-btn flex items-center gap-1.5 sm:gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors glass-panel px-2.5 sm:px-4 py-2 rounded-xl"
    >
      {copied ? (
        <>
          <Check className="w-4 h-4 text-lumos-safe" />
          <span className="text-lumos-safe">Copied!</span>
        </>
      ) : (
        <>
          <Share2 className="w-4 h-4" />
          <span className="hidden sm:inline">Share</span>
        </>
      )}
    </button>
  );
};

export default ShareReport;
