"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "~/lib/api";
import type { AssessmentUser } from "~/types/assessment";

const STORAGE_KEY = "scope-assessment-user-id";

const safeGetStoredUserId = () => {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(STORAGE_KEY);
};

/**
 * Stand-in for real authentication: the user is picked from a list and the
 * choice is remembered in localStorage. The backend enforces permissions.
 */
export function useMockSession() {
  const [users, setUsers] = useState<AssessmentUser[]>([]);
  const [userId, setUserId] = useState<string | null>(null);

  useEffect(() => {
    api
      .listUsers()
      .then(setUsers)
      .catch(() => setUsers([]));
    const stored = safeGetStoredUserId();
    if (stored) setUserId(stored);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (userId) {
      window.localStorage.setItem(STORAGE_KEY, userId);
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }, [userId]);

  const user: AssessmentUser | null = useMemo(() => {
    if (!userId) return null;
    return users.find((candidate) => candidate.id === userId) ?? null;
  }, [users, userId]);

  return {
    users,
    user,
    userId,
    setUserId,
    signOut: () => setUserId(null),
  };
}
