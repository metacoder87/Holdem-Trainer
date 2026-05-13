const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const API_BASE = API_URL;
export const WS_URL = (import.meta.env.VITE_WS_URL as string | undefined)
  || API_URL.replace(/^http/, "ws");

export function buildHandExportUrl(
  playerName: string,
  options: { fmt?: "json" | "jsonl"; limit?: number; won?: boolean } = {}
): string {
  const params = new URLSearchParams({ player: playerName });
  params.set("fmt", options.fmt ?? "jsonl");
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  if (options.won !== undefined) params.set("won", String(options.won));
  return `${API_URL}/api/hands/export?${params.toString()}`;
}

type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

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
  id: string | null;
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
  type: string;
  question: string;
  correct_answer: number;
  correct_percentage?: number;
  explanation: string;
  difficulty: number;
  acceptable_range?: [number, number];
};

export type QuizEvaluation = {
  correct: boolean;
  user_answer: number;
  correct_answer: number;
  difference?: number;
  feedback: string;
  performance_stats?: {
    total_quizzes: number;
    correct_answers: number;
    streak: number;
    best_streak: number;
  };
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
  config: Record<string, JsonValue>;
};

export type HandAction = {
  player: string;
  action: string;
  amount: number;
  pot_before: number;
  pot_after: number;
  betting_round: string;
  did_raise?: boolean;
};

export type DecisionPoint = {
  betting_round?: string;
  chosen_action?: string;
  recommended_action?: string;
  quality?: string;
  equity?: number;
  required_equity?: number;
  hand_strength?: number;
  hand_potential?: number;
  pot_total?: number;
  to_call?: number;
  hero_hole_cards?: string[];
  board?: string[];
  analysis?: {
    grade_method?: string;
    action_quality?: string;
    recommended_action?: string;
    hand_strength?: number;
    adjusted_strength?: number;
    position_factor?: number;
    pot_odds?: number;
    pot_odds_percentage?: number;
    hand_equity?: number;
    hand_equity_percentage?: number;
    reasoning?: string | string[];
    [key: string]: unknown;
  };
  opponent?: { name?: string | null; type?: string };
};

export type CoachNotes = {
  hero_won: boolean;
  headline: string;
  hand_grade: string;
  worst_decision: {
    betting_round?: string;
    chosen_action?: string;
    recommended_action?: string;
    quality?: string;
    equity?: number;
    required_equity?: number;
    line?: string;
  } | null;
  takeaway: string | null;
  decision_count: number;
};

export type HandHistory = {
  hand_number?: number;
  started_at?: string;
  hero_hole_cards?: string[];
  board?: string[];
  pot_total?: number;
  winners?: string[];
  actions?: HandAction[];
  decision_points?: DecisionPoint[];
  meta?: Record<string, JsonValue>;
  board_by_street?: Record<string, string[]>;
  coach_notes?: CoachNotes | null;
};

export type ReplayStreet = {
  name: "preflop" | "flop" | "turn" | "river";
  board: string[];
  actions: HandAction[];
  decisions: DecisionPoint[];
};

export type HandReplay = {
  hand_number?: number;
  started_at?: string;
  ended_at?: string;
  hero_hole_cards: string[];
  winners: string[];
  pot_total: number;
  meta: Record<string, JsonValue>;
  streets: ReplayStreet[];
  summary: {
    small_blind?: number;
    big_blind?: number;
    ante?: number;
    blind_level?: number;
    game_type?: string;
    limit_type?: string;
    hero_won?: boolean;
  };
};

export type AnalyticsTrendPoint = {
  started_at?: string;
  value: number;
};

export type AnalyticsSummary = {
  player: { name?: string; skill_level?: string | null } | null;
  metrics: Record<string, number>;
  session_count: number;
  trends: Record<string, AnalyticsTrendPoint[]>;
};

export type Leak = {
  id: string;
  title: string;
  severity: "low" | "medium" | "high";
  fix: string;
};

export type LeaksResponse = {
  player: { name?: string; skill_level?: string | null } | null;
  leaks: Leak[];
  recommended_topics?: string[];
};

export type PendingInput = {
  kind: "menu" | "number" | "yes_no";
  prompt: string;
  options?: string[] | null;
  min_value?: number | null;
  max_value?: number | null;
  integer_only?: boolean | null;
};

export type HudOpponent = {
  name: string;
  hands: number;
  vpip: number;
  pfr: number;
  aggression_factor: number;
  type: string;
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
  hud?: {
    opponents: HudOpponent[];
  };
};

export type TournamentResult = {
  result: "won" | "lost" | "forfeit";
  final_bankroll: number;
  chip_stack_at_end: number;
};

export type GameHandState = {
  session_id: string;
  status: string;
  state: LiveGameState;
  pending_input?: PendingInput | null;
  input_error?: string | null;
  last_hand?: HandHistory | null;
  error?: string | null;
  tournament_result?: TournamentResult | null;
};

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: JsonValue;
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
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
    const message = await response.text();
    throw new ApiError(response.status, message || `Request failed: ${response.status}`);
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

export async function getTrainingQuiz(quizType: string, potSize?: number, betToCall?: number) {
  const params = new URLSearchParams({ quiz_type: quizType });
  if (potSize !== undefined) params.set("pot_size", String(potSize));
  if (betToCall !== undefined) params.set("bet_to_call", String(betToCall));
  return requestJson<TrainingQuiz>(`/api/training/quiz?${params.toString()}`);
}

export async function evaluateTrainingQuiz(
  correctAnswer: number,
  userAnswer: number,
  tolerance = 0.05,
  options: { playerName?: string; quizType?: string } = {}
) {
  return requestJson<QuizEvaluation>("/api/training/quiz/evaluate", {
    method: "POST",
    body: {
      correct_answer: correctAnswer,
      user_answer: userAnswer,
      tolerance,
      player_name: options.playerName ?? null,
      quiz_type: options.quizType ?? null
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

export async function getHandDetail(playerName: string, handNumber: number) {
  return requestJson<HandHistory>(
    `/api/hands/${encodeURIComponent(playerName)}/${handNumber}`
  );
}

export async function getHandReplay(playerName: string, handNumber: number) {
  return requestJson<HandReplay>(
    `/api/hands/${encodeURIComponent(playerName)}/${handNumber}/replay`
  );
}

export async function getAnalyticsSummary(player?: string) {
  const query = player ? `?player=${encodeURIComponent(player)}` : "";
  return requestJson<AnalyticsSummary>(`/api/analytics/summary${query}`);
}

export async function getAnalyticsLeaks(player?: string) {
  const query = player ? `?player=${encodeURIComponent(player)}` : "";
  return requestJson<LeaksResponse>(`/api/analytics/leaks${query}`);
}

export type CareerMetrics = {
  total_hands: number;
  total_sessions: number;
  avg_vpip: number;
  avg_pfr: number;
  avg_aggression_factor: number;
  avg_winrate: number;
  total_profit: number;
  best_session_profit: number;
  worst_session_profit: number;
};

export type CareerMilestone = {
  type: string;
  achieved_at: string;
  total_hands: number;
};

export type CareerResponse = {
  player: { name?: string; skill_level?: string | null } | null;
  career_metrics: CareerMetrics | null;
  session_count: number;
  trends?: Record<string, { direction: string; change: number; recent_avg?: number; previous_avg?: number }>;
  milestones: CareerMilestone[];
  skill_progression?: Record<string, unknown>;
};

export async function getCareer(player?: string) {
  const query = player ? `?player=${encodeURIComponent(player)}` : "";
  return requestJson<CareerResponse>(`/api/analytics/career${query}`);
}

export type EvLeakSample = {
  hand_number?: number;
  betting_round?: string;
  chosen_action?: string;
  ev_loss_chips: number;
  ev_loss_bb: number;
  equity?: number;
  required_equity?: number;
};

export type EvSummary = {
  total_chips: number;
  total_bb: number;
  graded_decisions: number;
  avg_loss_bb_per_decision: number;
  top_leaks: EvLeakSample[];
};

export type EvSummaryResponse = {
  player: { name?: string; skill_level?: string | null } | null;
  ev: EvSummary;
};

export async function getEvSummary(player?: string) {
  const query = player ? `?player=${encodeURIComponent(player)}` : "";
  return requestJson<EvSummaryResponse>(`/api/analytics/ev${query}`);
}

export type SessionReportResponse = {
  player?: { name?: string; skill_level?: string | null } | null;
  session_index?: number;
  session?: Record<string, unknown> | null;
  report?: Record<string, unknown> | null;
};

export async function getSessionReport(player?: string, sessionIndex?: number) {
  const params = new URLSearchParams();
  if (player) params.set("player", player);
  const path =
    sessionIndex === undefined
      ? "/api/analytics/sessions/latest"
      : `/api/analytics/sessions/${sessionIndex}`;
  const qs = params.toString();
  return requestJson<SessionReportResponse>(`${path}${qs ? `?${qs}` : ""}`);
}

export type FocusArea = { id: string; label: string };

export type Drill = {
  drill_id: string;
  kind: string;
  scenario: string;
  options: string[];
  correct_action: string;
  context: Record<string, JsonValue>;
  difficulty: number;
  focus_area: string;
};

export type DrillGrade = {
  drill_id: string;
  kind: string;
  correct: boolean;
  user_answer: string;
  correct_action: string;
  feedback: string;
  persisted?: boolean;
  persist_error?: string;
};

export async function getDrillFocusAreas() {
  return requestJson<FocusArea[]>("/api/training/drills/focus-areas");
}

export async function createDrill(payload: {
  player_name?: string;
  focus_area?: string;
  difficulty?: number;
}) {
  return requestJson<Drill>("/api/training/drills", {
    method: "POST",
    body: payload as Record<string, JsonValue>
  });
}

export async function gradeDrill(payload: {
  drill_id: string;
  kind: string;
  correct_action: string;
  user_answer: string;
  player_name?: string;
  focus_area?: string;
}) {
  return requestJson<DrillGrade>("/api/training/drills/answer", {
    method: "POST",
    body: payload
  });
}
