export type MemoryOperation = 'recall_memory' | 'save_memory' | 'revise_belief';
export interface ChatSource {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  recorded_at: string;
}
export interface MemoryContext {
  conversationId: string;
  sources: readonly ChatSource[];
}
export interface MemoryConfig {
  baseUrl: string;
  token: string;
  allowRecall: boolean;
  allowWrite: boolean;
}
export interface MemoryAudit {
  operation: string;
  request_id: string | null;
  state: string;
  at: string;
  code?: string;
  delivery?: string;
  record_id?: string | null;
}
export interface MemoryReview {
  operation: string;
  destination: string;
  data: Record<string, unknown>;
}
export interface MemoryReply {
  ok: boolean;
  code?: string;
  operation: string;
  request_id: string | null;
  event_id?: string | null;
  delivery?: string;
  [key: string]: unknown;
}
export function validateBaseUrl(value: string): string;
export function createMemoryBridge(deps: {
  getConfig(): Promise<MemoryConfig | null>;
  digest(input: string): Promise<string>;
  newId(): string;
  now(): string;
  audit(event: MemoryAudit): Promise<void>;
  confirm(review: MemoryReview, signal?: AbortSignal): Promise<boolean>;
  transport(request: {
    url: string;
    method: string;
    token: string;
    body: string;
    idempotencyKey: string;
    requestId: string;
    signal?: AbortSignal;
    maxResponseBytes: number;
  }): Promise<{status: number; body: string}>;
}): {
  execute(
    operation: MemoryOperation,
    args: Record<string, unknown>,
    context?: MemoryContext,
    signal?: AbortSignal,
  ): Promise<MemoryReply>;
};
