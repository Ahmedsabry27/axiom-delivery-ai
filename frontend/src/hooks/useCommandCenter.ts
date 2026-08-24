import { useQuery } from "@tanstack/react-query";
import { getDeliveryCommandCenterData } from "../services/delivery-command-center.service";
import { normalizeCommandCenterData } from "../services/delivery.repository";

export function useCommandCenter(contextId = "portfolio-all") {
  return useQuery({
    queryKey: ["delivery", "command-center", contextId],
    queryFn: ({ signal }) => getDeliveryCommandCenterData({ signal, contextId }),
    select: (data) => data == null ? data : normalizeCommandCenterData(data),
    staleTime: 30_000,
    retry: false,
  });
}
