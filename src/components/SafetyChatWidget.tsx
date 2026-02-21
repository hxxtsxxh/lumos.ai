import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageCircle, X, Send, Sparkles, User } from 'lucide-react';
import { sendSafetyChatMessage } from '@/lib/api';
import type { FullSafetyResponse } from '@/lib/api';
import type { TravelParams, RouteAnalysisData } from '@/types/safety';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface SafetyChatWidgetProps {
  locationName: string;
  safetyData: FullSafetyResponse | null;
  routeData: RouteAnalysisData | null;
  params: TravelParams;
}

const SafetyChatWidget = ({ locationName, safetyData, routeData, params }: SafetyChatWidgetProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;

    const userMessage: ChatMessage = { role: 'user', content: trimmed };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const result = await sendSafetyChatMessage({
        message: trimmed,
        locationName: locationName || 'Unknown location',
        safetyIndex: safetyData?.safetyIndex ?? null,
        incidentTypes: safetyData?.incidentTypes?.map(i => i.type) ?? [],
        riskLevel: safetyData?.riskLevel ?? 'caution',
        timeOfTravel: params.timeOfTravel,
        conversationHistory: messages,
      });

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: result.reply || 'Sorry, I couldn\'t generate a response.',
      };
      setMessages(prev => [...prev, assistantMessage]);
    } catch {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: 'Sorry, something went wrong. Please try again.' },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <>
      {/* Toggle Button */}
      <AnimatePresence>
        {!isOpen && (
          <motion.button
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => setIsOpen(true)}
            className="fixed bottom-6 right-6 z-50 w-12 h-12 rounded-full bg-amber-500/90 hover:bg-amber-500 text-background shadow-lg shadow-amber-500/20 flex items-center justify-center transition-colors"
            aria-label="Open safety chat"
          >
            <MessageCircle className="w-5 h-5" />
          </motion.button>
        )}
      </AnimatePresence>

      {/* Chat Panel */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            className="fixed bottom-6 right-6 z-50 w-[380px] max-h-[520px] glass-panel flex flex-col overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-border/50">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-amber-500/15 border border-amber-500/25 flex items-center justify-center">
                  <Sparkles className="w-3.5 h-3.5 text-lumos-caution" />
                </div>
                <div>
                  <span className="font-display font-semibold text-sm text-foreground">LUMOS Chat</span>
                  <p className="text-[10px] text-muted-foreground leading-none mt-0.5">Safety Assistant</p>
                </div>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-secondary/80 text-muted-foreground hover:text-foreground transition-colors"
                aria-label="Close chat"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-[320px]">
              {messages.length === 0 && (
                <div className="text-center mt-10 space-y-3">
                  <div className="w-12 h-12 rounded-2xl mx-auto flex items-center justify-center bg-amber-500/10 border border-amber-500/20">
                    <Sparkles className="w-6 h-6 text-lumos-caution" />
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Ask me anything about safety
                  </p>
                  {locationName && (
                    <p className="text-xs text-muted-foreground/60">
                      Currently viewing: {locationName}
                    </p>
                  )}
                  <div className="flex flex-wrap justify-center gap-2 pt-2">
                    {['Is this area safe at night?', 'Nearby police stations?', 'Safety tips'].map(q => (
                      <button
                        key={q}
                        onClick={() => { setInput(q); inputRef.current?.focus(); }}
                        className="text-xs px-3 py-1.5 rounded-full bg-secondary/50 border border-border/50 text-muted-foreground hover:border-amber-500/40 hover:text-foreground transition-colors cursor-pointer"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {msg.role === 'assistant' && (
                    <div className="w-6 h-6 rounded-md bg-amber-500/15 border border-amber-500/25 flex items-center justify-center flex-shrink-0 mt-1">
                      <Sparkles className="w-3 h-3 text-lumos-caution" />
                    </div>
                  )}
                  <div
                    className={`max-w-[80%] rounded-xl px-3 py-2 text-sm whitespace-pre-wrap ${
                      msg.role === 'user'
                        ? 'bg-amber-500/90 text-background rounded-br-sm font-medium'
                        : 'bg-secondary/60 border border-border/40 text-foreground rounded-bl-sm'
                    }`}
                  >
                    {msg.content}
                  </div>
                  {msg.role === 'user' && (
                    <div className="w-6 h-6 rounded-md bg-secondary/80 border border-border/50 flex items-center justify-center flex-shrink-0 mt-1">
                      <User className="w-3 h-3 text-muted-foreground" />
                    </div>
                  )}
                </div>
              ))}

              {isLoading && (
                <div className="flex gap-2 items-center">
                  <div className="w-6 h-6 rounded-md bg-amber-500/15 border border-amber-500/25 flex items-center justify-center">
                    <Sparkles className="w-3 h-3 text-lumos-caution" />
                  </div>
                  <div className="bg-secondary/60 border border-border/40 rounded-xl px-4 py-2.5 flex gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-lumos-caution/70 animate-bounce [animation-delay:0ms]" />
                    <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/40 animate-bounce [animation-delay:150ms]" />
                    <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/40 animate-bounce [animation-delay:300ms]" />
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="px-3 py-2.5 border-t border-border/50">
              <div className="flex items-center gap-2">
                <input
                  ref={inputRef}
                  type="text"
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask about safety..."
                  className="flex-1 bg-secondary/50 border border-border/50 rounded-xl px-3 py-2 text-sm outline-none focus:border-amber-500/50 text-foreground placeholder:text-muted-foreground/50 transition-colors"
                  disabled={isLoading}
                />
                <button
                  onClick={handleSend}
                  disabled={!input.trim() || isLoading}
                  className="w-9 h-9 rounded-xl bg-amber-500/90 hover:bg-amber-500 disabled:opacity-30 disabled:cursor-not-allowed text-background flex items-center justify-center transition-colors"
                  aria-label="Send message"
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
};

export default SafetyChatWidget;
