# JobBot System Specification

> **Note:** The system specification and architecture documentation have been consolidated into a single authoritative source of truth. The docs describe the **v1 implementation**: deterministic scoring, rules-based classification, grounded inventory-driven resume generation, Playwright PDF rendering, Redis + Celery, React + Vite. No LLM dependency. Manual review and manual apply only.
> 
> Please refer to [docs/ARCHITECTURE.md](./ARCHITECTURE.md) for the complete engineering design document, which covers:
> - End-to-End System Flow
> - Core Domain and Data Models
> - Ingestion, Deduplication, and Scoring
> - Persona Classification and Resume Generation
> - API, Worker, and UI Architecture

