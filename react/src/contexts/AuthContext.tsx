import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from 'react';
import { getCurrentUser, logout as apiLogout, type User } from '../services/api';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({ user: null, loading: true, logout: async () => {} });

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    if (typeof window === 'undefined') return null;
    const stored = localStorage.getItem('user');
    if (!stored) return null;
    try {
      return JSON.parse(stored);
    } catch {
      localStorage.removeItem('user');
      return null;
    }
  });
  const [loading, setLoading] = useState(user === null);

  useEffect(() => {
    let mounted = true;
    async function fetchUser() {
      const fetchedUser = await getCurrentUser();
      if (mounted) {
        // 'transient' means the server could not be reached or returned a
        // non-401 error; keep the optimistic user instead of flashing a logout.
        if (fetchedUser !== 'transient') {
          setUser(fetchedUser);
        }
        setLoading(false);
      }
    }
    fetchUser();
    return () => {
      mounted = false;
    };
  }, []);

  const logout = useCallback(async () => {
    await apiLogout();
    setUser(null);
  }, []);

  return <AuthContext.Provider value={{ user, loading, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
