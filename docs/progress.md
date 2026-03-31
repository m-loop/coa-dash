# COA-dash Progress

## Current State

**Version**: 0.5.0
**Status**: E2E Testing Complete
**Last Updated**: 2026-03-31

## v0.5.1 - Swipe-to-Delete (2026-04-01)

### Features Implemented
- [x] Swipe-to-delete on mobile (left swipe reveals delete button)
- [x] Confirmation dialog before deletion
- [x] DELETE /api/tasks/:id endpoint
- [x] Auto-refresh after successful deletion
- [x] Smooth swipe animation with threshold detection

### Technical Changes
- **Frontend**: Touch event handlers (touchstart/touchmove/touchend), CSS animations, confirmation dialog
- **Backend**: delete_task() function, do_DELETE handler
- **UX**: 70px swipe threshold, prevent accidental clicks, visual feedback

### Testing
- [x] API DELETE endpoint tested
- [x] Task deletion verified
- [ ] Frontend swipe animation (manual testing required)


## v0.5.0 - OpenCode Tab & Session State

### Features Implemented
- [x] Session State button in top bar
- [x] Session State popup with task details
- [x] OpenCode tab with sidebar and chat
- [x] Multi-project support (config/opencode-projects.json)
- [x] OpenCode API proxy with security whitelist
- [x] Sessions list from opencode serve

### Bug Fixes
- [x] Gzip compression issue: Added `Accept-Encoding: identity` to proxy requests

### Known Issues
- [ ] Message loading slow (52KB+ response from opencode)
- [ ] SVG icon error in refresh button

### E2E Test Results (2026-03-31)
| Feature | Status |
|---------|--------|
| Session State button | ✅ Pass |
| Session State popup | ✅ Pass |
| OpenCode tab load | ✅ Pass |
| Projects list | ✅ Pass |
| Sessions list (39 items) | ✅ Pass |
| Session selection | ⚠️ Slow API |

## History

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-31 | 0.5.0 | OpenCode tab, Session State button, API proxy |
| 2026-03-30 | 0.4.0 | Mobile-first redesign, bottom nav |
| 2026-03-29 | 0.3.0 | Task management, notifications |
| 2026-03-28 | 0.2.0 | Agent status, live sessions |
| 2026-03-27 | 0.1.0 | Initial release |

## Services Running

| Service | Port | Status |
|---------|------|--------|
| coa-dash | 8890 | ✅ Active |
| opencode-serve@4096 | 4096 | ✅ Active |
| ttyd | 7681 | ✅ Active (backup) |

## Test URLs

- Local: http://localhost:8890
- Tailscale: http://100.103.186.109:8890