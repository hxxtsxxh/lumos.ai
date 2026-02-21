import { motion } from 'framer-motion';

const LumosLogo = ({ size = 40 }: { size?: number }) => {
  return (
    <motion.div
      className="flex items-center gap-2"
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: 'easeOut' }}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 48 48"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Shield shape */}
        <path
          d="M24 4L6 12V24C6 35.1 14.04 45.26 24 48C33.96 45.26 42 35.1 42 24V12L24 4Z"
          fill="hsl(var(--card))"
          stroke="hsl(38 92% 55%)"
          strokeWidth="1.5"
        />
        {/* Light burst / wand tip */}
        <circle cx="24" cy="22" r="6" fill="hsl(38 92% 55%)" opacity="0.9" />
        <circle cx="24" cy="22" r="3" fill="hsl(38 100% 75%)" />
        {/* Rays */}
        <line x1="24" y1="12" x2="24" y2="15" stroke="hsl(38 92% 55%)" strokeWidth="1.5" strokeLinecap="round" />
        <line x1="24" y1="29" x2="24" y2="32" stroke="hsl(38 92% 55%)" strokeWidth="1.5" strokeLinecap="round" />
        <line x1="15" y1="22" x2="18" y2="22" stroke="hsl(38 92% 55%)" strokeWidth="1.5" strokeLinecap="round" />
        <line x1="30" y1="22" x2="33" y2="22" stroke="hsl(38 92% 55%)" strokeWidth="1.5" strokeLinecap="round" />
        {/* Diagonal rays */}
        <line x1="17.5" y1="15.5" x2="19.6" y2="17.6" stroke="hsl(38 92% 55%)" strokeWidth="1" strokeLinecap="round" opacity="0.7" />
        <line x1="28.4" y1="26.4" x2="30.5" y2="28.5" stroke="hsl(38 92% 55%)" strokeWidth="1" strokeLinecap="round" opacity="0.7" />
        <line x1="30.5" y1="15.5" x2="28.4" y2="17.6" stroke="hsl(38 92% 55%)" strokeWidth="1" strokeLinecap="round" opacity="0.7" />
        <line x1="19.6" y1="26.4" x2="17.5" y2="28.5" stroke="hsl(38 92% 55%)" strokeWidth="1" strokeLinecap="round" opacity="0.7" />
        {/* Teal accent dot */}
        <circle cx="24" cy="38" r="2" fill="hsl(174 62% 47%)" />
      </svg>
      <span className="font-display text-xl sm:text-2xl font-bold tracking-tight text-foreground">
        Lumos
      </span>
    </motion.div>
  );
};

export default LumosLogo;
