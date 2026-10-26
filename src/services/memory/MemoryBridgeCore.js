/* MIT. Dependency-free protocol/policy core; native I/O is injected by the host. */
'use strict';

const OPERATIONS = Object.freeze({
  recall_memory: '/v1/memory/recall',
  save_memory: '/v1/memory/save',
  revise_belief: '/v1/memory/revise',
});
const MAX_BODY = 24000;
const MAX_RESPONSE = 65536;

class BridgeError extends Error {
  constructor(code) {
    super(code);
    this.code = code;
  }
}
const fail = code => {
  throw new BridgeError(code);
};
const object = value =>
  value !== null && typeof value === 'object' && !Array.isArray(value);
const text = (value, max, code = 'invalid_arguments') => {
  if (
    typeof value !== 'string' ||
    !value.trim() ||
    value.length > max ||
    /[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(value)
  ) {
    fail(code);
  }
  return value;
};
const id = value => {
  text(value, 128);
  if (value.trim() !== value || !/^[A-Za-z0-9][A-Za-z0-9_.:-]*$/.test(value)) {
    fail('invalid_arguments');
  }
  return value;
};
const bytes = value => {
  try {
    return encodeURIComponent(value).replace(/%[A-F\d]{2}/g, 'x').length;
  } catch (_) {
    return fail('invalid_encoding');
  }
};
function validateBaseUrl(value) {
  text(value, 256, 'invalid_configuration');
  if (value.trim() !== value) {
    fail('invalid_configuration');
  }
  // Deliberately narrow: HTTPS DNS host, optional port/path; no userinfo, query,
  // fragment, escapes or dot segments. No model-provided destination is used.
  const m =
    /^https:\/\/([a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?)(?::([0-9]{1,5}))?(\/[a-zA-Z0-9/_-]*)?$/.exec(
      value,
    );
  if (
    !m ||
    !m[1].includes('.') ||
    m[1].includes('..') ||
    /^[\d.]+$/.test(m[1]) ||
    m[1]
      .split('.')
      .some(
        label => !/^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$/.test(label),
      ) ||
    (m[2] && (+m[2] < 1 || +m[2] > 65535))
  ) {
    fail('invalid_configuration');
  }
  return value.replace(/\/+$/, '');
}
function exactKeys(args, allowed) {
  if (!object(args) || Object.keys(args).some(k => !allowed.includes(k))) {
    fail('invalid_arguments');
  }
}
function sourceSelection(raw, context, requireEvidence) {
  const sources = context.sources;
  let requested = raw;
  if (requested === undefined) {
    const latest = sources.filter(s => s.role === 'user').slice(-1);
    requested = latest.map(s => s.id);
  }
  if (
    !Array.isArray(requested) ||
    requested.length < 1 ||
    requested.length > 8 ||
    new Set(requested).size !== requested.length
  ) {
    fail('invalid_sources');
  }
  const selected = requested.map(key => {
    id(key);
    const found = sources.find(s => s.id === key);
    if (!found || !['user', 'assistant'].includes(found.role)) {
      fail('unknown_source');
    }
    return {
      id: id(found.id),
      role: found.role,
      text: text(found.text, 6000),
      recorded_at: text(found.recorded_at, 40),
    };
  });
  if (requireEvidence && !selected.some(s => s.role === 'user')) {
    fail('user_evidence_required');
  }
  return selected.sort(
    (a, b) =>
      a.recorded_at.localeCompare(b.recorded_at) || a.id.localeCompare(b.id),
  );
}
function makeData(operation, args, context) {
  if (!object(context) || !Array.isArray(context.sources)) {
    fail('local_chat_required');
  }
  const provenance = {
    conversation_id: id(context.conversationId),
    origin: 'dafeiyu_local_chat',
  };
  if (operation === 'recall_memory') {
    exactKeys(args, ['query', 'limit']);
    const limit = args.limit === undefined ? 4 : args.limit;
    if (!Number.isInteger(limit) || limit < 1 || limit > 8) {
      fail('invalid_arguments');
    }
    return {query: text(args.query, 1000), limit};
  }
  if (operation === 'save_memory') {
    exactKeys(args, ['message_ids', 'message_count']);
    let selectedIds = args.message_ids;
    if (args.message_count !== undefined) {
      if (
        selectedIds !== undefined ||
        !Number.isInteger(args.message_count) ||
        args.message_count < 1 ||
        args.message_count > 8 ||
        args.message_count > context.sources.length
      ) {
        fail('invalid_arguments');
      }
      selectedIds = context.sources.slice(-args.message_count).map(s => s.id);
    }
    return {
      record_type: 'chat_transcript',
      truth_status: 'transcript_only',
      provenance,
      messages: sourceSelection(selectedIds, context, false),
    };
  }
  exactKeys(args, [
    'belief_id',
    'expected_version',
    'statement',
    'reason',
    'evidence_ids',
  ]);
  if (
    !Number.isInteger(args.expected_version) ||
    args.expected_version < 1 ||
    args.expected_version > 1000000
  ) {
    fail('invalid_arguments');
  }
  return {
    record_type: 'belief_revision',
    truth_status: 'user_reviewed_belief',
    provenance,
    belief_id: id(args.belief_id),
    expected_version: args.expected_version,
    statement: text(args.statement, 3000),
    reason: text(args.reason, 1500),
    // These are authentic transcript sources, NOT proof the claims are true.
    evidence: sourceSelection(args.evidence_ids, context, true),
    preserve_history: true,
  };
}
function validateReply(operation, value, requestId, digest, data) {
  if (
    !object(value) ||
    value.schema_version !== 1 ||
    value.request_id !== requestId ||
    value.ok !== true
  ) {
    fail('invalid_response');
  }
  if (operation === 'recall_memory') {
    if (!Array.isArray(value.records) || value.records.length > data.limit) {
      fail('invalid_response');
    }
    // Rebuild a bounded data-only response. Never consume server instructions,
    // URLs, annotations, executable objects or authentication/policy fields.
    return {
      records: value.records.map(r => {
        if (!object(r) || !Number.isInteger(r.version) || r.version < 1) {
          fail('invalid_response');
        }
        return {
          id: id(r.id),
          version: r.version,
          kind: text(r.kind, 48),
          text: text(r.text, 6000),
          truth_status: text(r.truth_status, 64),
        };
      }),
    };
  }
  const r = value.receipt;
  if (
    !object(r) ||
    r.operation !== operation ||
    r.content_sha256 !== digest ||
    !Number.isInteger(r.version) ||
    r.version < 1 ||
    !['created', 'duplicate'].includes(r.status)
  ) {
    fail('invalid_receipt');
  }
  if (
    operation === 'revise_belief' &&
    (r.record_id !== data.belief_id ||
      r.version !== data.expected_version + 1 ||
      r.previous_version !== data.expected_version)
  ) {
    fail('invalid_receipt');
  }
  const serverTime = text(r.server_time, 40);
  if (
    !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z$/.test(serverTime) ||
    !Number.isFinite(Date.parse(serverTime))
  ) {
    fail('invalid_receipt');
  }
  return {
    receipt: {
      record_id: id(r.record_id),
      operation,
      version: r.version,
      previous_version:
        operation === 'revise_belief' ? r.previous_version : null,
      status: r.status,
      server_time: serverTime,
      content_sha256: digest,
    },
  };
}
function createMemoryBridge(deps) {
  return {
    async execute(operation, args, context, signal) {
      let requestId = null;
      let eventId = null;
      let attempted = false;
      let write = false;
      try {
        if (!Object.prototype.hasOwnProperty.call(OPERATIONS, operation)) {
          fail('unknown_operation');
        }
        if (signal && signal.aborted) {
          fail('cancelled');
        }
        const config = await deps.getConfig();
        if (!config) {
          fail('not_configured');
        }
        const baseUrl = validateBaseUrl(config.baseUrl);
        if (
          typeof config.token !== 'string' ||
          !/^[\x21-\x7e]{16,512}$/.test(config.token)
        ) {
          fail('invalid_configuration');
        }
        write = operation !== 'recall_memory';
        if (write ? config.allowWrite !== true : config.allowRecall !== true) {
          fail('permission_denied');
        }
        const data = makeData(operation, args, context);
        const canonical = JSON.stringify({schema_version: 1, operation, data});
        if (bytes(canonical) > MAX_BODY - 1000) {
          fail('payload_too_large');
        }
        const digest = await deps.digest(canonical);
        if (typeof digest !== 'string' || !/^[a-f0-9]{64}$/.test(digest)) {
          fail('digest_unavailable');
        }
        requestId = id(deps.newId());
        const key = write ? 'dfy-v1-' + digest : '';
        eventId = key || null;
        const body = JSON.stringify({
          schema_version: 1,
          request_id: requestId,
          operation,
          content_sha256: digest,
          idempotency_key: key || null,
          data,
        });
        if (
          write &&
          !(await deps.confirm({operation, destination: baseUrl, data}, signal))
        ) {
          fail('user_declined');
        }
        if (signal && signal.aborted) {
          fail('cancelled');
        }
        const currentConfig = await deps.getConfig();
        if (
          !currentConfig ||
          JSON.stringify(currentConfig) !== JSON.stringify(config)
        ) {
          fail('configuration_changed');
        }
        // The start receipt must persist before any private data leaves.
        await deps.audit({
          operation,
          request_id: requestId,
          state: 'started',
          at: deps.now(),
        });
        attempted = true;
        const reply = await deps.transport({
          url: baseUrl + OPERATIONS[operation],
          method: 'POST',
          token: config.token,
          body,
          idempotencyKey: key,
          requestId,
          signal,
          maxResponseBytes: MAX_RESPONSE,
        });
        if (!object(reply) || !Number.isInteger(reply.status)) {
          fail('invalid_response');
        }
        if (reply.status === 401 || reply.status === 403) {
          fail('authentication_failed');
        }
        if (reply.status === 409) {
          fail('version_conflict');
        }
        if (reply.status === 429) {
          fail('rate_limited');
        }
        if (reply.status !== 200 && reply.status !== 201) {
          fail('server_rejected');
        }
        if (
          typeof reply.body !== 'string' ||
          bytes(reply.body) > MAX_RESPONSE
        ) {
          fail('response_too_large');
        }
        if (reply.body.includes(config.token)) {
          fail('credential_in_response');
        }
        let decoded;
        try {
          decoded = JSON.parse(reply.body);
        } catch (_) {
          fail('invalid_response');
        }
        const result = validateReply(
          operation,
          decoded,
          requestId,
          digest,
          data,
        );
        let auditPersisted = true;
        try {
          await deps.audit({
            operation,
            request_id: requestId,
            state: 'succeeded',
            at: deps.now(),
            record_id: result.receipt ? result.receipt.record_id : null,
          });
        } catch (_) {
          auditPersisted = false;
        }
        return {
          ok: true,
          operation,
          request_id: requestId,
          event_id: eventId,
          audit_persisted: auditPersisted,
          ...result,
        };
      } catch (error) {
        // Never propagate raw exceptions, response bodies, URLs or headers.
        const code =
          error instanceof BridgeError
            ? error.code
            : signal && signal.aborted
              ? 'cancelled'
              : 'transport_or_storage_failed';
        const delivery =
          attempted && write
            ? 'unknown_check_same_id_before_retry'
            : 'not_confirmed';
        try {
          await deps.audit({
            operation: Object.prototype.hasOwnProperty.call(
              OPERATIONS,
              operation,
            )
              ? operation
              : 'unknown',
            request_id: requestId,
            state: 'failed',
            code,
            delivery,
            at: deps.now(),
          });
        } catch (_) {
          /* AgentRunner still records this sanitized result. */
        }
        return {
          ok: false,
          operation: Object.prototype.hasOwnProperty.call(OPERATIONS, operation)
            ? operation
            : 'unknown',
          request_id: requestId,
          event_id: eventId,
          code,
          delivery,
        };
      }
    },
  };
}
module.exports = {createMemoryBridge, validateBaseUrl};
