# Changelog

All notable changes to this project are documented here. This project
follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Initial release groundwork: config system, Python/TypeScript parsing
  (`LanguageAdapter`), the state tree and status engine, the `autodoc` CLI
  (`init`, `scan`, `status`, `diff`, `approve`, `check`, `install-hook`),
  git hook integration, and the `autodocstrings` agent skill.
- Agent JSON contract (`docs/agent-contract.md`), versioned via
  `schema_version` (currently `1`).
