"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { assessmentData } from "~/data/assessment-data";
import { api } from "~/lib/api";
import { useDebounce } from "~/lib/hooks/useDebounce";
import { useMockSession } from "~/lib/mock-session";
import type {
  FilterOptions,
  MovieStatus,
  PreviewChanges,
  Showtime,
  Theater,
} from "~/types/assessment";
import { FileUpload } from "./_components/FileUpload";
import { FilterBar } from "./_components/FilterBar";
import { PreviewModal } from "./_components/PreviewModal";
import {
  ShowtimesTable,
  type SortField,
  type SortOrder,
} from "./_components/ShowtimesTable";

const emptyPreview: PreviewChanges = {
  adds: [],
  updates: [],
  archives: [],
};

const emptyFilters = {
  status: "all" as "active" | "inactive" | "archived" | "all",
  format: "",
  language: "",
  rating: "",
  auditorium: "",
  movieStatus: "",
  startDate: "",
  endDate: "",
};

const emptyFilterOptions: FilterOptions = {
  formats: [],
  languages: [],
  ratings: [],
  auditoriums: [],
  movieStatuses: [],
};

// Table sort fields mapped to the API sort parameter names.
const sortParam: Record<SortField, string> = {
  movieTitle: "movie_title",
  startTime: "start_time",
  endTime: "end_time",
  lastUpdated: "last_updated",
  theaterName: "theater_name",
  movieStatus: "movie_status",
};

const PAGE_SIZE = 50;

export default function Home() {
  const { users, user, userId, setUserId, signOut } = useMockSession();
  const [accessibleTheaters, setAccessibleTheaters] = useState<Theater[]>([]);
  const [selectedTheaterId, setSelectedTheaterId] = useState<string>("all");
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  const [previewData, setPreviewData] = useState<PreviewChanges>(emptyPreview);

  const [filters, setFilters] = useState(emptyFilters);
  const [filterOptions, setFilterOptions] =
    useState<FilterOptions>(emptyFilterOptions);
  const [searchQuery, setSearchQuery] = useState("");
  const debouncedSearch = useDebounce(searchQuery, 300);
  const [sortField, setSortField] = useState<SortField>("startTime");
  const [sortOrder, setSortOrder] = useState<SortOrder>("asc");

  const [showtimes, setShowtimes] = useState<Showtime[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const latestRequest = useRef(0);

  const isAdmin = user?.role === "admin";
  const theaterParam = selectedTheaterId === "all" ? undefined : selectedTheaterId;

  // The backend only returns theaters the user belongs to.
  useEffect(() => {
    if (!userId) {
      setAccessibleTheaters([]);
      return;
    }
    api
      .myTheaters(userId)
      .then(setAccessibleTheaters)
      .catch(() => setAccessibleTheaters([]));
  }, [userId]);

  const theatersById = useMemo(() => {
    return accessibleTheaters.reduce(
      (acc, theater) => {
        acc[theater.id] = theater;
        return acc;
      },
      {} as Record<string, Theater>,
    );
  }, [accessibleTheaters]);

  useEffect(() => {
    if (
      selectedTheaterId !== "all" &&
      !accessibleTheaters.some((theater) => theater.id === selectedTheaterId)
    ) {
      setSelectedTheaterId("all");
    }
  }, [accessibleTheaters, selectedTheaterId]);

  const loadFilterOptions = useCallback(() => {
    if (!userId) {
      setFilterOptions(emptyFilterOptions);
      return;
    }
    api
      .filterOptions(userId, theaterParam)
      .then(setFilterOptions)
      .catch(() => setFilterOptions(emptyFilterOptions));
  }, [userId, theaterParam]);

  useEffect(loadFilterOptions, [loadFilterOptions]);

  const loadShowtimes = useCallback(async () => {
    if (!userId) {
      setShowtimes([]);
      setTotal(0);
      return;
    }
    const requestId = ++latestRequest.current;
    setIsLoading(true);
    setError(null);
    try {
      const result = await api.listShowtimes(userId, {
        theaterId: theaterParam,
        q: debouncedSearch,
        status: filters.status === "all" ? undefined : filters.status,
        movieStatus: filters.movieStatus,
        format: filters.format,
        language: filters.language,
        rating: filters.rating,
        auditorium: filters.auditorium,
        startDate: filters.startDate,
        endDate: filters.endDate,
        sort: sortParam[sortField],
        order: sortOrder,
        page: 1,
        pageSize: PAGE_SIZE,
      });
      if (requestId !== latestRequest.current) return; // a newer request won
      setShowtimes(result.items);
      setTotal(result.total);
    } catch (err) {
      if (requestId !== latestRequest.current) return;
      setError(err instanceof Error ? err.message : "Failed to load showtimes");
      setShowtimes([]);
      setTotal(0);
    } finally {
      if (requestId === latestRequest.current) setIsLoading(false);
    }
  }, [userId, theaterParam, debouncedSearch, filters, sortField, sortOrder]);

  useEffect(() => {
    void loadShowtimes();
  }, [loadShowtimes]);

  const previewForTheater = useMemo(() => {
    if (selectedTheaterId === "all") return emptyPreview;
    return (
      assessmentData.previewChangesByTheater[selectedTheaterId] ?? emptyPreview
    );
  }, [selectedTheaterId]);

  const handleFileSelect = (_content: string) => {
    setPreviewData(previewForTheater);
    setIsPreviewOpen(true);
  };

  const handleConfirmChanges = () => {
    setIsPreviewOpen(false);
  };

  const handleClearSchedule = () => {
    if (selectedTheaterId === "all") {
      alert("Select a single theater before clearing the schedule.");
      return;
    }
    if (
      confirm(
        "Are you sure you want to archive all showtimes for this theater?",
      )
    ) {
      setShowtimes((current) =>
        current.map((showtime) =>
          showtime.theaterId === selectedTheaterId
            ? { ...showtime, status: "archived" }
            : showtime,
        ),
      );
    }
  };

  const handleMovieStatusChange = (showtimeId: string, status: MovieStatus) => {
    setShowtimes((current) =>
      current.map((showtime) =>
        showtime.id === showtimeId
          ? { ...showtime, movieStatus: status }
          : showtime,
      ),
    );
  };

  const handleSortChange = (field: SortField, order: SortOrder) => {
    setSortField(field);
    setSortOrder(order);
  };

  const statusOptions = ["active", "inactive", "archived"] as const;

  return (
    <main className="min-h-screen bg-gradient-to-b from-[#1a0b2e] to-[#0f0720]">
      <div className="container mx-auto px-4 py-8">
        <div className="mb-8 flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h1 className="mb-2 text-4xl font-bold text-white">
              Theater Showtimes Manager
            </h1>
            <p className="text-gray-400">
              Upload partner CSV files to manage showtimes
            </p>
          </div>

          <div className="w-full max-w-md rounded-lg border border-gray-700 bg-gray-900 p-4">
            <p className="text-xs uppercase text-gray-500">Session</p>
            <div className="mt-2 flex flex-col gap-3">
              <select
                value={userId ?? ""}
                onChange={(e) => setUserId(e.target.value)}
                className="w-full rounded-lg border border-gray-600 bg-gray-800 px-3 py-2 text-sm text-white focus:border-purple-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
              >
                <option value="" disabled>
                  Select a user
                </option>
                {users.map((candidate) => (
                  <option key={candidate.id} value={candidate.id}>
                    {candidate.name} ({candidate.role})
                  </option>
                ))}
              </select>
              {user ? (
                <div className="text-sm text-gray-400">
                  <div className="flex items-center justify-between">
                    <span>{user.email}</span>
                    <span
                      className={`rounded-full px-2 py-1 text-xs font-medium ${
                        isAdmin
                          ? "bg-purple-900 text-purple-200"
                          : "bg-gray-700 text-gray-200"
                      }`}
                    >
                      {user.role}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-gray-500">
                    Theaters: {user.theaterIds.length || 0}
                  </div>
                </div>
              ) : (
                <div className="text-sm text-gray-500">
                  No user selected.
                </div>
              )}
              <button
                onClick={signOut}
                className="rounded-lg border border-gray-600 px-3 py-2 text-xs font-semibold text-gray-300 transition hover:bg-gray-800"
              >
                Clear selection
              </button>
            </div>
          </div>
        </div>

        <div className="mb-6 flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <label className="text-xs font-semibold uppercase text-gray-400">
              Theater Scope
            </label>
            <select
              value={selectedTheaterId}
              onChange={(e) => setSelectedTheaterId(e.target.value)}
              disabled={!accessibleTheaters.length}
              className="rounded-lg border border-gray-600 bg-gray-800 px-3 py-2 text-sm text-white focus:border-purple-500 focus:outline-none focus:ring-2 focus:ring-purple-500 disabled:opacity-50"
            >
              <option value="all">All accessible theaters</option>
              {accessibleTheaters.map((theater) => (
                <option key={theater.id} value={theater.id}>
                  {theater.name}
                </option>
              ))}
            </select>
          </div>

          <FileUpload
            onFileSelect={handleFileSelect}
            disabled={
              !isAdmin ||
              selectedTheaterId === "all" ||
              accessibleTheaters.length === 0
            }
          />

          <button
            onClick={handleClearSchedule}
            disabled={
              !isAdmin ||
              selectedTheaterId === "all" ||
              accessibleTheaters.length === 0
            }
            className="rounded-lg border border-red-600 px-6 py-3 font-semibold text-red-400 transition hover:bg-red-950 disabled:opacity-50"
          >
            Clear Schedule
          </button>

          <div className="ml-auto text-sm text-gray-400">
            {total > 0 && (
              <>
                {total} showtimes
                {selectedTheaterId === "all" ? " across theaters" : ""}
              </>
            )}
          </div>
        </div>

        {!isAdmin && (
          <div className="mb-6 rounded-lg border border-gray-700 bg-gray-900 p-4 text-sm text-gray-400">
            You are in read-only mode. Admin users can upload CSVs and update
            movie status.
          </div>
        )}

        {error && (
          <div className="mb-6 rounded-lg border border-red-800 bg-red-950 p-4 text-sm text-red-300">
            {error}
          </div>
        )}

        {accessibleTheaters.length === 0 ? (
          <div className="rounded-lg border border-gray-700 bg-gray-900 p-8 text-center text-gray-400">
            This user does not belong to any theaters yet.
          </div>
        ) : (
          <>
            <FilterBar
              status={filters.status}
              format={filters.format}
              language={filters.language}
              rating={filters.rating}
              auditorium={filters.auditorium}
              movieStatus={filters.movieStatus}
              startDate={filters.startDate}
              endDate={filters.endDate}
              onFilterChange={setFilters}
              availableFormats={filterOptions.formats}
              availableLanguages={filterOptions.languages}
              availableRatings={filterOptions.ratings}
              availableAuditoriums={filterOptions.auditoriums}
              availableMovieStatuses={filterOptions.movieStatuses}
            />

            <div className="rounded-lg border border-gray-700 bg-gray-900 p-6">
              <ShowtimesTable
                showtimes={showtimes}
                theatersById={theatersById}
                showTheaterColumn={selectedTheaterId === "all"}
                isAdmin={!!isAdmin}
                isLoading={isLoading}
                movieStatusOptions={assessmentData.movieStatusOptions}
                statusOptions={statusOptions}
                searchQuery={searchQuery}
                onSearchChange={setSearchQuery}
                sortField={sortField}
                sortOrder={sortOrder}
                onSortChange={handleSortChange}
                onMovieStatusChange={
                  isAdmin ? handleMovieStatusChange : undefined
                }
                onStatusChange={
                  isAdmin
                    ? (showtimeId, status) => {
                        setShowtimes((current) =>
                          current.map((showtime) =>
                            showtime.id === showtimeId
                              ? { ...showtime, status }
                              : showtime,
                          ),
                        );
                      }
                    : undefined
                }
              />
            </div>
          </>
        )}

        <PreviewModal
          isOpen={isPreviewOpen}
          onClose={() => setIsPreviewOpen(false)}
          onConfirm={handleConfirmChanges}
          changes={previewData}
          isApplying={false}
        />
      </div>
    </main>
  );
}
