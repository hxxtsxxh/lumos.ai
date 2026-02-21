import { motion, AnimatePresence } from 'framer-motion';
import { LogIn, LogOut, User, Bookmark } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { useState, useRef, useEffect } from 'react';

interface UserMenuProps {
  onOpenSaved?: () => void;
}

const UserMenu = ({ onOpenSaved }: UserMenuProps) => {
  const { user, signInWithGoogle, signOut } = useAuth();
  const [showMenu, setShowMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu on outside click
  useEffect(() => {
    if (!showMenu) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showMenu]);

  if (!user) {
    return (
      <motion.button
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        onClick={signInWithGoogle}
        className="header-btn flex items-center gap-1.5 sm:gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors glass-panel px-3 sm:px-4 py-2 rounded-xl"
      >
        <LogIn className="w-4 h-4" />
        <span className="hidden sm:inline">Sign In</span>
      </motion.button>
    );
  }

  return (
    <div className="relative" ref={menuRef}>
      <motion.button
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        onClick={() => setShowMenu(!showMenu)}
        className="header-btn flex items-center gap-1.5 sm:gap-2 glass-panel px-2.5 sm:px-3 py-2 rounded-xl hover:bg-secondary/50 transition-colors"
      >
        {user.photoURL ? (
          <img
            src={user.photoURL}
            alt=""
            className="w-6 h-6 rounded-full"
            referrerPolicy="no-referrer"
          />
        ) : (
          <User className="w-5 h-5 text-muted-foreground" />
        )}
        <span className="text-sm text-foreground max-w-[100px] truncate hidden sm:inline">
          {user.displayName?.split(' ')[0] || 'User'}
        </span>
      </motion.button>

      <AnimatePresence>
        {showMenu && (
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.95 }}
            className="absolute right-0 top-12 glass-panel rounded-xl p-2 min-w-[180px] z-50"
          >
            <button
              onClick={() => {
                onOpenSaved?.();
                setShowMenu(false);
              }}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-foreground hover:bg-secondary/50 transition-colors"
            >
              <Bookmark className="w-4 h-4" />
              Saved Reports
            </button>
            <div className="border-t border-border my-1" />
            <button
              onClick={() => {
                signOut();
                setShowMenu(false);
              }}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-muted-foreground hover:text-foreground hover:bg-secondary/50 transition-colors"
            >
              <LogOut className="w-4 h-4" />
              Sign Out
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default UserMenu;
