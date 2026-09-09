/**
 * Firebase Client SDK Initialization & Anonymous Authentication.
 *
 * Reads only public VITE_FIREBASE_* environment variables.
 * Never handles or exposes private service account credentials.
 */

import { initializeApp, getApps, FirebaseApp } from 'firebase/app';
import { getAuth, signInAnonymously, onAuthStateChanged, User, Auth } from 'firebase/auth';

export interface FirebaseFrontendConfig {
  apiKey?: string;
  authDomain?: string;
  projectId?: string;
  appId?: string;
}

export let firebaseConfig: FirebaseFrontendConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

let app: FirebaseApp | null = null;
let auth: Auth | null = null;
let initPromise: Promise<Auth | null> | null = null;

/**
 * Initializes Firebase using build-time env vars or runtime /api/auth/config fallback.
 */
export async function initFirebase(): Promise<Auth | null> {
  if (auth) return auth;
  if (initPromise) return initPromise;

  initPromise = (async () => {
    let activeConfig = { ...firebaseConfig };

    // If apiKey or projectId are not present in Vite build, fetch from runtime backend
    if (!activeConfig.apiKey || !activeConfig.projectId) {
      try {
        const res = await fetch('/api/auth/config');
        if (res.ok) {
          const remoteConfig = await res.json();
          activeConfig = { ...activeConfig, ...remoteConfig };
          firebaseConfig = activeConfig;
        }
      } catch (err) {
        console.warn('Could not retrieve remote Firebase config:', err);
      }
    }

    if (activeConfig.apiKey && activeConfig.projectId) {
      try {
        if (!getApps().length) {
          app = initializeApp(activeConfig as Record<string, string>);
        } else {
          app = getApps()[0];
        }
        auth = getAuth(app);
        return auth;
      } catch (err) {
        console.error('Failed to initialize Firebase app:', err);
      }
    }
    return null;
  })();

  return initPromise;
}

// Attempt eager initialization
initFirebase().catch(() => {});

/**
 * Ensures an authenticated user exists (via Firebase Anonymous Auth)
 * and retrieves their fresh ID token.
 */
export async function getAuthToken(): Promise<string | null> {
  const activeAuth = await initFirebase();
  if (!activeAuth) {
    return null;
  }

  return new Promise((resolve) => {
    onAuthStateChanged(activeAuth, async (user: User | null) => {
      if (user) {
        try {
          const token = await user.getIdToken();
          resolve(token);
        } catch {
          resolve(null);
        }
      } else {
        try {
          const userCredential = await signInAnonymously(activeAuth);
          const token = await userCredential.user.getIdToken();
          resolve(token);
        } catch (err: any) {
          console.warn('Firebase anonymous sign-in unavailable:', err?.message || err);
          resolve(null);
        }
      }
    });
  });
}

/**
 * Returns missing Vite frontend variable names if not fully configured.
 */
export function getMissingFrontendVariables(): string[] {
  const missing: string[] = [];
  if (!firebaseConfig.apiKey) missing.push('VITE_FIREBASE_API_KEY');
  if (!firebaseConfig.authDomain) missing.push('VITE_FIREBASE_AUTH_DOMAIN');
  if (!firebaseConfig.projectId) missing.push('VITE_FIREBASE_PROJECT_ID');
  if (!firebaseConfig.appId) missing.push('VITE_FIREBASE_APP_ID');
  return missing;
}
