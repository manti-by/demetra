import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { getCurrentUser, type User } from '../services/api';

interface AuthContextType {
  user: User | null;
  loading: boolean;
}

const AuthContext = createContext<AuthContextType>({ user: null, loading: true });

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    async function fetchUser() {
      try {
        const user = await getCurrentUser();
        if (mounted) {
          setUser(user);
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }
    fetchUser();
    return () => {
      mounted = false;
    };
  }, []);

  return <AuthContext.Provider value={{ user, loading }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
