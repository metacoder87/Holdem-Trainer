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

export type SummaryResponse = {
  player: {
    name: string;
    skill_level?: string | null;
    last_played?: string | null;
  };
  live_metrics: Metric[];
  training_tracks: TrainingTrack[];
  focus_queue: string[];
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

export type WinningHand = {
  player: string;
  rank?: string | null;
  cards?: string[];
  hole_cards?: string[];
};

export type HandHistory = {
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
    outs?: Record<string, JsonValue>;
    analysis?: Record<string, JsonValue>;
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
    } | null;
    decision_count?: number;
  } | null;
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
  }>;
  blinds?: {
    small_blind?: number;
    big_blind?: number;
    blind_level?: number | null;
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
    const message = await response.text();
    throw new ApiError(
      response.status,
      message || `Request failed: ${response.status}`,
      message
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

export async function getGameSession(sessionId: string) {
  return requestJson<GameSession>(`/api/games/sessions/${encodeURIComponent(sessionId)}`);
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

export async function runDemoHand(sessionId: string) {
  return requestJson<GameHandState>(`/api/games/sessions/${encodeURIComponent(sessionId)}/demo-hand`, {
    method: "POST"
  });
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

export async function getHandDetail(playerName: string, handNumber: number) {
  return requestJson<HandHistory>(
    `/api/hands/${encodeURIComponent(playerName)}/${handNumber}`
  );
}

export async function getChartData(metric: string, player?: string) {
  const params = new URLSearchParams();
  if (player) params.set("player", player);
  const query = params.toString() ? `?${params.toString()}` : "";
  return requestJson<Array<{ label: string; value: number }>>(
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
export type AnalyticsReport = {
  basic_stats?: Record<string, JsonValue>;
  playing_style: {
    player_type: string;
    vpip: number;
    pfr: number;
    aggression_factor: number;
  };
  recommendations: string[];
  performance_metrics: Record<string, JsonValue>;
  strategy_score?: number;
  metric_options?: Record<string, string>;
};

export async function getAnalyticsReport(playerName?: string) {
  const query = playerName ? `?player=${encodeURIComponent(playerName)}` : "";
  return requestJson<AnalyticsReport>(`/api/summary/report${query}`);
}
