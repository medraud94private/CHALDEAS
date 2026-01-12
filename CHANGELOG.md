# Changelog

All notable changes to CHALDEAS will be documented in this file.

## [0.5.1] - 2026-01-12

### Added
- UnifiedTimeline component for improved timeline UI
- DB sync script (`scripts/sync-db.ps1`) with automatic permission grant
- Deploy script (`scripts/deploy.ps1`) for Cloud Run deployment
- DB sync guide (`docs/guides/DB_SYNC.md`)

### Changed
- Refactored timeline components for better state management
- Improved timelineStore with cleaner architecture

## [0.5.0] - 2026-01-12

### Added
- Major UI/UX update with performance improvements
- Enhanced visualization components

### Changed
- Performance optimizations across the board

## [0.4.0] - 2026-01-11

### Added
- Statistics API (Phase 4 complete)
- V1 workplan with Phase 4-7 checkpoints

### Changed
- Completed Phase 4-6 review and quality check

## [0.3.0] - 2026-01-10

### Added
- Locations & Persons enrichment (Phase 3 complete)
- V1 schema and explore API
- V2 planning documentation

## [0.2.0] - 2026-01-08

### Added
- TXT file support in batch processor
- Recursive search in batch processor
- Archivist system for bulk downloads

### Fixed
- Batch API model and parameter corrections

## [0.1.0] - 2025-12-31

### Added
- Initial public release
- 3D globe interface with react-globe.gl
- Timeline navigation (BCE 3000 to present)
- Event, Person, Location data models
- Chat UI with RAG system (pgvector + OpenAI)
- Hybrid search (vector + keyword)
- Multi-language support (en/ko/ja)
- FGO-inspired UI design
- Cloud Run deployment configuration

### Core Features
- World-centric 7-layer architecture (CHALDEAS, SHEBA, LOGOS, etc.)
- Historical Chain concept for V1
- BCE date handling with negative integers
