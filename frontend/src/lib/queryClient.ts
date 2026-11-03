import { QueryClient } from "@tanstack/react-query";
import { isApiError } from "./apiClient";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 2 * 60 * 1000,
      gcTime: 5 * 60 * 1000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error: Error) => {
        if (isApiError(error) && (error.status === 401 || error.status === 403)) return false;
        return failureCount < 1;
      },
    },
  },
});
