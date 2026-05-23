# Portfolio Case Study: PyHoldem Pro

## The Context & Problem
In competitive Texas Hold'em poker, the difference between a winning and losing player lies in identifying and patching marginal leaks—strategic decisions that lose expected value (EV) over the long run. While solver-grade software exists for professional players, it suffers from significant inefficiencies:
1. **High Barriers to Entry:** Traditional solvers require expensive desktop licenses, complex configuration, and manual data entry.
2. **Privacy Concerns:** Cloud-based training platforms require users to upload their private hand histories, exposing proprietary playing styles to third-party databases.
3. **Lack of Integration:** Basic simulators let players play hands but do not evaluate the decisions mathematically in real time, while static drill tools fail to adapt to a player's observed weaknesses.

PyHoldem Pro addresses this market gap by delivering an open-source, local-first, highly integrated gameplay simulator, automated coaching assistant, and statistical training platform. It runs locally to guarantee absolute data privacy while executing real-time EV-based grading, Bayesian playing-style classifications, and spaced-repetition training drills.

## The Solution & Impact
PyHoldem Pro provides an end-to-end training pipeline. The application consists of a concurrent CLI simulator and a modern React web dashboard connected via a FastAPI application server. 

### Key Tangible Results:
- **Absolute Local Data Privacy:** Player profiles, hand logs, and neural bandit parameters are persisted locally via JSON file-system storage or a local PostgreSQL instance, eliminating cloud leakage.
- **Real-Time Automated Coaching:** Every human decision point is evaluated against mathematical baselines. The system immediately outputs the EV loss in big blinds, pinpointing costly mistakes.
- **Adaptive Spaced-Repetition Drills:** The training engine maps weaknesses (e.g., "Too Loose", "Poor Pot Odds") to specific focus areas, dynamically serving scenarios where the player has historically struggled.
- **Robust Test Coverage:** The platform is backed by a suite of 630+ passing tests verifying core game loops, pot distributions, side pots, Bayesian credible intervals, and tournament payouts.

## System Architecture
The application is structured as a decoupled, multi-tier system designed to be lightweight, modular, and deployment-friendly via Docker containers.

```
+--------------------------------------------------------------+
|                User Interface (React / TS)                   |
|  +--------------------+  +--------------------+  +--------+  |
|  | Gameplay & HUD UI  |  | Analytics Charts   |  | Drills |  |
|  +--------------------+  +--------------------+  +--------+  |
+------------------------------+-------------------------------+
                               |
                   HTTP / WebSockets Connection
                               v
+--------------------------------------------------------------+
|               FastAPI Application Server                     |
|  +------------------+  +--------------------+  +----------+  |
|  | REST API Router  |  | WS Event Streamer  |  | Middleware | |
|  +------------------+  +--------------------+  +----------+  |
+------------------------------+-------------------------------+
                               |
                               v
+--------------------------------------------------------------+
|                  Core Python Logic Layer                     |
|  +--------------------+  +------------------+  +----------+  |
|  | Game/Rules Engine  |  | Training Service |  | Math/EVs |  |
|  +--------------------+  +------------------+  +----------+  |
+------------------------------+-------------------------------+
                               |
            SQLAlchemy ORM / Local Storage Writer
                               v
+--------------------------------------------------------------+
|                      Persistence Layer                       |
|   +--------------------+     +---------------------------+   |
|   | PostgreSQL / JSON  |     | GTO Policy / CFR Models   |   |
|   +--------------------+     +---------------------------+   |
+--------------------------------------------------------------+
```

### Architectural Decisions & Stack Justification:
- **Frontend (React 18 + TypeScript + Vite):** Selected for high performance rendering of fast-updating table states and dashboard UI components. Vite provides instantaneous Hot Module Replacement (HMR) during development. Type safety with TypeScript ensures complex WebSocket payloads remain compliant with backend contracts.
- **Backend (Python 3.13 + FastAPI + Uvicorn):** Python was selected due to its mathematical libraries and hand evaluation speed. FastAPI handles concurrent operations efficiently using ASGI, routing REST endpoints and persistent WebSockets connections (for live table game state pushes) with low latency.
- **Persistence (PostgreSQL + SQLAlchemy + Alembic):** Relational structures are mapped using SQLAlchemy, enabling a seamless transition from local JSON file storage (`data/players.json`) to enterprise-grade PostgreSQL using environment variables. Alembic manages structural database schema migrations.
- **Observability (Prometheus + Grafana):** Configured as a Docker compose overlay to scrape application metrics, exposing API response latencies, game loop performance, and ASGI server health metrics.

## Core Engineering Challenges

### 1. Scaling CPU-Bound Monte Carlo Calculations in an ASGI Event Loop
*The Hurdle:* Computing heads-up and multiway range-vs-range preflop/postflop equity requires running thousands of Monte Carlo card deal simulations. Running these heavy mathematical calculations synchronously inside FastAPI's event loop blocks execution, causing WebSocket connection timeouts and API freezes.
*The Solution:* The simulation engine was optimized by implementing a highly compressed lookup table and a fast hand evaluation module (`fast_eval.py`). Additionally, identical board/hand combinations are cached, and exact enumeration is preferred over Monte Carlo when cards-to-come are low (e.g., on the river). This reduced execution times from seconds to single-digit milliseconds.

### 2. Preventing Client-Side Inspection in Quizzes and Drills
*The Hurdle:* In online training tools, users can cheat or bypass quiz math by inspecting client-side React states or API JSON payloads.
*The Solution:* We designed a server-owned quiz and drill validation structure. The frontend requests a quiz via a unique server-generated `quiz_id`. The correct answers are cached privately in the backend's transient player progress files. The user submits their numeric or text answer to `POST /api/training/quiz/evaluate`, which performs the tolerance calculation (absolute or relative margins) server-side and writes the results directly to the database before exposing the feedback.

### 3. Scaling Exact Malmuth-Harville ICM Permutations
*The Hurdle:* Computing tournament equity using the Independent Chip Model (ICM) requires running permutations of finishing positions across player stacks. For a 9-handed final table, evaluating exact permutations requires $9! = 362,880$ iterations, creating a severe bottleneck.
*The Solution:* We designed an optimized recursion algorithm (`icm_calculator.py`) that calculates probabilities in $O(2^n \cdot n)$ using memoized sub-state stack weights. For small tables ($n \le 6$), it defaults to exact permutation indexing, while for larger fields ($7 \le n \le 9$), it implements the dynamic programming approach, ensuring completion under $5$ milliseconds.

## Future Roadmap
1. **Asynchronous Background Processing:** Integrate Celery and Redis to handle CPU-intensive CFR (Counterfactual Regret Minimization) solving and multiway simulations outside the web request cycle.
2. **Weekly Study Plans:** Develop an automated study recommendation scheduler that generates 7-day drills focused on the user's highest EV-loss spots.
3. **Advanced Log Exporting:** Implement log export services supporting standard formats (e.g., PokerStars-compatible text logs) to allow external commercial solver analysis.
