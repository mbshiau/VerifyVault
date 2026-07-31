"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import type { TranscriptSegment } from "@/lib/api";

export type VideoPlayerHandle = {
  seekTo: (ms: number) => void;
  play: () => Promise<void>;
  pause: () => void;
};

export const VideoPlayer = forwardRef<VideoPlayerHandle, { src: string; captions?: TranscriptSegment[]; onTimeUpdate?: (ms: number) => void }>(
  function VideoPlayer({ src, captions, onTimeUpdate }, ref) {
    const videoRef = useRef<HTMLVideoElement>(null);
    const [vttUrl, setVttUrl] = useState<string | null>(null);

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
      async play() {
        const video = videoRef.current;
        if (!video) return;
        try {
          await video.play();
        } catch (e) {
          // ignore play errors
        }
      },
      pause() {
        const video = videoRef.current;
        if (!video) return;
        try {
          video.pause();
        } catch (e) {
          // ignore
        }
      },
    }));

    useEffect(() => {
      const video = videoRef.current;
      if (!video || !onTimeUpdate) return;
      const handler = () => onTimeUpdate(Math.round(video.currentTime * 1000));
      video.addEventListener("timeupdate", handler);
      return () => video.removeEventListener("timeupdate", handler);
    }, [onTimeUpdate]);

    useEffect(() => {
      if (!captions || captions.length === 0) {
        setVttUrl(null);
        return;
      }
      // Build WebVTT content
      function msToVtt(ts: number) {
        const totalMs = Math.max(0, Math.floor(ts));
        const hours = Math.floor(totalMs / 3600000);
        const minutes = Math.floor((totalMs % 3600000) / 60000);
        const seconds = Math.floor((totalMs % 60000) / 1000);
        const msPart = totalMs % 1000;
        return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}.${String(msPart).padStart(3, "0")}`;
      }
      let vtt = "WEBVTT\n\n";
      captions.forEach((s, i) => {
        const start = msToVtt(s.start_ms ?? 0);
        const end = msToVtt(s.end_ms ?? (s.start_ms ?? 0) + 1000);
        const text = (s.text || "").replace(/\n/g, " ").replace(/-->/g, "->");
        vtt += `${i}\n${start} --> ${end}\n${text}\n\n`;
      });
      const blob = new Blob([vtt], { type: "text/vtt" });
      const url = URL.createObjectURL(blob);
      setVttUrl(url);
      return () => {
        if (url) URL.revokeObjectURL(url);
        setVttUrl(null);
      };
    }, [captions]);

    return (
      <div className="mx-auto max-w-2xl">
        <video
          ref={videoRef}
          src={src}
          controls
          preload="metadata"
          className="max-h-[70vh] w-full rounded-xl bg-black"
        >
          {vttUrl && <track kind="captions" src={vttUrl} srcLang="en" default />}
        </video>
      </div>
    );
  }
);
