# Frontend Stack & Design Specification

This document details the frontend architecture, technology stack, design system, and page hierarchy for PyHoldem Pro.

---

## 1. Technology Stack

The frontend is a lightweight Single-Page Application (SPA) designed for local-first execution.

- **Core Library:** React 18.2 (Functional Components & Hooks).
- **Language:** TypeScript (Strict type checking for API payloads and WebSocket messages).
- **Build Tool:** Vite (For instant dev server starts and optimized production builds).
- **Routing:** React Router DOM v6.
- **Charts & Visualizations:** Apache ECharts (Integrated via lazy-loaded components for performance).
- **WebSocket client:** Native browser `WebSocket` API for real-time state synchronization.

---

## 2. Design System & Styling

PyHoldem Pro relies on a custom Vanilla CSS design system (located in `frontend/src/styles/`) for maximum flexibility, fast rendering, and clean layouts.

### 2.1 Color Palette (Dark Theme)
- **Background-Primary:** Deep Slate `#0f172a` (slate-900)
- **Background-Secondary:** Card/Panel Grey `#1e293b` (slate-800)
- **Text-Primary:** Bright Off-White `#f8fafc` (slate-50)
- **Text-Secondary:** Muted Grey `#94a3b8` (slate-400)
- **Accents:**
  - **Success / Green (Optimal/Profit):** `#10b981` (emerald-500)
  - **Warning / Orange (Suboptimal):** `#f59e0b` (amber-500)
  - **Danger / Red (Mistake/Loss):** `#ef4444` (red-500)
  - **HUD Blue:** `#3b82f6` (blue-500)

### 2.2 Typography
- **Primary Font:** `Inter` or system-default sans-serif.
- **Headers:** Crisp headings utilizing geometric letter-spacing.

---

## 3. UI Component & Page Layouts

The application is structured around a central Layout Shell (`Shell.tsx`) providing sidebar navigation to the core views:

### 3.1 Home / Welcome (`Home.tsx`)
- Selection/Creation of player profiles.
- Summary of player bankroll, hands played, and current skill level.

### 3.2 Live Table Session (`Session.tsx` & `Table.tsx`)
- Canvas or CSS-grid rendering of the poker table.
- Interactive seat nodes displaying player actions, dealer button, and active bet sizes.
- **HUD Overlays:** Outs calculator, pot odds calculator, and real-time hand strength metrics.
- **Coaching Sidebar:** Interactive cards revealing coach recommendations and post-hand feedback.

### 3.3 Training Hub (`Training.tsx`)
- Interactive mathematical quizzes (Pot Odds, Implied Odds, Sizing).
- **Leak Radar:** Listing of identified leaks (e.g., "Too Loose", "Poor Pot Odds").
- Focus Queue launcher.

### 3.4 Drills Stepper (`Drill.tsx`)
- Focus-area practice runner.
- Stepper component providing scenario context (Hole cards, Position, Opponent type, and Board texture) and validating user action selections.

### 3.5 Analytics Dashboard (`Analytics.tsx`)
- **Bayesian Cards:** VPIP, PFR, and Aggression Factor cards showing credible intervals.
- **Trend Charts:** Realized vs. EV-adjusted cumulative profit lines.
- **Quant Panels:** Risk of Ruin, Kelly sizing, and tournament ICM bubble calculators.

### 3.6 Replay Vault (`Replay.tsx` & `ReplayDetail.tsx`)
- Directory of recorded hand histories with filters (Game type, street, profit, or leak type).
- Interactive street-by-street replayer displaying the exact decisions made, alongside recommendations and EV loss analysis.
