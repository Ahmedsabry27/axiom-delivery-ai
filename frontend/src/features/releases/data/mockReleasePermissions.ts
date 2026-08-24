export interface ReleasePermissions {
  canViewReadiness: boolean;
  canManageEvidence: boolean;
  canRequestReview: boolean;
  canApproveExceptions: boolean;
  canApproveRelease: boolean;
}

export function getMockReleasePermissions(releaseId: string): ReleasePermissions {
  return {
    canViewReadiness: true,
    canManageEvidence: releaseId === "rel-001",
    canRequestReview: true,
    canApproveExceptions: releaseId === "rel-001",
    canApproveRelease: releaseId === "rel-001",
  };
}
