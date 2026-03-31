# COA-dash Mobile UI Specification

Detailed CSS and layout specifications for mobile-first, touch-first, foldable-responsive design.

**Version**: 0.3.0  
**Design System**: ui-ux-pro-max (Dark Mode OLED)  
**Interaction Model**: Touch-first, no keyboard shortcuts

---

## Target Devices

| Device | Screen Size | Use Case |
|--------|-------------|----------|
| Huawei Mate X6 Folded | 410px × 890px | Primary (quick glance) |
| Huawei Mate X6 Unfolded | 890px × 1780px | Secondary (detail work) |
| iPhone 15 Pro | 393px × 852px | Reference |
| Desktop | >1024px | Full layout |

---

## Touch Interaction Model

### Supported Gestures

| Gesture | Action | Context |
|---------|--------|---------|
| **Tap** | Primary action | Expand card, select tab, press button |
| **Long Press** (500ms) | Secondary action | Show action menu |
| **Swipe Horizontal** | Navigate tabs | Tabs area only |
| **Swipe Vertical** | Scroll page | Main content area |
| **Pull Down** | Refresh | Top of scrollable content |

### Forbidden Gestures

| Gesture | Reason |
|---------|--------|
| Double Tap | Conflicts with single tap |
| Pinch | No zoom needed |
| Drag | Conflicts with scroll |
| Hover | No hover on touch |

### Touch Target Sizes

| Element | Minimum Size |
|---------|--------------|
| Buttons | 44px × 44px |
| Nav Items | 44px × 44px |
| Tab Items | 44px min-height |
| Cards | Full width (tap anywhere) |

---

## Layout Structure

### Vertical Phone (Folded - Primary)

```
+----------------------------------+
|         TOP BAR (48px)           |
+----------------------------------+
|        TABS (44px)               |
+----------------------------------+
|                                  |
|      MAIN CONTENT                |
|      (Scrollable)                |
|      calc(100vh - 148px)         |
|                                  |
+----------------------------------+
|       BOTTOM NAV (56px)          |
+----------------------------------+
```

### Unfolded Phone (Secondary)

```
+----------+-----------------------+
|          |      TOP BAR (56px)   |
| SIDEBAR  +-----------------------+
| (240px)  |                       |
|          |    MAIN CONTENT       |
|          |    (Scrollable)       |
|          |                       |
+----------+-----------------------+
```

---

## CSS Variables

```css
:root {
  /* Colors */
  --bg: #020617;
  --primary: #0F172A;
  --secondary: #1E293B;
  --accent: #22C55E;
  --text: #F8FAFC;
  --text-muted: #94A3B8;
  --border: #334155;
  
  /* Status Colors */
  --green: #22C55E;
  --yellow: #FACC15;
  --indigo: #6366F1;
  --slate: #64748B;
  --red: #EF4444;
  --orange: #F97316;
  
  /* Spacing */
  --spacing-xs: 4px;
  --spacing-sm: 8px;
  --spacing-md: 12px;
  --spacing-lg: 16px;
  
  /* Font Sizes - Vertical */
  --font-title: 16px;
  --font-body: 14px;
  --font-label: 12px;
  --font-small: 11px;
  
  /* Layout - Vertical */
  --top-bar-height: 48px;
  --tabs-height: 44px;
  --bottom-nav-height: 56px;
  --sidebar-width: 240px;
  --card-margin: 8px;
  --card-padding: 12px;
  
  /* Touch */
  --touch-target: 44px;
  
  /* Animation */
  --transition-fast: 150ms ease-out;
  --transition-normal: 200ms ease-out;
  --transition-slow: 300ms ease-out;
  
  /* Toast */
  --toast-bg: rgba(0, 0, 0, 0.85);
  --toast-duration: 2000ms;
}

/* Unfolded Overrides */
@media (min-width: 780px) {
  :root {
    --font-title: 18px;
    --font-body: 15px;
    --font-label: 13px;
    --font-small: 12px;
    --top-bar-height: 56px;
    --card-margin: 12px;
    --card-padding: 16px;
  }
}
```

---

## Typography

### Font Import

```css
@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600&family=Fira+Sans:wght@400;500;600;700&display=swap');
```

### Font Stack

```css
body {
  font-family: 'Fira Code', ui-monospace, monospace;
  font-size: var(--font-body);
  color: var(--text);
  line-height: 1.5;
}

h1, h2, h3, h4, h5, h6 {
  font-family: 'Fira Sans', system-ui, sans-serif;
  font-weight: 600;
  color: var(--text);
}
```

---

## Component Specifications

### 1. Top Bar

```css
.top-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: var(--top-bar-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--spacing-md);
  background: var(--primary);
  border-bottom: 1px solid var(--border);
  z-index: 100;
}

.top-bar-logo {
  font-family: 'Fira Sans', sans-serif;
  font-size: var(--font-title);
  font-weight: 700;
  color: var(--text);
}

.top-bar-status {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-size: var(--font-label);
}

.top-bar-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--green);
}

.top-bar-status-dot.offline {
  background: var(--red);
}

.top-bar-refresh {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--touch-target);
  height: var(--touch-target);
  border-radius: 8px;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.top-bar-refresh:active {
  background: var(--secondary);
}

.top-bar-refresh.loading {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
```

### 2. Tabs

```css
.tabs {
  position: sticky;
  top: var(--top-bar-height);
  height: var(--tabs-height);
  display: flex;
  background: var(--primary);
  border-bottom: 1px solid var(--border);
  z-index: 99;
  /* Prevent vertical scroll in tabs area */
  touch-action: pan-x;
}

.tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 60px;
  min-height: var(--touch-target);
  font-size: var(--font-label);
  color: var(--text-muted);
  cursor: pointer;
  transition: color var(--transition-fast);
  border-bottom: 2px solid transparent;
}

.tab:active {
  background: var(--secondary);
}

.tab.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}

/* Swipe indicator */
.tabs::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  height: 2px;
  background: var(--accent);
  transition: transform var(--transition-normal);
}
```

### 3. Bottom Navigation (Vertical Only)

```css
.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: var(--bottom-nav-height);
  display: flex;
  background: var(--primary);
  border-top: 1px solid var(--border);
  z-index: 100;
}

.bottom-nav-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  min-height: var(--touch-target);
  color: var(--text-muted);
  cursor: pointer;
  transition: color var(--transition-fast);
}

.bottom-nav-item:active {
  background: var(--secondary);
}

.bottom-nav-item.active {
  color: var(--accent);
}

.bottom-nav-item svg {
  width: 24px;
  height: 24px;
}

.bottom-nav-item span {
  font-size: var(--font-small);
}

/* Hide on unfolded */
@media (min-width: 780px) {
  .bottom-nav {
    display: none;
  }
}
```

### 4. Sidebar (Unfolded Only)

```css
.sidebar {
  display: none;
  position: fixed;
  top: var(--top-bar-height);
  left: 0;
  bottom: 0;
  width: var(--sidebar-width);
  background: var(--primary);
  border-right: 1px solid var(--border);
  overflow-y: auto;
  padding: var(--spacing-md);
}

@media (min-width: 780px) {
  .sidebar {
    display: block;
  }
}

.sidebar-section {
  margin-bottom: var(--spacing-lg);
}

.sidebar-section-title {
  font-size: var(--font-small);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  margin-bottom: var(--spacing-sm);
  padding-bottom: var(--spacing-xs);
  border-bottom: 1px solid var(--border);
}

.sidebar-agent-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  border-radius: 8px;
  min-height: var(--touch-target);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.sidebar-agent-item:active {
  background: rgba(255, 255, 255, 0.08);
}

.sidebar-agent-status {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.sidebar-agent-status.online { background: var(--green); }
.sidebar-agent-status.busy { background: var(--yellow); }
.sidebar-agent-status.idle { background: var(--indigo); }
.sidebar-agent-status.offline { background: var(--slate); }
.sidebar-agent-status.dead { background: var(--red); }
.sidebar-agent-status.sick { background: var(--orange); }

.sidebar-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-sm);
}

.sidebar-stat {
  text-align: center;
  padding: var(--spacing-sm);
  background: var(--secondary);
  border-radius: 8px;
}

.sidebar-stat-value {
  font-size: var(--font-title);
  font-weight: 600;
  color: var(--text);
}

.sidebar-stat-label {
  font-size: var(--font-small);
  color: var(--text-muted);
}
```

### 5. Agent Card

```css
.agent-card {
  background: var(--primary);
  border: 1px solid var(--border);
  border-radius: 12px;
  margin-bottom: var(--card-margin);
  overflow: hidden;
  transition: background var(--transition-fast);
}

.agent-card:active {
  background: var(--secondary);
}

.agent-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--card-padding);
  min-height: var(--touch-target);
  cursor: pointer;
}

.agent-card-id {
  font-family: 'Fira Sans', sans-serif;
  font-size: var(--font-title);
  font-weight: 600;
  color: var(--text);
}

.agent-card-meta {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.agent-card-time {
  font-size: var(--font-small);
  color: var(--text-muted);
}

.agent-card-body {
  display: none;
  padding: 0 var(--card-padding) var(--card-padding);
  border-top: 1px solid var(--border);
}

.agent-card.expanded .agent-card-body {
  display: block;
}

.agent-card-detail {
  display: flex;
  justify-content: space-between;
  padding: var(--spacing-xs) 0;
  font-size: var(--font-body);
}

.agent-card-detail-label {
  color: var(--text-muted);
}

.agent-card-detail-value {
  color: var(--text);
}

.agent-card-expand-icon {
  transition: transform var(--transition-fast);
}

.agent-card.expanded .agent-card-expand-icon {
  transform: rotate(180deg);
}
```

### 6. Task Card

```css
.task-card {
  background: var(--primary);
  border: 1px solid var(--border);
  border-radius: 12px;
  margin-bottom: var(--card-margin);
  overflow: hidden;
  transition: background var(--transition-fast);
}

.task-card:active {
  background: var(--secondary);
}

.task-card-header {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
  padding: var(--card-padding);
  min-height: var(--touch-target);
  cursor: pointer;
}

.task-card-id {
  font-size: var(--font-body);
  font-weight: 600;
  color: var(--accent);
  flex-shrink: 0;
}

.task-card-title {
  flex: 1;
  font-size: var(--font-body);
  font-weight: 500;
  color: var(--text);
}

.task-card-badges {
  display: flex;
  gap: var(--spacing-xs);
  margin-top: var(--spacing-xs);
  flex-wrap: wrap;
}

.task-card-body {
  display: none;
  padding: 0 var(--card-padding);
  border-top: 1px solid var(--border);
}

.task-card.expanded .task-card-body {
  display: block;
}

.task-card-details {
  padding: var(--spacing-sm) 0;
}

.task-card-detail-row {
  display: flex;
  gap: var(--spacing-sm);
  padding: var(--spacing-xs) 0;
  font-size: var(--font-body);
}

.task-card-detail-label {
  color: var(--text-muted);
  min-width: 80px;
}

.task-card-detail-value {
  color: var(--text);
}

.task-card-notes {
  background: var(--secondary);
  padding: var(--spacing-sm);
  border-radius: 8px;
  margin-top: var(--spacing-sm);
  font-size: var(--font-body);
  color: var(--text-muted);
  white-space: pre-wrap;
}

.task-card-children {
  margin-top: var(--spacing-sm);
  padding-left: var(--spacing-md);
  border-left: 2px solid var(--border);
}

.task-card-actions {
  display: none;
  padding: var(--card-padding);
  border-top: 1px solid var(--border);
  gap: var(--spacing-sm);
}

.task-card.expanded .task-card-actions {
  display: block;
}

.task-card-priority-buttons {
  display: flex;
  gap: var(--spacing-xs);
  margin-bottom: var(--spacing-sm);
}

.task-card-action-buttons {
  display: flex;
  gap: var(--spacing-xs);
}
```

### 7. Status Badge

```css
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: var(--font-small);
  font-weight: 600;
  white-space: nowrap;
}

.status-badge .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.status-online {
  background: rgba(34, 197, 94, 0.15);
  color: var(--green);
}

.status-online .dot {
  background: var(--green);
  box-shadow: 0 0 8px var(--green);
}

.status-busy {
  background: rgba(250, 204, 21, 0.15);
  color: var(--yellow);
}

.status-busy .dot {
  background: var(--yellow);
  animation: pulse 2s ease-in-out infinite;
}

.status-idle {
  background: rgba(99, 102, 241, 0.15);
  color: var(--indigo);
}

.status-idle .dot {
  background: var(--indigo);
}

.status-offline {
  background: rgba(100, 116, 139, 0.15);
  color: var(--slate);
}

.status-offline .dot {
  background: var(--slate);
}

.status-dead {
  background: rgba(239, 68, 68, 0.15);
  color: var(--red);
}

.status-dead .dot {
  background: var(--red);
}

.status-sick {
  background: rgba(249, 146, 60, 0.15);
  color: var(--orange);
}

.status-sick .dot {
  background: var(--orange);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
```

### 8. Buttons

```css
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-sm) var(--spacing-md);
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: var(--font-label);
  font-weight: 500;
  cursor: pointer;
  min-height: var(--touch-target);
  min-width: var(--touch-target);
  transition: all var(--transition-fast);
  user-select: none;
}

.btn:active {
  transform: scale(0.98);
}

.btn:disabled {
  opacity: 0.5;
  pointer-events: none;
}

.btn-primary {
  background: var(--accent);
  color: #000;
  border-color: var(--accent);
}

.btn-primary:active {
  background: #16a34a;
}

.btn-secondary {
  background: var(--secondary);
  color: var(--text);
}

.btn-secondary:active {
  background: var(--primary);
}

.btn-ghost {
  background: transparent;
  color: var(--text-muted);
  border-color: transparent;
}

.btn-ghost:active {
  background: var(--secondary);
}

.btn-icon {
  padding: var(--spacing-sm);
}

.btn-small {
  font-size: var(--font-small);
  padding: var(--spacing-xs) var(--spacing-sm);
  min-height: 36px;
}

.btn-loading {
  position: relative;
  color: transparent;
}

.btn-loading::after {
  content: '';
  position: absolute;
  width: 16px;
  height: 16px;
  border: 2px solid var(--text-muted);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* Priority buttons */
.btn-priority {
  flex: 1;
  background: var(--secondary);
  color: var(--text-muted);
  border-color: var(--border);
}

.btn-priority.active {
  background: var(--accent);
  color: #000;
  border-color: var(--accent);
}

.btn-priority-high.active {
  background: var(--red);
  border-color: var(--red);
}

.btn-priority-medium.active {
  background: var(--yellow);
  border-color: var(--yellow);
  color: #000;
}

.btn-priority-low.active {
  background: var(--green);
  border-color: var(--green);
  color: #000;
}
```

### 9. Toast

```css
.toast-container {
  position: fixed;
  bottom: 80px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 1000;
  pointer-events: none;
}

.toast {
  background: var(--toast-bg);
  color: var(--text);
  padding: var(--spacing-sm) var(--spacing-lg);
  border-radius: 8px;
  font-size: var(--font-body);
  white-space: nowrap;
  animation: toastIn var(--transition-normal) ease-out;
}

.toast.toast-out {
  animation: toastOut var(--transition-fast) ease-in forwards;
}

.toast-error {
  background: rgba(239, 68, 68, 0.9);
}

.toast-success {
  background: rgba(34, 197, 94, 0.9);
}

@keyframes toastIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes toastOut {
  from {
    opacity: 1;
    transform: translateY(0);
  }
  to {
    opacity: 0;
    transform: translateY(-20px);
  }
}
```

### 10. Loading States

```css
/* Skeleton */
.skeleton {
  background: var(--secondary);
  border-radius: 8px;
  animation: skeleton-pulse 1.5s ease-in-out infinite;
}

.skeleton-text {
  height: 14px;
  margin-bottom: var(--spacing-xs);
}

.skeleton-text.short {
  width: 60%;
}

.skeleton-title {
  height: 18px;
  width: 80%;
  margin-bottom: var(--spacing-sm);
}

.skeleton-card {
  height: 80px;
  margin-bottom: var(--card-margin);
}

@keyframes skeleton-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* Spinner */
.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.spinner.small {
  width: 16px;
  height: 16px;
}

.spinner.large {
  width: 32px;
  height: 32px;
}

/* Page loading */
.page-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--text-muted);
}
```

### 11. Empty State

```css
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-lg) * 2;
  text-align: center;
}

.empty-state-icon {
  font-size: 48px;
  margin-bottom: var(--spacing-md);
  opacity: 0.5;
}

.empty-state-title {
  font-size: var(--font-title);
  color: var(--text);
  margin-bottom: var(--spacing-sm);
}

.empty-state-text {
  font-size: var(--font-body);
  color: var(--text-muted);
}
```

### 12. Error Banner

```css
.error-banner {
  position: fixed;
  top: var(--top-bar-height);
  left: 0;
  right: 0;
  padding: var(--spacing-sm) var(--spacing-md);
  background: rgba(239, 68, 68, 0.9);
  color: white;
  font-size: var(--font-body);
  text-align: center;
  z-index: 99;
  animation: slideDown var(--transition-normal) ease-out;
}

.error-banner-close {
  position: absolute;
  right: var(--spacing-md);
  top: 50%;
  transform: translateY(-50%);
  padding: var(--spacing-xs);
  cursor: pointer;
}

@keyframes slideDown {
  from {
    transform: translateY(-100%);
  }
  to {
    transform: translateY(0);
  }
}
```

### 13. Filter Buttons

```css
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
  padding: var(--spacing-sm);
  background: var(--primary);
  border-bottom: 1px solid var(--border);
}

.filter-btn {
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--secondary);
  border: 1px solid var(--border);
  border-radius: 20px;
  font-size: var(--font-label);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
  min-height: 36px;
}

.filter-btn:active {
  background: var(--primary);
}

.filter-btn.active {
  background: var(--accent);
  color: #000;
  border-color: var(--accent);
}

.filter-search {
  flex: 1;
  min-width: 150px;
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: var(--font-body);
  color: var(--text);
  min-height: 36px;
}

.filter-search::placeholder {
  color: var(--text-muted);
}
```

### 14. Action Menu (Long Press)

```css
.action-menu-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1000;
  animation: fadeIn var(--transition-fast) ease-out;
}

.action-menu {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--primary);
  border-radius: 16px 16px 0 0;
  padding: var(--spacing-md);
  padding-bottom: calc(var(--spacing-md) + env(safe-area-inset-bottom));
  z-index: 1001;
  animation: slideUp var(--transition-normal) ease-out;
}

.action-menu-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  border-radius: 8px;
  font-size: var(--font-body);
  color: var(--text);
  cursor: pointer;
  min-height: var(--touch-target);
  transition: background var(--transition-fast);
}

.action-menu-item:active {
  background: var(--secondary);
}

.action-menu-item.destructive {
  color: var(--red);
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}
```

### 15. Coming Soon Page

```css
.coming-soon {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: var(--spacing-lg);
  text-align: center;
}

.coming-soon-icon {
  font-size: 64px;
  margin-bottom: var(--spacing-md);
}

.coming-soon-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: var(--spacing-sm);
}

.coming-soon-text {
  font-size: var(--font-body);
  color: var(--text-muted);
}
```

### 16. Config Page

```css
.config-section {
  margin-bottom: var(--spacing-lg);
}

.config-section-title {
  font-size: var(--font-label);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  margin-bottom: var(--spacing-sm);
  padding-bottom: var(--spacing-xs);
  border-bottom: 1px solid var(--border);
}

.config-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-sm) 0;
  border-bottom: 1px solid var(--border);
}

.config-item:last-child {
  border-bottom: none;
}

.config-label {
  font-size: var(--font-body);
  color: var(--text-muted);
}

.config-value {
  font-size: var(--font-body);
  color: var(--text);
  font-family: 'Fira Code', monospace;
}
```

---

## Touch Event Handling

### Swipe Detection

```javascript
function setupSwipe(container, onSwipeLeft, onSwipeRight) {
  let startX = 0;
  let startY = 0;
  const threshold = 50;
  
  container.addEventListener('touchstart', (e) => {
    startX = e.touches[0].clientX;
    startY = e.touches[0].clientY;
  });
  
  container.addEventListener('touchend', (e) => {
    const endX = e.changedTouches[0].clientX;
    const endY = e.changedTouches[0].clientY;
    const diffX = endX - startX;
    const diffY = endY - startY;
    
    // Only trigger if horizontal swipe is dominant
    if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > threshold) {
      if (diffX > 0) onSwipeRight();
      else onSwipeLeft();
    }
  });
}
```

### Long Press Detection

```javascript
function setupLongPress(element, callback, duration = 500) {
  let timer = null;
  let moved = false;
  
  element.addEventListener('touchstart', (e) => {
    moved = false;
    timer = setTimeout(() => {
      if (!moved) {
        callback(e);
        // Haptic feedback if available
        if (navigator.vibrate) navigator.vibrate(50);
      }
    }, duration);
  });
  
  element.addEventListener('touchmove', () => {
    moved = true;
    clearTimeout(timer);
  });
  
  element.addEventListener('touchend', () => {
    clearTimeout(timer);
  });
}
```

### Pull to Refresh

```javascript
function setupPullToRefresh(container, onRefresh) {
  let startY = 0;
  let pulling = false;
  
  container.addEventListener('touchstart', (e) => {
    if (container.scrollTop === 0) {
      startY = e.touches[0].clientY;
      pulling = true;
    }
  });
  
  container.addEventListener('touchmove', (e) => {
    if (!pulling) return;
    const currentY = e.touches[0].clientY;
    const diff = currentY - startY;
    if (diff > 60) {
      container.style.transform = `translateY(${Math.min(diff - 60, 80)}px)`;
    }
  });
  
  container.addEventListener('touchend', (e) => {
    if (!pulling) return;
    const endY = e.changedTouches[0].clientY;
    const diff = endY - startY;
    container.style.transform = '';
    pulling = false;
    if (diff > 140) onRefresh();
  });
}
```

---

## Accessibility

### Focus Visible

```css
:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
```

### Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

### ARIA Labels

```html
<button class="btn-icon" aria-label="刷新数据">
  <svg aria-hidden="true">...</svg>
</button>

<nav class="bottom-nav" aria-label="主导航">
  <a class="bottom-nav-item" aria-current="page">...</a>
</nav>

<span class="status-badge status-online" role="status" aria-label="状态: 在线">
  <span aria-hidden="true">●</span>
  Online
</span>
```

---

## Performance

### CSS Containment

```css
.agent-card, .task-card {
  contain: layout style paint;
}
```

### GPU Acceleration

```css
.card, .toast, .action-menu {
  will-change: transform;
  transform: translateZ(0);
}
```

### Font Preload

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
```

---

**END OF MOBILE UI SPECIFICATION**
