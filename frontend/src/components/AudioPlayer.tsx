import { forwardRef } from "react";

/**
 * Audio player for a meeting recording. The parent owns the ref so transcript
 * clicks can seek, and listens to onTimeUpdate to highlight the current
 * segment while playing.
 */
export const AudioPlayer = forwardRef<
  HTMLAudioElement,
  { src: string; onTimeUpdate?: (seconds: number) => void }
>(function AudioPlayer({ src, onTimeUpdate }, ref) {
  return (
    <audio
      ref={ref}
      className="audio-player"
      src={src}
      controls
      preload="metadata"
      onTimeUpdate={(e) => onTimeUpdate?.((e.target as HTMLAudioElement).currentTime)}
    />
  );
});
