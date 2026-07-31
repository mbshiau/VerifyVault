"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import type { VideoPlayerHandle } from "./VideoPlayer";

declare global {
  interface Window {
    YT?: {
      Player: new (
        elementId: string,
        options: { videoId: string; events?: { onReady?: () => void } }
      ) => YouTubePlayerInstance;
    };
    onYouTubeIframeAPIReady?: () => void;
  }
}

type YouTubePlayerInstance = {
  seekTo: (seconds: number, allowSeekAhead: boolean) => void;
  playVideo: () => void;
  pauseVideo: () => void;
  getCurrentTime: () => number;
  destroy: () => void;
};

let apiLoadPromise: Promise<void> | null = null;

function loadYouTubeApi(): Promise<void> {
  if (typeof window === "undefined") return Promise.resolve();
  if (window.YT?.Player) return Promise.resolve();
  if (apiLoadPromise) return apiLoadPromise;

  apiLoadPromise = new Promise((resolve) => {
    const previous = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      previous?.();
      resolve();
    };
    const script = document.createElement("script");
    script.src = "https://www.youtube.com/iframe_api";
    document.head.appendChild(script);
  });
  return apiLoadPromise;
}

export const YouTubePlayer = forwardRef<VideoPlayerHandle, { videoId: string; onTimeUpdate?: (ms: number) => void }>(function YouTubePlayer(
  { videoId, onTimeUpdate },
  ref
) {
  const containerId = useRef(`yt-player-${Math.random().toString(36).slice(2)}`).current;
  const playerRef = useRef<YouTubePlayerInstance | null>(null);
  const [ready, setReady] = useState(false);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    setReady(false);
    loadYouTubeApi().then(() => {
      if (cancelled || !window.YT) return;
      playerRef.current = new window.YT.Player(containerId, {
        videoId,
        events: { onReady: () => setReady(true) },
      });
    });
    return () => {
      cancelled = true;
      if (pollRef.current) window.clearInterval(pollRef.current);
      playerRef.current?.destroy();
      playerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoId]);

  // Poll current time when ready
  useEffect(() => {
    if (!ready || !onTimeUpdate) return;
    if (!playerRef.current) return;
    pollRef.current = window.setInterval(() => {
      try {
        const t = playerRef.current?.getCurrentTime() ?? 0;
        onTimeUpdate(Math.round(t * 1000));
      } catch (e) {
        // ignore
      }
    }, 250);
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
      pollRef.current = null;
    };
  }, [ready, onTimeUpdate]);

  useImperativeHandle(ref, () => ({
    seekTo(ms: number) {
      if (!ready || !playerRef.current) return;
      playerRef.current.seekTo(ms / 1000, true);
      playerRef.current.playVideo();
    },
    async play() {
      if (!ready || !playerRef.current) return;
      try {
        playerRef.current.playVideo();
      } catch (e) {
        // ignore
      }
    },
    pause() {
      if (!ready || !playerRef.current) return;
      try {
        playerRef.current.pauseVideo();
      } catch (e) {
        // ignore
      }
    },
  }));

  return (
    <div className="mx-auto max-w-2xl overflow-hidden rounded-xl bg-black" style={{ aspectRatio: "16 / 9" }}>
      <div id={containerId} className="h-full w-full" />
    </div>
  );
});
