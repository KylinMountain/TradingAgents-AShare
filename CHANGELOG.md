# Changelog

All notable changes to this project will be documented in this file.

## [v0.4.4] - 2026-03-18

### Fixed
- Fixed critical **SQLAlchemy TimeoutError** by unifying database session lifecycle across API endpoints and background tasks.
- Fixed **Resource/Semaphore Leakage** on shutdown by adding executor shutdown to the FastAPI lifespan.
- Improved repository structure by moving `announcements.json` to the `api/` directory and updating search paths.
- Cleaned up redundant `uv.lock.cp313` and `CLAUDE.md` files.

## [v0.4.3] - 2026-03-16

### Added
- Added **Task Lifecycle Persistence and Recovery** (#32): Analysis jobs can now survive server restarts.
- Added **Configurable Max Workers** (#33): Job executor concurrency is now tunable via `TA_MAX_WORKERS` env var.

### Changed
- Improved error messaging for failed analysis steps in the UI.

## [v0.4.2] - 2026-03-16

### Added
- Added user-context grounding so analysis can incorporate objective, risk preference, investment horizon, and holding constraints.
- Added local Docker one-click deployment script for easier self-hosted setup.

### Changed
- Upgraded the debate workflow to a claim-driven flow for stronger argument organization and downstream judgment.
- Improved multi-horizon analysis wording and parameter handling.

### Fixed
- Fixed structured extraction prompts by explicitly restoring missing JSON keywords that caused 400 errors.
- Removed mistakenly committed runtime artifacts such as `deploy` and `.vite` from version control.

## [v0.4.1] - 2026-03-15
... (rest of history)
