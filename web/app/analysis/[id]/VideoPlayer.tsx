"use client";

import { forwardRef, useImperativeHandle, useRef } from "react";

export type VideoPlayerHandle = {
  seekTo: (ms: number) => void;
};

export const VideoPlayer = forwardRef<VideoPlayerHandle, { src: string }>(function VideoPlayer({ src }, ref) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useImperativeHandle(ref, () => ({
    seekTo(ms: number) {
      const video = videoRef.current;
      if (!video) return;
      video.currentTime = ms / 1000;
      video.play().catch(() => {
        // Autoplay can be blocked without a prior user gesture - seeking
        // still succeeds, it just stays paused until the user hits play.
      });
    },
  }));

  return (
    <div className="mx-auto max-w-2xl">
      <video
        ref={videoRef}
        src={src}
        controls
        preload="metadata"
        className="max-h-[70vh] w-full rounded-xl bg-black"
      />
    </div>
  );
});
