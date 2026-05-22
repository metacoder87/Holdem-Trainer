export const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const normalizePath = (path: string) => (path.startsWith("/") ? path : `/${path}`);

export const getWebSocketUrl = (path: string) => {
  const base = new URL(API_URL);
  const protocol = base.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${base.host}${normalizePath(path)}`;
};

// Convenience base for callers that want to build their own ws:// path. Either
// VITE_WS_URL takes precedence (so docker-compose can swap the wsk URL at
// build time) or we derive it from API_URL.
export const WS_URL =
  (import.meta.env.VITE_WS_URL as string | undefined) ||
  API_URL.replace(/^http/, "ws");

// Surfaced so callers (Session.tsx) can distinguish 404/410 "stale session"
// from generic network failures. `requestJson` throws this for !response.ok.
export class ApiError extends Error {
  constructor(public status: number, message: string, public body?: string) {
    super(message);
    this.name = "ApiError";
  }
}

export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

export type Metric = {
  label: string;
  value: string;
  delta: string;
  tone: "good" | "warn" | "bad";
};

export type TrainingTrack = {
  title: string;
  summary: string;
  cadence: string;
  intensity: string;
  progress: number;
};

export type TimelineEntry = {
  time: string;
  label: string;
  detail: string;
};

export type FocusQueueItem = {
  id?: string | null;
  label: string;
};

export type SummaryResponse = {
  player: {
    name: string;
    skill_level?: string | null;
    last_played?: string | null;
  };
  live_metrics: Metric[];
  training_tracks: TrainingTrack[];
  focus_queue: string[];
  focus_queue_items?: FocusQueueItem[];
  timeline: TimelineEntry[];
};

export type PlayerSummary = {
  name: string;
  bankroll: number;
  last_played?: string | null;
  skill_level?: string | null;
};

export type BankrollSummary = {
  total_players: number;
  total_bankroll: number;
  total_games_played: number;
};

export type TrainingContent = {
  tips: Array<{ title: string; content: string; category?: string; difficulty?: string }>;
  vocabulary: Array<{ term: string; definition: string; example?: string }>;
  strategy_guides: Array<{ title: string; content: string; category?: string; difficulty?: string }>;
  cheat_sheets: Record<string, JsonValue>;
};

export type TrainingQuiz = {
  quiz_id: string;
  player?: string;
  generated_at?: string;
  type: string;
  question: string;
  difficulty: number;
};

export type TrainingDrill = {
  drill_id: string;
  player: string;
  focus_area: string;
  generated_at?: string;
  configuration: {
    focus_areas: string[];
    quiz_distribution: Record<string, number>;
    difficulty: number;
    estimated_duration: number;
    weakness_targets: string[];
  };
  scenario: Record<string, JsonValue>;
  quiz: Record<string, JsonValue>;
  curriculum: Record<string, JsonValue>;
};

export type QuizEvaluation = {
  correct: boolean;
  user_answer: JsonValue;
  correct_answer: number | string;
  difference?: number;
  feedback: string;
  explanation?: string;
  quiz_id?: string;
  quiz_type?: string;
  performance_stats?: {
    total_quizzes: number;
    correct_answers: number;
    accuracy?: number | null;
    streak?: number;
    best_streak?: number;
  };
};

export type TrainingProgress = {
  player: string;
  schema_version?: number;
  quiz_attempts: Array<Record<string, JsonValue>>;
  drill_attempts: Array<Record<string, JsonValue>>;
  weakness_history: Record<string, JsonValue>;
  mastery_progress: Record<string, number>;
  study_recommendations: string[];
  quiz_stats: {
    total: number;
    correct: number;
    accuracy?: number | null;
  };
  drill_stats: {
    total: number;
    correct: number;
    accuracy?: number | null;
  };
};

export type DrillEvaluation = {
  drill_id: string;
  focus_area: string;
  correct: boolean;
  feedback: string;
  user_answer: JsonValue;
  correct_answer: JsonValue;
  explanation?: string;
  recommended_actions: string[];
  progress: Omit<TrainingProgress, "player">;
};

export type GameMode = {
  id: string;
  label: string;
  description: string;
  defaults: {
    small_blind?: number;
    big_blind?: number;
    opponents?: number;
    buy_in?: number;
    starting_chips?: number;
  };
};

export type GameSession = {
  id: string;
  player_name: string;
  game_type: string;
  limit_type: string;
  status: string;
  terminal_reason?: string | null;
  config: Record<string, JsonValue>;
};

export type SavedGameSession = {
  id: string;
  player_name?: string;
  game_type?: string;
  limit_type?: string;
  status?: string;
  terminal_reason?: string | null;
  updated_at?: number | string | null;
  hands_played?: number;
  hero_stack?: number | null;
  last_hand?: HandHistory | null;
};

export type WinningHand = {
  player: string;
  rank?: string | null;
  cards?: string[];
  hole_cards?: string[];
};

export type HandHistory = {
  session_id?: string;
  hand_number?: number;
  started_at?: string;
  hero_hole_cards?: string[];
  board?: string[];
  pot_total?: number;
  winners?: string[];
  winning_hands?: WinningHand[];
  won_by_fold?: boolean;
  winner?: string;
  winning_hand_rank?: string | null;
  actions?: Array<{
    player: string;
    action: string;
    amount: number;
    pot_before: number;
    pot_after: number;
    betting_round: string;
  }>;
  decision_points?: Array<{
    betting_round?: string;
    chosen_action?: string;
    chosen_amount?: number;
    recommended_action?: string;
    quality?: string;
    equity?: number;
    required_equity?: number;
    chosen_ev_chips?: number | null;
    best_ev_chips?: number | null;
    ev_loss_chips?: number | null;
    ev_loss_bb?: number | null;
    ev_method?: string | null;
    outs?: Record<string, JsonValue>;
    analysis?: Record<string, JsonValue>;
    // Track 3 fields surfaced for the per-decision audit table.
    pot_total?: number;
    to_call?: number;
    hero_stack?: number;
    hero_position?: number;
    spr?: number;
    spr_bucket?: number;
    board?: string[];
    hero_hole_cards?: string[];
  }>;
  meta?: Record<string, JsonValue>;
  board_by_street?: Record<string, string[]>;
  // Optional engine output - present when the post-hand feedback pipeline
  // populates it. Session.tsx renders a card when this is non-null.
  coach_notes?: {
    hero_won: boolean;
    headline: string;
    hand_grade: string;
    takeaway?: string | null;
    worst_decision?: {
      betting_round?: string;
      chosen_action?: string;
      recommended_action?: string;
      quality?: string;
      equity?: number;
      required_equity?: number;
      line?: string;
      gto?: GtoAdvice | null;
    } | null;
    decision_count?: number;
    // Top-level GTO summary mirrors worst_decision.gto when present
    // so the UI can render the comparison without drilling.
    gto_summary?: GtoSummary | null;
  } | null;
};

// Per-decision GTO advice payload from backend/app/services/gto_advisor.py.
// Present only when the cached CFR cache covered this spot.
export type GtoAdvice = {
  gto_action: string;
  gto_frequency: number;
  hero_action?: string | null;
  hero_frequency?: number | null;
  ev_delta_bb?: number | null;
  action_breakdown?: Record<string, number>;
  source: string;
  spot_signature: string;
  iterations?: number | null;
};

// Trimmed copy of GtoAdvice that the coach_notes panel renders directly.
export type GtoSummary = {
  gto_action?: string | null;
  gto_frequency?: number | null;
  hero_action?: string | null;
  hero_frequency?: number | null;
  ev_delta_bb?: number | null;
  action_breakdown?: Record<string, number> | null;
  spot_signature?: string | null;
};

export type HudOpponent = {
  name: string;
  hands: number;
  vpip: number;
  pfr: number;
  aggression_factor: number;
  type: string;
};

export type PendingInput = {
  kind: "menu" | "number" | "yes_no";
  prompt: string;
  options?: string[] | null;
  min_value?: number | null;
  max_value?: number | null;
  integer_only?: boolean | null;
};

export type LiveCoach = {
  recommended_action: string;
  confidence: number;
  summary: string;
  math: {
    pot: number;
    to_call: number;
    pot_odds?: number | null;
    required_equity?: number | null;
    estimated_equity?: number | null;
    equity_edge?: number | null;
    hand_strength?: number | null;
    hand_potential?: number | null;
    outs?: Record<string, JsonValue>;
    spr?: number | null;
    effective_stack?: number | null;
  };
  opponent?: {
    name?: string | null;
    type: string;
    hands: number;
    vpip: number;
    pfr: number;
    aggression_factor: number;
  } | null;
  rationale: string[];
  warnings: string[];
  history_signals: string[];
  training_link?: string | null;
};

export type LiveGameState = {
  game_state: string;
  community_cards: string[];
  pot_size: number;
  players: Array<{
    name: string;
    bankroll: number;
    current_bet: number;
    folded: boolean;
    all_in: boolean;
    position?: number;
    // Seat-role markers (Track 3 UX). Optional so legacy responses
    // without them still typecheck.
    is_dealer?: boolean;
    is_small_blind?: boolean;
    is_big_blind?: boolean;
    is_hero?: boolean;
  }>;
  next_to_act?: string | null;
  blinds?: {
    small_blind?: number;
    big_blind?: number;
    blind_level?: number | null;
    dealer_name?: string | null;
    small_blind_player?: string | null;
    big_blind_player?: string | null;
  };
  hero_cards?: string[];
  hero_name?: string;
  hero_bankroll?: number;
  hand_number?: number;
  game_over_reason?: string | null;
  // Optional HUD payload - present when the engine has enough hand history to
  // compute opponent stats. Session.tsx renders a table when populated.
  hud?: {
    opponents: HudOpponent[];
  } | null;
};

export type TournamentResult = {
  result: "won" | "lost" | "forfeit";
  final_bankroll: number;
  chip_stack_at_end?: number;
};

export type GameHandState = {
  session_id: string;
  status: string;
  state: LiveGameState;
  pending_input?: PendingInput | null;
  live_coach?: LiveCoach | null;
  input_error?: string | null;
  last_hand?: HandHistory | null;
  terminal_reason?: string | null;
  error?: string | null;
  // Populated when a tournament resolves (won/lost/forfeit). Used by Session.tsx
  // to render a one-line settlement banner.
  tournament_result?: TournamentResult | null;
};

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: JsonValue;
};

function errorMessageFromBody(body: string, status: number) {
  if (body) {
    try {
      const payload = JSON.parse(body) as { detail?: unknown; message?: unknown; error?: unknown };
      const detail = payload.detail ?? payload.message ?? payload.error;
      if (typeof detail === "string" && detail.trim()) {
        return detail;
      }
    } catch {
      // Non-JSON responses still fall back to the raw response text.
    }
    return body;
  }
  return `Request failed: ${status}`;
}

async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    },
    body: options.body ? JSON.stringify(options.body) : undefined
  });

  if (!response.ok) {
    const body = await response.text();
    throw new ApiError(
      response.status,
      errorMessageFromBody(body, response.status),
      body
    );
  }

  return response.json() as Promise<T>;
}

export async function getHealth() {
  return requestJson<{ status: string }>("/health");
}

export async function getSummary(player?: string) {
  const query = player ? `?player=${encodeURIComponent(player)}` : "";
  return requestJson<SummaryResponse>(`/api/summary${query}`);
}

// ---------- Track 4 adaptive engine types ----------

export type BanditArmReport = {
  topic: string;
  alpha: number;
  beta: number;
  pulls: number;
  expected_accuracy: number;
  ci_lower: number;
  ci_upper: number;
};

export type AdaptiveProgressionReport = {
  player?: string;
  bandit: BanditArmReport[];
  next_topic: string | null;
  srs: {
    total_cards: number;
    due_count: number;
    due_card_ids: string[];
  };
  elo: {
    player_rating: number;
    attempts: number;
    tracked_scenarios: number;
  };
};

export async function getAdaptiveProgression(player?: string) {
  const query = player ? `?player=${encodeURIComponent(player)}` : "";
  return requestJson<AdaptiveProgressionReport>(
    `/api/training/progression${query}`
  );
}

export async function getNextBanditTopic(player?: string) {
  const query = player ? `?player=${encodeURIComponent(player)}` : "";
  return requestJson<{
    player: string;
    topic: string;
    bandit: BanditArmReport[];
  }>(`/api/training/progression/next-topic${query}`);
}

export async function postBanditResult(payload: {
  player: string;
  topic: string;
  correct: boolean;
}) {
  return requestJson<AdaptiveProgressionReport>(
    "/api/training/progression/bandit-result",
    { method: "POST", body: payload as unknown as JsonValue }
  );
}

export async function postSrsReview(payload: {
  player: string;
  card_id: string;
  quality: number;
}) {
  return requestJson<AdaptiveProgressionReport>(
    "/api/training/progression/srs-review",
    { method: "POST", body: payload as unknown as JsonValue }
  );
}

export async function postScenarioResult(payload: {
  player: string;
  scenario_id: string;
  player_won: boolean;
}) {
  return requestJson<AdaptiveProgressionReport>(
    "/api/training/progression/scenario-result",
    { method: "POST", body: payload as unknown as JsonValue }
  );
}

export async function getTrainingContent() {
  return requestJson<TrainingContent>("/api/training/content");
}

export async function getTrainingQuiz(quizType: string, player?: string, potSize?: number, betToCall?: number) {
  const params = new URLSearchParams({ quiz_type: quizType });
  if (player) params.set("player", player);
  if (potSize !== undefined) params.set("pot_size", String(potSize));
  if (betToCall !== undefined) params.set("bet_to_call", String(betToCall));
  return requestJson<TrainingQuiz>(`/api/training/quiz?${params.toString()}`);
}

export async function evaluateTrainingQuiz(
  quizId: string,
  userAnswer: JsonValue,
  player?: string,
  tolerance = 0.05
) {
  return requestJson<QuizEvaluation>("/api/training/quiz/evaluate", {
    method: "POST",
    body: {
      quiz_id: quizId,
      player: player || null,
      user_answer: userAnswer,
      tolerance
    }
  });
}

export async function getPlayers() {
  return requestJson<PlayerSummary[]>("/api/bankroll/players");
}

export async function getBankrollSummary() {
  return requestJson<BankrollSummary>("/api/bankroll/summary");
}

export async function updateBankroll(playerName: string, bankroll: number) {
  return requestJson<PlayerSummary>(`/api/bankroll/players/${encodeURIComponent(playerName)}`, {
    method: "PATCH",
    body: { bankroll }
  });
}

export async function createPlayer(name: string, bankroll: number) {
  return requestJson<PlayerSummary>("/api/bankroll/players", {
    method: "POST",
    body: { name, bankroll }
  });
}

export async function getGameModes() {
  return requestJson<GameMode[]>("/api/games/modes");
}

export async function createGameSession(payload: Record<string, JsonValue>) {
  return requestJson<GameSession>("/api/games/sessions", {
    method: "POST",
    body: payload
  });
}

export async function getSavedGameSessions(player?: string, state = "active") {
  const params = new URLSearchParams();
  if (player) params.set("player", player);
  if (state) params.set("state", state);
  const query = params.toString() ? `?${params.toString()}` : "";
  return requestJson<SavedGameSession[]>(`/api/games/sessions${query}`);
}

export async function getGameSession(sessionId: string) {
  return requestJson<GameSession>(`/api/games/sessions/${encodeURIComponent(sessionId)}`);
}

export async function pauseGameSession(sessionId: string) {
  return requestJson<GameSession>(`/api/games/sessions/${encodeURIComponent(sessionId)}/pause`, {
    method: "POST"
  });
}

export async function resumeGameSession(sessionId: string) {
  return requestJson<GameHandState>(`/api/games/sessions/${encodeURIComponent(sessionId)}/resume`, {
    method: "POST"
  });
}

export async function deleteGameSession(sessionId: string) {
  return requestJson<{ id: string; status: string }>(`/api/games/sessions/${encodeURIComponent(sessionId)}`, {
    method: "DELETE"
  });
}

export async function startGameHand(sessionId: string) {
  return requestJson<GameHandState>(
    `/api/games/sessions/${encodeURIComponent(sessionId)}/hand/start`,
    {
      method: "POST"
    }
  );
}

export async function getGameHandState(sessionId: string) {
  return requestJson<GameHandState>(`/api/games/sessions/${encodeURIComponent(sessionId)}/hand`);
}

export async function submitGameInput(
  sessionId: string,
  payload: { choice?: number; value?: JsonValue }
) {
  return requestJson<GameHandState>(
    `/api/games/sessions/${encodeURIComponent(sessionId)}/hand/input`,
    {
      method: "POST",
      body: payload
    }
  );
}

export async function getHandHistory(playerName: string, limit = 50) {
  const params = new URLSearchParams({ player: playerName, limit: String(limit) });
  return requestJson<HandHistory[]>(`/api/hands?${params.toString()}`);
}

export async function getTrainingDrill(player?: string, focus?: string) {
  const params = new URLSearchParams();
  if (player) params.set("player", player);
  if (focus) params.set("focus", focus);
  const query = params.toString() ? `?${params.toString()}` : "";
  return requestJson<TrainingDrill>(`/api/training/drill${query}`);
}

export async function evaluateTrainingDrill(drillId: string, userAnswer: JsonValue, player?: string) {
  return requestJson<DrillEvaluation>("/api/training/drill/evaluate", {
    method: "POST",
    body: {
      drill_id: drillId,
      player: player || null,
      user_answer: userAnswer
    }
  });
}

export async function getTrainingProgress(player?: string) {
  const params = new URLSearchParams();
  if (player) params.set("player", player);
  const query = params.toString() ? `?${params.toString()}` : "";
  return requestJson<TrainingProgress>(`/api/training/progress${query}`);
}

export async function getHandDetail(playerName: string, handNumber: number, sessionId?: string) {
  const params = new URLSearchParams();
  if (sessionId) params.set("session_id", sessionId);
  const query = params.toString() ? `?${params.toString()}` : "";
  return requestJson<HandHistory>(
    `/api/hands/${encodeURIComponent(playerName)}/${handNumber}${query}`
  );
}

export async function getChartData(
  metric: string,
  player?: string,
  options: { window?: number; includeAdjusted?: boolean } = {}
) {
  const params = new URLSearchParams();
  if (player) params.set("player", player);
  if (options.window && options.window > 1)
    params.set("window", String(options.window));
  if (options.includeAdjusted) params.set("include_adjusted", "true");
  const query = params.toString() ? `?${params.toString()}` : "";
  return requestJson<ChartRow[]>(
    `/api/charts/${encodeURIComponent(metric)}${query}`
  );
}

export async function getAnalyticsSessions(player: string, limit = 20) {
  const params = new URLSearchParams({ player, limit: String(limit) });
  return requestJson<Array<Record<string, JsonValue>>>(`/api/stats/sessions?${params.toString()}`);
}

export async function getFilteredHands(
  playerName: string,
  filters: {
    winner?: string;
    minPot?: number;
    sessionId?: string;
    gameType?: string;
    street?: string;
    decisionQuality?: string;
    weakness?: string;
    limit?: number;
  } = {}
) {
  const params = new URLSearchParams({ player: playerName, limit: String(filters.limit ?? 50) });
  if (filters.winner) params.set("winner", filters.winner);
  if (filters.minPot !== undefined) params.set("min_pot", String(filters.minPot));
  if (filters.sessionId) params.set("session_id", filters.sessionId);
  if (filters.gameType) params.set("game_type", filters.gameType);
  if (filters.street) params.set("street", filters.street);
  if (filters.decisionQuality) params.set("decision_quality", filters.decisionQuality);
  if (filters.weakness) params.set("weakness", filters.weakness);
  return requestJson<HandHistory[]>(`/api/hands/filter?${params.toString()}`);
}
// Analytics Helper

/**
 * Bayesian credible interval block attached to each rate stat.
 *
 * Produced by backend/app/services/bayes_stats.py - Beta-Binomial
 * posterior for rates (VPIP/PFR), nonparametric bootstrap for
 * continuous metrics (aggression factor). The UI renders this as
 * "29% (CI 22-37%, n=142)" instead of a bare "29%".
 */
export type BayesianStat = {
  value: number;
  ci_lower: number;
  ci_upper: number;
  sample_size: number;
  small_sample: boolean;
  // Only present for rate stats that have a target band.
  position_vs_target?: "low" | "high" | null;
  target_low?: number;
  target_high?: number;
};

export type AnalyticsReport = {
  basic_stats?: Record<string, JsonValue>;
  playing_style: {
    player_type: string;
    vpip: number;
    pfr: number;
    aggression_factor: number;
    // Bayesian fields (added in Track 2). Optional so legacy
    // backends without them still typecheck.
    vpip_ci?: BayesianStat;
    pfr_ci?: BayesianStat;
    aggression_factor_ci?: BayesianStat;
  };
  recommendations: string[];
  performance_metrics: Record<string, JsonValue>;
  strategy_score?: number;
  metric_options?: Record<string, string>;
};

/**
 * Variance + risk-of-ruin report from /api/analytics/variance.
 *
 * The realized vs EV cumulative line is the standard "luck graph"
 * from PokerTracker/Hold'em Manager. risk_of_ruin and kelly_fraction
 * are populated only when bankroll_bbs was provided in the request.
 */
export type VarianceReport = {
  player?: string | null;
  winrate: {
    mean_bb100: number;
    std_bb100: number;
    session_count: number;
    total_hands: number;
    risk_of_ruin: number | null;
    kelly_fraction: number | null;
    ci_lower: number;
    ci_upper: number;
    small_sample: boolean;
  } | null;
  rolling_bb100: Array<{
    label: string;
    value: number;
    window_hands: number;
  }>;
  ev_adjusted_lines: Array<{
    label: string;
    realized: number;
    ev: number | null;
  }>;
  all_in_luck: {
    luck_bb_total: number;
    sessions_with_data: number;
  } | null;
  session_count: number;
};

/**
 * ICM (Malmuth-Harville) tournament equity report.
 *
 * ``equities[i]`` is the expected dollar payout for seat i;
 * ``chip_shares[i]`` is the chip-EV-only baseline. The gap between
 * them tells you ICM pressure direction. ``risk_premium`` summarizes
 * how much equity edge you need over chip-EV breakeven for hero's
 * seat to take a coinflip-sized all-in.
 */
export type IcmEquities = {
  equities: number[];
  chip_shares: number[];
  total_chips: number;
  total_prize: number;
};

export type IcmRiskPremium = {
  chip_ev: number;
  icm_ev_at_50: number;
  hero_icm_equity_now: number;
  hero_icm_equity_win: number;
  hero_icm_equity_lose: number;
  risk_premium: number;
  bubble_factor: number;
};

export type IcmReport = {
  player?: string | null;
  icm: IcmEquities | null;
  hero_index?: number;
  risk_premium?: IcmRiskPremium | null;
  note?: string;
  error?: string;
};

export type ChartRow = {
  label: string;
  value: number;
  rolling_value?: number;
  window_hands?: number;
  realized_cumulative_bb?: number;
  ev_cumulative_bb?: number | null;
};

export type EvLeakGroup = {
  street: string;
  position: string;
  chosen_action: string;
  recommended_action: string;
  opponent_type: string;
  decision_count: number;
  total_ev_loss_bb: number;
  total_ev_loss_chips: number;
  average_ev_loss_bb: number;
  examples: Array<{
    hand_number?: number | null;
    session_id?: string | null;
    ev_loss_bb: number;
    quality?: string | null;
  }>;
};

export type EvLeakReport = {
  player?: string | null;
  priced_decision_count: number;
  mistake_count: number;
  total_ev_loss_bb: number;
  total_ev_loss_chips: number;
  worst_group?: EvLeakGroup | null;
  groups: EvLeakGroup[];
};

export async function getAnalyticsReport(playerName?: string) {
  const query = playerName ? `?player=${encodeURIComponent(playerName)}` : "";
  return requestJson<AnalyticsReport>(`/api/summary/report${query}`);
}

export async function getEvLeakReport(playerName?: string, limit = 20) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (playerName) params.set("player", playerName);
  return requestJson<EvLeakReport>(`/api/analytics/ev-leaks?${params.toString()}`);
}

export async function getVarianceReport(
  playerName?: string,
  bankrollBbs?: number
) {
  const params = new URLSearchParams();
  if (playerName) params.set("player", playerName);
  if (bankrollBbs !== undefined && bankrollBbs > 0)
    params.set("bankroll_bbs", String(bankrollBbs));
  const query = params.toString() ? `?${params.toString()}` : "";
  return requestJson<VarianceReport>(`/api/analytics/variance${query}`);
}

export async function getIcmReport(playerName?: string) {
  const query = playerName ? `?player=${encodeURIComponent(playerName)}` : "";
  return requestJson<IcmReport>(`/api/analytics/icm${query}`);
}

// Track 3: regret heatmap (EV loss grouped by structural spot)
export type RegretHeatmapCell = {
  street: string;
  position: number | null;
  spr_bucket: number;
  decision_count: number;
  total_ev_loss_bb: number;
  average_ev_loss_bb: number;
  example_keys: Array<{
    hand_number: number | null;
    decision_index: number;
    ev_loss_bb: number;
  }>;
};

export type RegretHeatmapReport = {
  player?: string | null;
  cells: RegretHeatmapCell[];
  max_loss_bb: number;
  totals: {
    decisions: number;
    ev_loss_bb: number;
  };
};

export async function getRegretHeatmap(playerName?: string, scanHands = 500) {
  const params = new URLSearchParams({ scan_hands: String(scanHands) });
  if (playerName) params.set("player", playerName);
  return requestJson<RegretHeatmapReport>(
    `/api/analytics/regret-heatmap?${params.toString()}`
  );
}

// Track 3: drill seeded from a specific decision.
export type DrillFromDecisionResponse = {
  drill: {
    drill_id: string;
    player?: string;
    focus_area?: string;
    scenario: Record<string, unknown>;
    quiz: Record<string, unknown>;
    from_decision?: { hand_number: number; decision_index: number };
  } | null;
  source?: { hand_number: number; decision_index: number };
  error?: string;
};

export async function postDrillFromDecision(payload: {
  player: string;
  hand_number: number;
  decision_index: number;
}) {
  return requestJson<DrillFromDecisionResponse>(
    "/api/training/drill/from-decision",
    {
      method: "POST",
      body: payload as unknown as JsonValue,
    }
  );
}

// ---------- Track 5: Range + equity types ----------

/** Class-string -> weight map. Used by the frontend RangeGrid. */
export type RangeClassMap = Record<string, number>;

export type PreflopChartsResponse = {
  charts: Record<string, RangeClassMap>;
  raw: Record<string, string>;
};

export async function getPreflopCharts() {
  return requestJson<PreflopChartsResponse>("/api/poker/preflop-charts");
}

/**
 * One player slot in a range-equity request. Exactly one of
 * ``hand``, ``range``, or ``preflop_chart`` must be set.
 */
export type RangeEquityPlayerSpec = {
  hand?: string[];
  range?: string;
  preflop_chart?: string;
};

export type RangeEquityResult = {
  equities: number[];
  players: Array<{
    label: string;
    equity: number;
    combo_count: number;
  }>;
  trials: number | null;
  board: string[];
};

export async function postRangeEquity(payload: {
  players: RangeEquityPlayerSpec[];
  board?: string[];
  trials?: number;
}) {
  return requestJson<RangeEquityResult>("/api/poker/range-equity", {
    method: "POST",
    body: payload as unknown as JsonValue,
  });
}

export async function getIcmForSpot(payload: {
  stacks: number[];
  payouts: number[];
  hero_index?: number;
}) {
  // requestJson auto-stringifies options.body (typed as JsonValue),
  // so we pass the object directly.
  return requestJson<IcmReport>(`/api/analytics/icm/spot`, {
    method: "POST",
    body: payload as unknown as JsonValue,
  });
}
