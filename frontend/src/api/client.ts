const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

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

export type HandHistory = {
  hand_number?: number;
  started_at?: string;
  hero_hole_cards?: string[];
  board?: string[];
  pot_total?: number;
  winners?: string[];
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
    recommended_action?: string;
    quality?: string;
  }>;
  meta?: Record<string, JsonValue>;
  board_by_street?: Record<string, string[]>;
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
};

export type GameHandState = {
  session_id: string;
  status: string;
  state: LiveGameState;
  pending_input?: PendingInput | null;
  input_error?: string | null;
  last_hand?: HandHistory | null;
  error?: string | null;
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
    throw new Error(message || `Request failed: ${response.status}`);
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
  tolerance = 0.05
) {
  return requestJson<QuizEvaluation>("/api/training/quiz/evaluate", {
    method: "POST",
    body: {
      correct_answer: correctAnswer,
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

export async function getHandDetail(playerName: string, handNumber: number) {
  return requestJson<HandHistory>(
    `/api/hands/${encodeURIComponent(playerName)}/${handNumber}`
  );
}
