import { useQuery } from "@tanstack/react-query";
import { getRelease, getReleases } from "../services/release.service";

export const useReleases = () => useQuery({
  queryKey: ["delivery", "releases"],
  queryFn: ({ signal }) => getReleases(signal),
  retry: false,
  staleTime: 30_000,
});

export const useRelease = (id: string) => useQuery({
  queryKey: ["delivery", "releases", id],
  queryFn: ({ signal }) => getRelease(id, signal),
  enabled: Boolean(id),
  retry: false,
  staleTime: 30_000,
});
