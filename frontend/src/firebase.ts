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

export const firebaseConfig: FirebaseFrontendConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

export const isFirebaseConfigured = Boolean(
  firebaseConfig.apiKey && firebaseConfig.projectId
);

let app: FirebaseApp | null = null;
let auth: Auth | null = null;

if (isFirebaseConfigured) {
  if (!getApps().length) {
    app = initializeApp(firebaseConfig as Record<string, string>);
  } else {
    app = getApps()[0];
  }
  auth = getAuth(app);
}

/**
 * Ensures an authenticated user exists (via Firebase Anonymous Auth)
 * and retrieves their fresh ID token.
 */
export async function getAuthToken(): Promise<string | null> {
  if (!auth) {
    return null;
  }

  return new Promise((resolve) => {
    onAuthStateChanged(auth!, async (user: User | null) => {
      if (user) {
        try {
          const token = await user.getIdToken();
          resolve(token);
        } catch {
          resolve(null);
        }
      } else {
        try {
          const userCredential = await signInAnonymously(auth!);
          const token = await userCredential.user.getIdToken();
          resolve(token);
        } catch {
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
