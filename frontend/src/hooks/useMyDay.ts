import { useQuery } from "@tanstack/react-query";
import { getMyDayData } from "../services/delivery-command-center.service";
import { normalizeMyDayData } from "../services/delivery.repository";

export function useMyDay() {
  return useQuery({ queryKey:["delivery","my-day"], queryFn:({signal})=>getMyDayData({signal}), select:normalizeMyDayData, staleTime:30_000, retry:false });
}
