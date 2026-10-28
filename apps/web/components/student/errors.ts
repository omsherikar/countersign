import { ApiError } from "@/lib/api";
import { t } from "@/lib/copy";
import { errorMessage } from "@/components/common/query-state";

/**
 * The copy deck's err.* sentence for an api error on the student, verifier
 * and degree pages (deck section 13). Codes without a deck line fall back to
 * the shared wording, then to the envelope message.
 */
export function deckError(err: unknown, secondsLeft?: number | null): string {
  if (!(err instanceof ApiError)) return t("err.INTERNAL");
  switch (err.code) {
    case "RATE_LIMITED":
      return t("err.RATE_LIMITED", { seconds: secondsLeft ?? err.retryAfter ?? 30 });
    case "NOTICE_NOT_FOUND":
    case "NOTICE_EXPIRED":
    case "NOTICE_ALREADY_CHANGED":
    case "CREDENTIAL_NOT_ELIGIBLE":
    case "CREDENTIAL_REVOKED":
    case "PRESENTATION_NOT_FOUND":
      return t(`err.${err.code}`);
    default:
      return errorMessage(err);
  }
}

/** "Ref: CODE" under a failure, as on every other page. */
export function errorCodeOf(err: unknown): string {
  return err instanceof ApiError ? err.code : "INTERNAL";
}
