export type UserRole = "admin" | "viewer";
export type ShowtimeStatus = "active" | "inactive" | "archived";
export type MovieStatus = "approved" | "draft" | "flagged" | "needs-review";

export const movieStatusOptions: MovieStatus[] = [
  "approved",
  "draft",
  "flagged",
  "needs-review",
];

export interface Theater {
  id: string;
  name: string;
  location: string;
  timezone: string;
}

export interface AssessmentUser {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  theaterIds: string[];
}

export interface Showtime {
  id: string;
  theaterId: string;
  movieTitle: string;
  movieStatus: MovieStatus;
  auditorium: string;
  startTime: string;
  endTime: string;
  language: string;
  format: string;
  rating: string;
  lastUpdated: string;
  status: ShowtimeStatus;
}

export interface FieldDiff {
  field: string;
  oldValue: string;
  newValue: string;
}

export interface ShowtimeUpdate {
  id: string;
  movieTitle: string;
  startTime: string;
  endTime: string;
  diffs: FieldDiff[];
}

export interface ShowtimeAdd {
  rowKey: string;
  movieTitle: string;
  auditorium: string;
  startTime: string;
  endTime: string;
  language: string;
  format: string;
  rating: string;
}

export interface ShowtimeArchive {
  id: string;
  movieTitle: string;
  startTime: string;
  endTime: string;
}

export interface ColumnMapping {
  source: string;
  target: string;
}

export interface MatchSuggestion {
  rowKey: string;
  showtimeId: string;
  csvTitle: string;
  existingTitle: string;
  confidence: number;
  reason: string;
}

export interface ReviewWarning {
  movieTitle: string;
  startTime: string;
  message: string;
}

/** What the AI upload assistant contributed to a preview. */
export interface AssistantInfo {
  enabled: boolean;
  /** Which model provider answered: "gemini" or "anthropic". */
  provider: string | null;
  columnMapping: ColumnMapping[];
  suggestions: MatchSuggestion[];
  summary: string | null;
  warnings: ReviewWarning[];
}

export interface PreviewChanges {
  adds: ShowtimeAdd[];
  updates: ShowtimeUpdate[];
  archives: ShowtimeArchive[];
  assistant: AssistantInfo;
}

/** A suggestion the admin accepted; sent back when applying. */
export interface AcceptedMatch {
  rowKey: string;
  showtimeId: string;
}

export interface ShowtimePage {
  items: Showtime[];
  total: number;
  page: number;
  pageSize: number;
}

export interface FilterOptions {
  formats: string[];
  languages: string[];
  ratings: string[];
  auditoriums: string[];
  movieStatuses: string[];
}

export interface ApplyResult {
  added: number;
  updated: number;
  archived: number;
}
