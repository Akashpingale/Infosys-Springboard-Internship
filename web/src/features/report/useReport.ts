import {
  useIsMutating,
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from '@tanstack/react-query';

import { API_URL, ApiError, request, type ApiErrorBody } from '@/api/client';
import { queryKeys } from '@/api/queries';
import type { components } from '@/api/types.gen';
import type { RunDetail } from '@/features/run/useRun';
import { MESSAGES } from '@/lib/format';

export type ReportDocument = components['schemas']['ReportDocument'];
export type ReportSection = components['schemas']['ReportSection'];
export type ReportBlock = NonNullable<ReportSection['blocks']>[number];
export type BibEntry = components['schemas']['BibEntry'];
export type ReportStatus = components['schemas']['RunReportStatus'];
export type FileFormat = 'pdf' | 'markdown';

export interface FileReply {
  blob: Blob;
  fileName: string | null;
}

export interface GenerateReportInput {
  force?: boolean;
  narrative?: boolean;
  signal?: AbortSignal;
}

const SLUG_MAX = 40;
const SLUG_FALLBACK = 'idea';
const DATE = /^[0-9]{4}-[0-9]{2}-[0-9]{2}/;
const EXTENSIONS: Record<FileFormat | 'json', string> = { pdf: 'pdf', markdown: 'md', json: 'json' };
const FILE_NAME = /filename="([^"]+)"/;

export function reportKey(runId: string) {
  return ['report', runId] as const;
}

export function reportPath(runId: string, suffix = ''): string {
  return `/api/runs/${encodeURIComponent(runId)}/report${suffix}`;
}

export function generateKey(runId: string) {
  return ['report', runId, 'generate'] as const;
}

export function canHaveReport(run: RunDetail | undefined): boolean {
  return Boolean(run && run.state === 'done' && run.result && run.result.status !== 'failed');
}

export function fileSlug(title: string): string {
  const ascii = title.normalize('NFKD').replace(/[^\u0000-\u007f]/g, '').toLowerCase();
  const slug = ascii.replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, SLUG_MAX).replace(/-+$/g, '');
  return slug || SLUG_FALLBACK;
}

export function reportFileName(document: ReportDocument, format: FileFormat | 'json'): string {
  const date = DATE.exec(document.meta.generated_at)?.[0] ?? new Date().toISOString().slice(0, 10);
  return `startup-validation_${fileSlug(document.meta.idea_title)}_${date}.${EXTENSIONS[format]}`;
}

export function useReport(runId: string | undefined, enabled: boolean): UseQueryResult<ReportDocument | null> {
  return useQuery({
    queryKey: reportKey(runId ?? 'unknown'),
    queryFn: async () => {
      try {
        return await request<ReportDocument>(reportPath(runId ?? ''));
      } catch (cause) {
        if (cause instanceof ApiError && cause.code === 'report_not_found') {
          return null;
        }
        throw cause;
      }
    },
    enabled: Boolean(runId) && enabled,
    staleTime: 0,
  });
}

export function useGenerateReport(runId: string | undefined) {
  const queryClient = useQueryClient();
  const id = runId ?? '';
  return useMutation({
    mutationKey: generateKey(id),
    mutationFn: ({ force = false, narrative = true, signal }: GenerateReportInput = {}) =>
      request<ReportDocument>(reportPath(id), { method: 'POST', body: { force, narrative }, signal }),
    onSuccess: (document) => {
      queryClient.setQueryData(reportKey(id), document);
      void queryClient.invalidateQueries({ queryKey: queryKeys.run(id), exact: true });
    },
  });
}

export function useIsGenerating(runId: string | undefined): boolean {
  return useIsMutating({ mutationKey: generateKey(runId ?? '') }) > 0;
}

export function useDeleteReport(runId: string | undefined) {
  const queryClient = useQueryClient();
  const id = runId ?? '';
  return useMutation({
    mutationFn: () => request<void>(reportPath(id), { method: 'DELETE' }),
    onSuccess: () => {
      queryClient.setQueryData(reportKey(id), null);
      void queryClient.invalidateQueries({ queryKey: queryKeys.run(id), exact: true });
    },
  });
}

export async function downloadReport(runId: string, format: FileFormat): Promise<FileReply> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${reportPath(runId, `/${format}`)}`);
  } catch {
    throw new ApiError(MESSAGES.backendDown, 0, 'backend_unreachable');
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as Partial<ApiErrorBody> | null;
    throw new ApiError(
      body?.error?.message ?? `The server answered with an error (HTTP ${response.status}).`,
      response.status,
      body?.error?.code ?? 'unexpected_error',
    );
  }
  const match = FILE_NAME.exec(response.headers.get('Content-Disposition') ?? '');
  return { blob: await response.blob(), fileName: match?.[1] ?? null };
}
