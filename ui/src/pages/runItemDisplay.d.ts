import type { RunItem } from "../api";

export function buildRunItemDisplay(item: RunItem): {
  companyName: string;
  location: string;
  source: string;
  sourceJobId: string;
  jobId: string;
  listingHref: string | null;
  applyHref: string | null;
  rawPayloadText: string;
};
