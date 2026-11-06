import { env } from "~/env";
import type {
  ApplyResult,
  AssessmentUser,
  FilterOptions,
  MovieStatus,
  PreviewChanges,
  Showtime,
  ShowtimePage,
  ShowtimeStatus,
  Theater,
} from "~/types/assessment";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

type QueryValue = string | number | undefined | null;

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH";
  userId?: string | null;
  query?: Record<string, QueryValue>;
  json?: unknown;
  form?: FormData;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = new URL(path, env.NEXT_PUBLIC_API_URL);
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }

  const headers: Record<string, string> = {};
  // The selected session user identifies the caller on every request.
  if (options.userId) headers["X-User-Id"] = options.userId;
  if (options.json !== undefined) headers["Content-Type"] = "application/json";

  const response = await fetch(url, {
    method: options.method ?? "GET",
    headers,
    body: options.form ?? (options.json !== undefined ? JSON.stringify(options.json) : undefined),
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // non-JSON error body; keep the status text
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export interface ShowtimeQuery {
  theaterId?: string;
  q?: string;
  status?: string;
  movieStatus?: string;
  format?: string;
  language?: string;
  rating?: string;
  auditorium?: string;
  startDate?: string;
  endDate?: string;
  sort?: string;
  order?: "asc" | "desc";
  page?: number;
  pageSize?: number;
}

export const api = {
  listUsers: () => request<AssessmentUser[]>("/users"),

  myTheaters: (userId: string) => request<Theater[]>("/me/theaters", { userId }),

  listShowtimes: (userId: string, query: ShowtimeQuery) =>
    request<ShowtimePage>("/showtimes", {
      userId,
      query: {
        theater_id: query.theaterId,
        q: query.q,
        status: query.status,
        movie_status: query.movieStatus,
        format: query.format,
        language: query.language,
        rating: query.rating,
        auditorium: query.auditorium,
        start_date: query.startDate,
        end_date: query.endDate,
        sort: query.sort,
        order: query.order,
        page: query.page,
        page_size: query.pageSize,
      },
    }),

  filterOptions: (userId: string, theaterId?: string) =>
    request<FilterOptions>("/showtimes/filter-options", {
      userId,
      query: { theater_id: theaterId },
    }),

  updateShowtime: (
    userId: string,
    showtimeId: string,
    body: { movieStatus?: MovieStatus; status?: ShowtimeStatus },
  ) => request<Showtime>(`/showtimes/${showtimeId}`, { method: "PATCH", userId, json: body }),

  previewSchedule: (userId: string, theaterId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<PreviewChanges>(`/theaters/${theaterId}/schedule/preview`, {
      method: "POST",
      userId,
      form,
    });
  },

  applySchedule: (userId: string, theaterId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ApplyResult>(`/theaters/${theaterId}/schedule/apply`, {
      method: "POST",
      userId,
      form,
    });
  },

  archiveAll: (userId: string, theaterId: string) =>
    request<ApplyResult>(`/theaters/${theaterId}/schedule/archive-all`, {
      method: "POST",
      userId,
    }),
};
