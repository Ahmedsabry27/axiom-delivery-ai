import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

vi.mock("../hooks/useReleases", async () => {
  const [{ mockReleases }, { mockReleaseNotesMap }] = await Promise.all([
    import("../features/releases/data/mockReleases"),
    import("../features/releases/data/mockReleaseNotes"),
  ]);
  const releases = mockReleases.map((release) => ({
    ...release,
    releaseNotes: mockReleaseNotesMap[release.id],
  }));
  return {
    useReleases: () => ({ data: releases, isLoading: false, isError: false }),
    useRelease: (id) => {
      const data = releases.find((release) => release.id === id);
      return { data, isLoading: false, isError: !data };
    },
  };
});

afterEach(cleanup);
