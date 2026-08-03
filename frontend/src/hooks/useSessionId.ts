import { useState } from "react";

let cached: string | null = null;

function gen(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function useSessionId(): string {
  const [sessionId] = useState<string>(() => {
    if (cached) return cached;
    cached = gen();
    return cached;
  });

  return sessionId;
}

export function refreshSessionId(): string {
  cached = gen();
  return cached;
}