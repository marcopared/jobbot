# Tests

The test suite still contains historical coverage for archived custom-resume generation behavior. During the MVP cleanup, prioritize focused smoke tests for the active flow:

```text
ingest/manual job -> score -> classify -> ATS analysis -> existing-resume recommendation
```

Recommended active smoke checks:

```bash
pytest tests/test_matching.py tests/test_ats_extraction.py tests/test_scoring.py tests/test_classification.py
pytest tests/test_api_jobs.py -k "manual or ready"
```

Full-suite failures may point at archived generation/artifact assumptions and should be triaged before being treated as active MVP regressions.
