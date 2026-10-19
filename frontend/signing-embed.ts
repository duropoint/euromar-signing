/**
 * Framework-agnostic helper for apps that show Documenso's signing page in
 * an iframe. Copy this file into your frontend (no dependencies).
 *
 * The backend creates the session (euromar_signing.SigningService.start) and
 * hands the browser `embed_url`. Put it in an <iframe>, then:
 *
 *   const stop = listenForSigningEvents(iframe, embedUrl, {
 *     onCompleted: () => backend.reconcile(),   // then close the modal
 *     onRejected: (reason) => ...,
 *     onError: () => ...,
 *   });
 *   // call stop() when the modal closes
 *
 * Only messages from the Documenso origin AND from this iframe are accepted
 * (Documenso posts with targetOrigin "*"). A completed event is only a UI
 * hint: the backend must confirm with the Documenso API before trusting it.
 */

export type SigningEventHandlers = {
  onReady?: () => void;
  onCompleted?: (data: { envelopeId?: string; recipientId?: number }) => void;
  onRejected?: (reason?: string) => void;
  onError?: () => void;
};

type DocumensoMessage = { action?: string; data?: Record<string, unknown> | null };

export function signingOrigin(embedUrl: string): string {
  return new URL(embedUrl).origin;
}

export function listenForSigningEvents(
  iframe: HTMLIFrameElement,
  embedUrl: string,
  handlers: SigningEventHandlers,
): () => void {
  const origin = signingOrigin(embedUrl);

  const onMessage = (event: MessageEvent) => {
    if (event.origin !== origin || event.source !== iframe.contentWindow) return;
    const msg = event.data as DocumensoMessage;
    if (!msg || typeof msg.action !== "string") return;

    switch (msg.action) {
      case "document-ready":
        handlers.onReady?.();
        break;
      case "document-completed":
        handlers.onCompleted?.({
          envelopeId: msg.data?.envelopeId as string | undefined,
          recipientId: msg.data?.recipientId as number | undefined,
        });
        break;
      case "document-rejected":
        handlers.onRejected?.(msg.data?.reason as string | undefined);
        break;
      case "document-error":
      case "recipient-expired":
      case "sender-disabled":
        handlers.onError?.();
        break;
    }
  };

  window.addEventListener("message", onMessage);
  return () => window.removeEventListener("message", onMessage);
}
