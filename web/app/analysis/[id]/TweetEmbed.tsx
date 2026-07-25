"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import type { VideoPlayerHandle } from "./VideoPlayer";

declare global {
  interface Window {
    twttr?: {
      widgets: {
        createTweet: (tweetId: string, container: HTMLElement) => Promise<HTMLElement | undefined>;
      };
    };
  }
}

let widgetsLoadPromise: Promise<void> | null = null;

function loadTwitterWidgets(): Promise<void> {
  if (typeof window === "undefined") return Promise.resolve();
  if (window.twttr?.widgets) return Promise.resolve();
  if (widgetsLoadPromise) return widgetsLoadPromise;

  widgetsLoadPromise = new Promise((resolve) => {
    const script = document.createElement("script");
    script.src = "https://platform.twitter.com/widgets.js";
    script.async = true;
    script.onload = () => resolve();
    document.head.appendChild(script);
  });
  return widgetsLoadPromise;
}

// X/Twitter's embedded tweet widget has no public API to seek video to a
// timestamp (unlike YouTube's IFrame Player) - so this still exposes the
// same VideoPlayerHandle shape the rest of the analysis page calls
// unconditionally, but seekTo is a deliberate no-op here. Clicking a claim
// still highlights/scrolls the transcript; it just can't jump the embedded
// player itself.
export const TweetEmbed = forwardRef<VideoPlayerHandle, { tweetId: string }>(function TweetEmbed(
  { tweetId },
  ref
) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    const container = containerRef.current;
    if (!container) return;
    container.innerHTML = "";
    loadTwitterWidgets().then(() => {
      if (cancelled || !window.twttr || !container) return;
      window.twttr.widgets.createTweet(tweetId, container);
    });
    return () => {
      cancelled = true;
    };
  }, [tweetId]);

  useImperativeHandle(ref, () => ({
    seekTo() {
      // No-op: see the component-level comment above.
    },
  }));

  return (
    <div className="mx-auto flex max-w-2xl justify-center">
      <div ref={containerRef} />
    </div>
  );
});
