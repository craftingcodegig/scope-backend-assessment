"use client";

import type { MovieStatus, Showtime, ShowtimeStatus, Theater } from "~/types/assessment";

export type SortField =
  | "movieTitle"
  | "startTime"
  | "endTime"
  | "lastUpdated"
  | "theaterName"
  | "movieStatus";
export type SortOrder = "asc" | "desc";

interface ShowtimesTableProps {
  showtimes: Showtime[];
  theatersById: Record<string, Theater>;
  showTheaterColumn: boolean;
  isAdmin: boolean;
  isLoading: boolean;
  movieStatusOptions: MovieStatus[];
  statusOptions: readonly ShowtimeStatus[];
  searchQuery: string;
  onSearchChange: (query: string) => void;
  sortField: SortField;
  sortOrder: SortOrder;
  onSortChange: (field: SortField, order: SortOrder) => void;
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onMovieStatusChange?: (showtimeId: string, status: MovieStatus) => void;
  onStatusChange?: (showtimeId: string, status: ShowtimeStatus) => void;
}

export function ShowtimesTable({
  showtimes,
  theatersById,
  showTheaterColumn,
  isAdmin,
  isLoading,
  movieStatusOptions,
  statusOptions,
  searchQuery,
  onSearchChange,
  sortField,
  sortOrder,
  onSortChange,
  page,
  pageSize,
  total,
  onPageChange,
  onMovieStatusChange,
  onStatusChange,
}: ShowtimesTableProps) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const firstRow = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const lastRow = Math.min(page * pageSize, total);

  // Search, filtering and sorting happen on the server. This component only
  // reports the chosen search and sort upward and renders the page it is given.
  const handleSort = (field: SortField) => {
    if (sortField === field) {
      onSortChange(field, sortOrder === "asc" ? "desc" : "asc");
    } else {
      onSortChange(field, "asc");
    }
  };

  const formatDateTime = (date: string) => {
    return new Date(date).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <span className="ml-1 text-gray-500">↕</span>;
    return <span className="ml-1">{sortOrder === "asc" ? "↑" : "↓"}</span>;
  };

  const columnCount = 10 + (showTheaterColumn ? 1 : 0);

  return (
    <div className="w-full">
      <div className="mb-4">
        <input
          type="text"
          placeholder="Search by movie title..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="w-full rounded-lg border border-gray-600 bg-gray-800 px-4 py-2 text-white placeholder-gray-400 focus:border-purple-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
        />
      </div>

      <div
        className={`overflow-x-auto rounded-lg border border-gray-700 transition-opacity ${
          isLoading ? "opacity-60" : ""
        }`}
      >
        <table className="w-full text-left text-sm">
          <thead className="bg-gray-800 text-xs uppercase text-gray-400">
            <tr>
              {showTheaterColumn && (
                <th
                  className="cursor-pointer px-4 py-3 hover:bg-gray-700"
                  onClick={() => handleSort("theaterName")}
                >
                  Theater <SortIcon field="theaterName" />
                </th>
              )}
              <th
                className="cursor-pointer px-4 py-3 hover:bg-gray-700"
                onClick={() => handleSort("movieTitle")}
              >
                Movie Title <SortIcon field="movieTitle" />
              </th>
              <th
                className="cursor-pointer px-4 py-3 hover:bg-gray-700"
                onClick={() => handleSort("movieStatus")}
              >
                Movie Status <SortIcon field="movieStatus" />
              </th>
              <th className="px-4 py-3">Auditorium</th>
              <th
                className="cursor-pointer px-4 py-3 hover:bg-gray-700"
                onClick={() => handleSort("startTime")}
              >
                Start Time <SortIcon field="startTime" />
              </th>
              <th
                className="cursor-pointer px-4 py-3 hover:bg-gray-700"
                onClick={() => handleSort("endTime")}
              >
                End Time <SortIcon field="endTime" />
              </th>
              <th className="px-4 py-3">Language</th>
              <th className="px-4 py-3">Format</th>
              <th className="px-4 py-3">Rating</th>
              <th className="px-4 py-3">Status</th>
              <th
                className="cursor-pointer px-4 py-3 hover:bg-gray-700"
                onClick={() => handleSort("lastUpdated")}
              >
                Last Updated <SortIcon field="lastUpdated" />
              </th>
            </tr>
          </thead>
          <tbody>
            {showtimes.length === 0 ? (
              <tr>
                <td
                  colSpan={columnCount}
                  className="px-4 py-8 text-center text-gray-400"
                >
                  {isLoading ? "Loading showtimes..." : "No showtimes found"}
                </td>
              </tr>
            ) : (
              showtimes.map((showtime) => (
                <tr
                  key={showtime.id}
                  className={`border-b border-gray-700 hover:bg-gray-800 ${
                    showtime.status === "archived" ? "opacity-50" : ""
                  }`}
                >
                  {showTheaterColumn && (
                    <td className="px-4 py-3 text-gray-300">
                      {theatersById[showtime.theaterId]?.name ?? "Unknown"}
                    </td>
                  )}
                  <td className="px-4 py-3 font-medium text-white">
                    {showtime.movieTitle}
                  </td>
                  <td className="px-4 py-3 text-gray-300">
                    {isAdmin ? (
                      <select
                        value={showtime.movieStatus}
                        onChange={(e) =>
                          onMovieStatusChange?.(
                            showtime.id,
                            e.target.value as MovieStatus,
                          )
                        }
                        className="rounded border border-gray-600 bg-gray-800 px-2 py-1 text-xs text-white focus:border-purple-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
                      >
                        {movieStatusOptions.map((statusOption) => (
                          <option key={statusOption} value={statusOption}>
                            {statusOption}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span className="rounded-full bg-gray-700 px-2 py-1 text-xs text-gray-200">
                        {showtime.movieStatus}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-300">
                    {showtime.auditorium}
                  </td>
                  <td className="px-4 py-3 text-gray-300">
                    {formatDateTime(showtime.startTime)}
                  </td>
                  <td className="px-4 py-3 text-gray-300">
                    {formatDateTime(showtime.endTime)}
                  </td>
                  <td className="px-4 py-3 text-gray-300">
                    {showtime.language}
                  </td>
                  <td className="px-4 py-3 text-gray-300">
                    {showtime.format}
                  </td>
                  <td className="px-4 py-3 text-gray-300">
                    {showtime.rating}
                  </td>
                  <td className="px-4 py-3">
                    {isAdmin ? (
                      <select
                        value={showtime.status}
                        onChange={(e) =>
                          onStatusChange?.(
                            showtime.id,
                            e.target.value as ShowtimeStatus,
                          )
                        }
                        className="rounded border border-gray-600 bg-gray-800 px-2 py-1 text-xs text-white focus:border-purple-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
                      >
                        {statusOptions.map((statusOption) => (
                          <option key={statusOption} value={statusOption}>
                            {statusOption}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span
                        className={`rounded-full px-2 py-1 text-xs font-medium ${
                          showtime.status === "active"
                            ? "bg-green-900 text-green-300"
                            : showtime.status === "inactive"
                              ? "bg-amber-900 text-amber-300"
                              : "bg-gray-700 text-gray-400"
                        }`}
                      >
                        {showtime.status}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-300">
                    {formatDateTime(showtime.lastUpdated)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-gray-400">
        <span>
          Showing {firstRow}–{lastRow} of {total}
        </span>
        <div className="flex items-center gap-3">
          <button
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1 || isLoading}
            className="rounded-lg border border-gray-600 px-3 py-1 text-gray-300 transition hover:bg-gray-800 disabled:opacity-50"
          >
            Previous
          </button>
          <span>
            Page {page} of {pageCount}
          </span>
          <button
            onClick={() => onPageChange(page + 1)}
            disabled={page >= pageCount || isLoading}
            className="rounded-lg border border-gray-600 px-3 py-1 text-gray-300 transition hover:bg-gray-800 disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
