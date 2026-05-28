/**
 * useTypewriter hook — Claude-style animated text reveal.
 * IP-24 Phase 3.5.
 *
 * Features:
 * - Adaptive speed based on text length
 * - requestAnimationFrame loop for smooth animation
 * - Respects prefers-reduced-motion
 * - Auto-skip on document hidden
 * - Manual skip() function
 */

import { useEffect, useRef, useState } from "react";

export interface UseTypewriterOptions {
  text: string;
  enabled: boolean;
  charsPerSecond?: number;
}

export interface UseTypewriterResult {
  displayed: string;
  isTyping: boolean;
  skip: () => void;
}

function getAdaptiveSpeed(textLength: number): number {
  if (textLength < 500) return 60;
  if (textLength < 1500) return 150;
  return 250;
}

export function useTypewriter(
  options: UseTypewriterOptions
): UseTypewriterResult {
  const { text, enabled, charsPerSecond } = options;

  const speed = charsPerSecond ?? getAdaptiveSpeed(text.length);

  const [displayed, setDisplayed] = useState("");
  const [isTyping, setIsTyping] = useState(false);

  const requestIdRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(0);
  const indexRef = useRef<number>(0);
  const skippedRef = useRef<boolean>(false);
  const textRef = useRef(text); // WHY: skip() needs current text, not stale closure
  textRef.current = text;

  const skip = (): void => {
    skippedRef.current = true;
    if (requestIdRef.current !== null) {
      cancelAnimationFrame(requestIdRef.current);
      requestIdRef.current = null;
    }
    setDisplayed(textRef.current); // WHY: use ref to avoid stale closure
    setIsTyping(false);
  };

  useEffect(() => {
    // Check for reduced motion
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const prefersReducedMotion = mediaQuery.matches;

    if (!enabled || prefersReducedMotion) {
      setDisplayed(text);
      setIsTyping(false);
      return;
    }

    // Reset state
    skippedRef.current = false;
    indexRef.current = 0;
    startTimeRef.current = 0;
    setDisplayed("");
    setIsTyping(true);

    // Animation loop
    function animate(timestamp: number): void {
      if (startTimeRef.current === 0) {
        startTimeRef.current = timestamp;
      }

      const elapsed = timestamp - startTimeRef.current;
      const msPerChar = 1000 / speed;
      const targetIndex = Math.floor(elapsed / msPerChar);

      if (targetIndex >= text.length) {
        // Done
        setDisplayed(text);
        setIsTyping(false);
        return;
      }

      if (targetIndex > indexRef.current) {
        indexRef.current = targetIndex;
        setDisplayed(text.slice(0, targetIndex + 1));
      }

      requestIdRef.current = requestAnimationFrame(animate);
    }

    requestIdRef.current = requestAnimationFrame(animate);

    // Auto-skip on document hidden
    function handleVisibilityChange(): void {
      if (document.hidden) {
        skip();
      }
    }
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      if (requestIdRef.current !== null) {
        cancelAnimationFrame(requestIdRef.current);
      }
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [text, enabled, speed]); // WHY: skip removed from deps - uses refs, stable across renders

  return { displayed, isTyping, skip };
}
