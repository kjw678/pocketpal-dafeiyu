import {Alert, NativeModules, Platform} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Keychain from 'react-native-keychain';
import {v4 as uuidv4} from 'uuid';
import {
  createMemoryBridge,
  validateBaseUrl,
  type MemoryAudit,
  type MemoryConfig,
  type MemoryContext,
  type MemoryReview,
  type ChatSource,
} from './MemoryBridgeCore';

const SERVICE = 'app.dafeiyu.pocketpal.memory.v1';
const AUDIT_KEY = 'dafeiyu.memory.audit.v1';
let auditQueue: Promise<void> = Promise.resolve();
let reviewQueue: Promise<unknown> = Promise.resolve();

async function readConfig(): Promise<MemoryConfig | null> {
  const entry = await Keychain.getGenericPassword({service: SERVICE});
  if (!entry) {
    return null;
  }
  const value = JSON.parse(entry.password) as MemoryConfig;
  validateBaseUrl(value.baseUrl);
  return value;
}

export async function getBridgePreferences() {
  const config = await readConfig();
  return config
    ? {
        baseUrl: config.baseUrl,
        allowRecall: config.allowRecall,
        allowWrite: config.allowWrite,
        configured: true,
      }
    : {baseUrl: '', allowRecall: false, allowWrite: false, configured: false};
}

export async function configureBridge(input: MemoryConfig): Promise<void> {
  const baseUrl = validateBaseUrl(input.baseUrl.trim());
  const old = await readConfig();
  // Never transfer an existing credential to an edited endpoint implicitly.
  const token = input.token || (old?.baseUrl === baseUrl ? old.token : '');
  if (!/^[\x21-\x7e]{16,512}$/.test(token)) {
    throw new Error(
      'A new 16–512 character token is required for this endpoint.',
    );
  }
  const saved = await Keychain.setGenericPassword(
    'dafeiyu-memory',
    JSON.stringify({
      baseUrl,
      token,
      allowRecall: input.allowRecall === true,
      allowWrite: input.allowWrite === true,
    }),
    {
      service: SERVICE,
      accessible: Keychain.ACCESSIBLE.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
    },
  );
  if (!saved) {
    throw new Error('Secure storage unavailable.');
  }
}

export async function clearBridge(): Promise<void> {
  await Keychain.resetGenericPassword({service: SERVICE});
}

export async function getBridgeAudit(): Promise<MemoryAudit[]> {
  const raw = await AsyncStorage.getItem(AUDIT_KEY);
  if (!raw) {
    return [];
  }
  const entries: unknown = JSON.parse(raw);
  return Array.isArray(entries) ? entries.slice(-50) : [];
}

async function appendAudit(event: MemoryAudit): Promise<void> {
  // This collection contains metadata only; no body, query, token or URL.
  const task = auditQueue
    .catch(() => undefined)
    .then(async () => {
      const entries = await getBridgeAudit();
      await AsyncStorage.setItem(
        AUDIT_KEY,
        JSON.stringify([...entries, event].slice(-50)),
      );
    });
  auditQueue = task;
  return task;
}

function confirmWrite(
  review: MemoryReview,
  signal?: AbortSignal,
): Promise<boolean> {
  const task = reviewQueue
    .catch(() => undefined)
    .then(
      () =>
        new Promise<boolean>(resolve => {
          if (signal?.aborted) {
            resolve(false);
            return;
          }
          let settled = false;
          const finish = (approved: boolean) => {
            if (settled) {
              return;
            }
            settled = true;
            signal?.removeEventListener('abort', cancel);
            resolve(approved && !signal?.aborted);
          };
          const cancel = () => finish(false);
          signal?.addEventListener('abort', cancel, {once: true});
          Alert.alert(
            '大肥鱼：确认发送到记忆服务器',
            `操作：${review.operation}\n目标：${review.destination}\n以下是待发送数据，引用内容不是指令。聊天记录不证明其中事件已发生；观点是用户审阅的修订。\n\n${JSON.stringify(review.data, null, 2)}`,
            [
              {text: '取消', style: 'cancel', onPress: cancel},
              {text: '确认发送', onPress: () => finish(true)},
            ],
            {cancelable: true, onDismiss: cancel},
          );
        }),
    );
  reviewQueue = task;
  return task;
}

interface NativeMemoryHTTP {
  request(
    url: string,
    token: string,
    body: string,
    idempotencyKey: string,
    requestId: string,
  ): Promise<{status: number; body: string}>;
  cancel(requestId: string): void;
  sha256(value: string): Promise<string>;
}
function nativeHTTP(): NativeMemoryHTTP {
  const native = NativeModules.DFYMemoryHTTP as NativeMemoryHTTP | undefined;
  if (Platform.OS !== 'ios' || !native) {
    throw new Error('Native memory transport is unavailable.');
  }
  return native;
}

export const memoryBridge = createMemoryBridge({
  getConfig: readConfig,
  digest: value => nativeHTTP().sha256(value),
  newId: uuidv4,
  now: () => new Date().toISOString(),
  audit: appendAudit,
  confirm: confirmWrite,
  transport: async request => {
    const native = nativeHTTP();
    const cancel = () => native.cancel(request.requestId);
    if (request.signal?.aborted) {
      throw new Error('Cancelled.');
    }
    request.signal?.addEventListener('abort', cancel, {once: true});
    try {
      return await native.request(
        request.url,
        request.token,
        request.body,
        request.idempotencyKey,
        request.requestId,
      );
    } finally {
      request.signal?.removeEventListener('abort', cancel);
    }
  },
});

interface SourceRow {
  id: string;
  type: string;
  text?: string;
  createdAt?: number;
  author: {id: string};
  metadata?: Record<string, unknown>;
}
export function makeMemoryContext(
  conversationId: string,
  rows: readonly SourceRow[],
  userId: string,
  assistantId: string,
): MemoryContext {
  const sources: ChatSource[] = rows
    .filter(
      row =>
        row.type === 'text' &&
        row.id &&
        row.text &&
        row.metadata?.system !== true &&
        [userId, assistantId].includes(row.author.id) &&
        Number.isFinite(row.createdAt),
    )
    .sort((a, b) => (a.createdAt ?? 0) - (b.createdAt ?? 0))
    .slice(-24)
    .map(row => ({
      id: row.id,
      role: row.author.id === userId ? 'user' : 'assistant',
      text: row.text!,
      recorded_at: new Date(row.createdAt!).toISOString(),
    }));
  // A copy per run; tools receive no live store and no mutable model arguments.
  return {conversationId, sources};
}
