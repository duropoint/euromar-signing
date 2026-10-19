/**
 * Reference React component (copy and restyle with your app's design system).
 * Renders the Documenso signing page and reports completion.
 */
"use client";

import { useEffect, useRef } from "react";

import { listenForSigningEvents } from "./signing-embed";

export function SigningEmbed({
  embedUrl,
  onCompleted,
  onRejected,
  onError,
  height = 760,
}: {
  embedUrl: string;
  onCompleted: () => void;
  onRejected?: (reason?: string) => void;
  onError?: () => void;
  height?: number;
}) {
  const ref = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    return listenForSigningEvents(ref.current, embedUrl, {
      onCompleted: () => onCompleted(),
      onRejected,
      onError,
    });
  }, [embedUrl, onCompleted, onRejected, onError]);

  return (
    <iframe
      ref={ref}
      src={embedUrl}
      title="Sign documents"
      style={{ width: "100%", height, border: 0 }}
      allow="clipboard-write"
    />
  );
}
