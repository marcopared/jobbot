export const JOBBOT_ERROR_EVENT = "jobbot:error";

export function notifyError(message: string): void {
  window.dispatchEvent(new CustomEvent(JOBBOT_ERROR_EVENT, { detail: message }));
}
