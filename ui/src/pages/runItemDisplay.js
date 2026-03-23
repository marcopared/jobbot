export function buildRunItemDisplay(item) {
  const listingHref = item.url || item.apply_url || null;
  const applyHref = item.apply_url || null;

  return {
    companyName: item.company_name || "Unknown company",
    location: item.location || "N/A",
    source: item.source || "N/A",
    sourceJobId: item.source_job_id || "N/A",
    jobId: item.job_id || "N/A",
    listingHref,
    applyHref,
    rawPayloadText: JSON.stringify(item.raw_payload_json, null, 2),
  };
}
