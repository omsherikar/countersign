"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Camera, CameraOff } from "lucide-react";
import { t } from "@/lib/copy";
import { cn } from "@/lib/utils";
import { outlineButton, primaryButton } from "@/components/student/bits";
import { scanTarget } from "@/components/verify/code-form";

/** The parts of the Shape Detection API used here; TypeScript's DOM library does not declare it yet. */
interface DetectedBarcode {
  rawValue: string;
}
interface BarcodeDetectorLike {
  detect(source: HTMLVideoElement): Promise<DetectedBarcode[]>;
}
type BarcodeDetectorCtor = new (options?: { formats?: string[] }) => BarcodeDetectorLike;

function detectorClass(): BarcodeDetectorCtor | null {
  if (typeof window === "undefined") return null;
  return ((window as unknown as { BarcodeDetector?: BarcodeDetectorCtor }).BarcodeDetector ?? null) as BarcodeDetectorCtor | null;
}

const noSubscribe = () => () => {};
/** null on the server and while hydrating, then whether this browser can scan. */
export function useCanScan(): boolean | null {
  return React.useSyncExternalStore(
    noSubscribe,
    () => Boolean(detectorClass() && navigator.mediaDevices?.getUserMedia),
    () => null,
  );
}

/**
 * Camera scan with the browser's BarcodeDetector (W3-4). A scanned
 * Countersign link opens its own path; a refused camera says so and hands
 * focus to the code box.
 */
export function Scanner({ onDenied }: { onDenied: () => void }) {
  const router = useRouter();
  const canScan = useCanScan();
  const [on, setOn] = React.useState(false);
  const [denied, setDenied] = React.useState(false);
  const video = React.useRef<HTMLVideoElement>(null);
  const stream = React.useRef<MediaStream | null>(null);
  const stopButton = React.useRef<HTMLButtonElement>(null);
  const startButton = React.useRef<HTMLButtonElement>(null);

  const stop = React.useCallback(() => {
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
    setOn(false);
  }, []);

  React.useEffect(() => stop, [stop]);

  React.useEffect(() => {
    if (!on) return;
    const Detector = detectorClass();
    if (!Detector || !video.current) return;
    const detector = new Detector({ formats: ["qr_code"] });
    let alive = true;
    const tick = async () => {
      if (!alive || !video.current) return;
      try {
        const codes = video.current.readyState >= 2 ? await detector.detect(video.current) : [];
        const path = codes.map((c) => scanTarget(c.rawValue)).find(Boolean);
        if (path) {
          stop();
          router.push(path);
          return;
        }
      } catch {
        // A frame the detector could not read; try the next one.
      }
      if (alive) setTimeout(tick, 250);
    };
    tick();
    return () => {
      alive = false;
    };
  }, [on, router, stop]);

  const start = async () => {
    setDenied(false);
    try {
      const media = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
      stream.current = media;
      setOn(true);
      requestAnimationFrame(() => {
        if (video.current) {
          video.current.srcObject = media;
          video.current.play().catch(() => undefined);
        }
        stopButton.current?.focus();
      });
    } catch {
      setDenied(true);
      onDenied();
    }
  };

  if (canScan === null) return <div className="h-12" aria-hidden="true" />;
  if (!canScan) return <p className="text-ink-muted">{t("verify.scan_unsupported")}</p>;

  return (
    <div>
      {on ? (
        <div>
          <video ref={video} muted playsInline aria-hidden="true" className="aspect-square w-full rounded-md bg-ink object-cover" />
          <p className="mt-2 text-ink-muted">{t("verify.scan_hint")}</p>
          <button
            ref={stopButton}
            type="button"
            className={cn(outlineButton, "mt-2")}
            onClick={() => {
              stop();
              requestAnimationFrame(() => startButton.current?.focus());
            }}
          >
            <CameraOff className="size-5" aria-hidden="true" />
            {t("verify.scan_stop")}
          </button>
        </div>
      ) : (
        <button ref={startButton} type="button" className={primaryButton} onClick={start}>
          <Camera className="size-5" aria-hidden="true" />
          {t("verify.scan")}
        </button>
      )}
      {denied && (
        <p role="alert" className="mt-2 text-check-fail-ink">
          {t("verify.camera_denied")}
        </p>
      )}
    </div>
  );
}
