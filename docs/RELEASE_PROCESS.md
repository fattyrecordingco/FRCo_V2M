# Release Process

## Versioning
Use semantic versioning:
- MAJOR: breaking changes
- MINOR: new backward-compatible features
- PATCH: fixes and small improvements

## Local Pre-Release Checklist
- Update roadmap/status docs if needed.
- Run test suite and confirm pass.
- Perform manual MIDI export/import checks.
- Update changelog section in release notes.

## GitHub Release Steps
1. Ensure local branch is clean.
2. Create tag, e.g. `v0.1.0`.
3. Push commits and tags to GitHub.
4. Create GitHub Release using tag.
5. Include:
   - What shipped
   - Known issues
   - Upgrade notes

## Post-Release
- Open a milestone for next version.
- Create tasks from known issues and feedback.
