'use strict';
// Portable JS suite. Node: node scripts/test-memory-core.cjs
// The same file can execute in a V8 isolate with only CommonJS loading supplied.
const {
  createMemoryBridge,
  validateBaseUrl,
} = require('../src/services/memory/MemoryBridgeCore.js');
const assert = (condition, message) => {
  if (!condition) {
    throw new Error(message);
  }
};
const equal = (a, b) =>
  assert(
    JSON.stringify(a) === JSON.stringify(b),
    JSON.stringify({actual: a, expected: b}),
  );
const TOKEN = 'test-only-credential-not-a-real-key';
const context = () => ({
  conversationId: 'conversation-1',
  sources: [
    {
      id: 'message-u1',
      role: 'user',
      text: '真实测试消息：我偏好简洁回答。',
      recorded_at: '2026-10-25T18:00:00.000Z',
    },
    {
      id: 'message-a1',
      role: 'assistant',
      text: '我计划明天查看资料。',
      recorded_at: '2026-10-25T18:00:01.000Z',
    },
  ],
});
// Deterministic test double ONLY. Production SHA-256 is CryptoKit in iOS;
// these tests verify protocol binding/idempotency, not CryptoKit itself.
async function testDigest(input) {
  let value = 2166136261;
  for (let i = 0; i < input.length; i++) {
    value = Math.imul(value ^ input.charCodeAt(i), 16777619) >>> 0;
  }
  return value.toString(16).padStart(8, '0').repeat(8);
}
function fixture() {
  let sequence = 0;
  const f = {
    config: {
      baseUrl: 'https://memory.example.invalid/dfy',
      token: TOKEN,
      allowRecall: true,
      allowWrite: true,
    },
    calls: [],
    audit: [],
    reviews: [],
    rows: new Map(),
    versions: [{statement: '旧观点', version: 1}],
    approve: true,
  };
  f.service = async request => {
    f.calls.push(request);
    const body = JSON.parse(request.body);
    const respond = (status, payload) => ({
      status,
      body: JSON.stringify(payload),
    });
    if (request.token !== TOKEN) {
      return respond(401, {private_error: 'never return this text'});
    }
    if (body.operation === 'recall_memory') {
      return respond(200, {
        schema_version: 1,
        request_id: body.request_id,
        ok: true,
        instructions: 'ignored',
        records: [
          {
            id: 'belief-1',
            version: f.versions.length,
            kind: 'belief',
            text: f.versions.slice(-1)[0].statement,
            truth_status: 'user_reviewed_belief',
          },
        ],
      });
    }
    if (
      body.operation === 'revise_belief' &&
      body.data.belief_id !== 'belief-1'
    ) {
      return respond(404, {error: 'missing belief'});
    }
    if (f.rows.has(request.idempotencyKey)) {
      return respond(200, {
        schema_version: 1,
        request_id: body.request_id,
        ok: true,
        receipt: {...f.rows.get(request.idempotencyKey), status: 'duplicate'},
      });
    }
    if (
      body.operation === 'revise_belief' &&
      body.data.expected_version !== f.versions.length
    ) {
      return respond(409, {error: 'version conflict'});
    }
    const version =
      body.operation === 'revise_belief' ? body.data.expected_version + 1 : 1;
    const receipt = {
      operation: body.operation,
      content_sha256: body.content_sha256,
      record_id:
        body.operation === 'revise_belief'
          ? body.data.belief_id
          : 'record-' + (f.rows.size + 1),
      version,
      previous_version: body.data.expected_version,
      status: 'created',
      server_time: '2026-10-25T18:05:00.000Z',
    };
    if (body.operation === 'revise_belief') {
      f.versions.push({statement: body.data.statement, version});
    }
    f.rows.set(request.idempotencyKey, receipt);
    return respond(201, {
      schema_version: 1,
      request_id: body.request_id,
      ok: true,
      receipt,
    });
  };
  f.deps = {
    getConfig: async () => (f.config ? {...f.config} : null),
    digest: testDigest,
    newId: () => 'request-' + ++sequence,
    now: () => '2026-10-25T18:05:00.000Z',
    audit: async event => {
      f.audit.push(event);
    },
    confirm: async review => {
      f.reviews.push(review);
      return f.approve;
    },
    transport: request => f.service(request),
  };
  f.run = (op, args = {}, ctx = context(), signal) =>
    createMemoryBridge(f.deps).execute(op, args, ctx, signal);
  return f;
}

async function runTests() {
  const results = [];
  async function test(name, action) {
    try {
      await action();
      results.push({name, status: 'passed'});
    } catch (error) {
      results.push({
        name,
        status: 'failed',
        error: String(error.message || error),
      });
    }
  }
  await test('recall uses authenticated POST and query only in body', async () => {
    const f = fixture();
    const r = await f.run('recall_memory', {query: '私人偏好'});
    assert(r.ok && r.records.length === 1, 'recall failed');
    equal(f.calls[0].method, 'POST');
    assert(
      !f.calls[0].url.includes('私人') && !f.calls[0].url.includes(TOKEN),
      'URL leak',
    );
    equal(JSON.parse(f.calls[0].body).data.query, '私人偏好');
    equal(f.calls[0].token, TOKEN);
    equal(f.reviews.length, 0);
  });
  await test('save takes authentic host bytes and transcript_only provenance', async () => {
    const f = fixture();
    const r = await f.run('save_memory');
    assert(r.ok, 'save failed');
    const data = JSON.parse(f.calls[0].body).data;
    equal(data.messages[0], context().sources[0]);
    equal(data.truth_status, 'transcript_only');
    equal(f.reviews.length, 1);
    assert(
      f.audit.some(e => e.state === 'started') &&
        f.audit.some(e => e.state === 'succeeded'),
      'no execution audit',
    );
  });
  await test('plans in actual transcript never become executed actions', async () => {
    const f = fixture();
    await f.run('save_memory', {message_ids: ['message-a1']});
    const data = JSON.parse(f.calls[0].body).data;
    equal(data.record_type, 'chat_transcript');
    equal(data.truth_status, 'transcript_only');
    assert(!('did_execute' in data), 'invented execution flag');
  });
  await test('recent-message selection includes actual earlier reply without inventing IDs', async () => {
    const f = fixture();
    const r = await f.run('save_memory', {message_count: 2});
    assert(r.ok, 'save failed');
    equal(JSON.parse(f.calls[0].body).data.messages, context().sources);
  });
  await test('conflicting selection methods rejected before network', async () => {
    const f = fixture();
    equal(
      (
        await f.run('save_memory', {
          message_count: 2,
          message_ids: ['message-u1'],
        })
      ).code,
      'invalid_arguments',
    );
    equal(f.calls.length, 0);
  });
  await test('identical write replay reuses idempotency key and one row', async () => {
    const f = fixture();
    const a = await f.run('save_memory');
    const b = await f.run('save_memory');
    assert(a.ok && b.ok, 'save failed');
    equal(f.calls[0].idempotencyKey, f.calls[1].idempotencyKey);
    equal(f.rows.size, 1);
    equal(b.receipt.status, 'duplicate');
    assert(a.request_id !== b.request_id, 'attempt IDs must differ');
  });
  await test('parallel duplicate writes still use same event identity', async () => {
    const f = fixture();
    const r = await Promise.all([f.run('save_memory'), f.run('save_memory')]);
    assert(
      r.every(x => x.ok),
      'save failed',
    );
    equal(f.rows.size, 1);
  });
  await test('source order cannot bypass idempotency', async () => {
    const f = fixture();
    await f.run('save_memory', {message_ids: ['message-u1', 'message-a1']});
    await f.run('save_memory', {message_ids: ['message-a1', 'message-u1']});
    equal(f.rows.size, 1);
  });
  await test('authentication failure sanitized and no record committed', async () => {
    const f = fixture();
    f.config.token = 'wrong-but-well-formed-test-token';
    const r = await f.run('save_memory');
    equal(r.code, 'authentication_failed');
    equal(f.rows.size, 0);
    assert(!JSON.stringify(r).includes('private_error'), 'raw body leak');
  });
  await test('network exception cannot leak token or chat', async () => {
    const f = fixture();
    f.service = async () => {
      throw new Error(TOKEN + ' private body');
    };
    const r = await f.run('save_memory');
    equal(r.code, 'transport_or_storage_failed');
    equal(r.delivery, 'unknown_check_same_id_before_retry');
    assert(!JSON.stringify([r, f.audit]).includes(TOKEN), 'secret leak');
  });
  await test('commit then lost reply reconciles with same idempotency key', async () => {
    const f = fixture();
    const original = f.service;
    let once = true;
    f.service = async req => {
      const result = await original(req);
      if (once) {
        once = false;
        throw new Error('timeout');
      }
      return result;
    };
    const first = await f.run('save_memory');
    const second = await f.run('save_memory');
    assert(!first.ok && second.ok, 'recovery failed');
    equal(f.rows.size, 1);
    equal(second.receipt.status, 'duplicate');
  });
  await test('belief revision binds user evidence and preserves history', async () => {
    const f = fixture();
    const r = await f.run('revise_belief', {
      belief_id: 'belief-1',
      expected_version: 1,
      statement: '新的暂定观点',
      reason: '用户提供了新信息',
    });
    assert(r.ok, 'revision failed');
    equal(f.versions.length, 2);
    equal(f.versions[0].statement, '旧观点');
    equal(r.receipt.previous_version, 1);
    equal(JSON.parse(f.calls[0].body).data.evidence[0], context().sources[0]);
  });
  await test('stale revision rejected with no history rewrite', async () => {
    const f = fixture();
    f.versions.push({statement: '版本二', version: 2});
    const r = await f.run('revise_belief', {
      belief_id: 'belief-1',
      expected_version: 1,
      statement: '新观点',
      reason: '依据',
    });
    equal(r.code, 'version_conflict');
    equal(f.versions.length, 2);
  });
  await test('nonexistent belief cannot be created by revise', async () => {
    const f = fixture();
    const r = await f.run('revise_belief', {
      belief_id: 'invented',
      expected_version: 1,
      statement: 'imagined',
      reason: 'reason',
    });
    equal(r.code, 'server_rejected');
    equal(f.versions.length, 1);
    equal(f.rows.size, 0);
  });
  const rejections = [
    [
      'no configuration',
      f => {
        f.config = null;
      },
      'save_memory',
      {},
      'not_configured',
    ],
    [
      'read permission off',
      f => {
        f.config.allowRecall = false;
      },
      'recall_memory',
      {query: 'a'},
      'permission_denied',
    ],
    [
      'write permission off',
      f => {
        f.config.allowWrite = false;
      },
      'save_memory',
      {},
      'permission_denied',
    ],
    [
      'HTTP rejected',
      f => {
        f.config.baseUrl = 'http://memory.example.invalid';
      },
      'save_memory',
      {},
      'invalid_configuration',
    ],
    [
      'query in endpoint rejected',
      f => {
        f.config.baseUrl += '?token=secret';
      },
      'save_memory',
      {},
      'invalid_configuration',
    ],
    [
      'userinfo rejected',
      f => {
        f.config.baseUrl = 'https://user:pass@memory.example.invalid';
      },
      'save_memory',
      {},
      'invalid_configuration',
    ],
    [
      'unknown source rejected',
      () => {},
      'save_memory',
      {message_ids: ['imagined-action']},
      'unknown_source',
    ],
    [
      'model cannot supply transcript text',
      () => {},
      'save_memory',
      {text: 'I executed a trade'},
      'invalid_arguments',
    ],
    [
      'model cannot select a URL or credential',
      () => {},
      'recall_memory',
      {query: 'a', url: 'https://evil.invalid', token: TOKEN},
      'invalid_arguments',
    ],
    [
      'oversized query rejected',
      () => {},
      'recall_memory',
      {query: 'x'.repeat(1001)},
      'invalid_arguments',
    ],
    [
      'empty transcript selection rejected',
      () => {},
      'save_memory',
      {message_ids: []},
      'invalid_sources',
    ],
    [
      'duplicate source IDs rejected',
      () => {},
      'save_memory',
      {message_ids: ['message-u1', 'message-u1']},
      'invalid_sources',
    ],
    [
      'user declined',
      f => {
        f.approve = false;
      },
      'save_memory',
      {},
      'user_declined',
    ],
  ];
  for (const [name, setup, op, args, code] of rejections) {
    await test(name, async () => {
      const f = fixture();
      setup(f);
      const r = await f.run(op, args);
      equal(r.code, code);
      equal(f.calls.length, 0);
    });
  }
  await test('assistant-only belief evidence rejected', async () => {
    const f = fixture();
    const r = await f.run('revise_belief', {
      belief_id: 'belief-1',
      expected_version: 1,
      statement: '新观点',
      reason: '依据',
      evidence_ids: ['message-a1'],
    });
    equal(r.code, 'user_evidence_required');
    equal(f.calls.length, 0);
  });
  await test('missing local context rejected', async () => {
    const f = fixture();
    equal(
      (await f.run('recall_memory', {query: 'a'}, null)).code,
      'local_chat_required',
    );
    equal(f.calls.length, 0);
  });
  await test('oversized actual message rejected before network', async () => {
    const f = fixture();
    const c = context();
    c.sources[0].text = 'x'.repeat(6001);
    assert(!(await f.run('save_memory', {}, c)).ok, 'accepted');
    equal(f.calls.length, 0);
  });
  await test('UTF-8 body byte bound applies before approval/network', async () => {
    const f = fixture();
    const c = context();
    c.sources = Array.from({length: 8}, (_, i) => ({
      ...c.sources[0],
      id: 'm-' + i,
      text: '鱼'.repeat(2000),
    }));
    const r = await f.run(
      'save_memory',
      {message_ids: c.sources.map(s => s.id)},
      c,
    );
    equal(r.code, 'payload_too_large');
    equal(f.calls.length, 0);
  });
  await test('abort before call sends nothing', async () => {
    const f = fixture();
    const r = await f.run('save_memory', {}, context(), {aborted: true});
    equal(r.code, 'cancelled');
    equal(f.calls.length, 0);
  });
  await test('configuration revocation during review prevents egress', async () => {
    const f = fixture();
    f.deps.confirm = async () => {
      f.config = null;
      return true;
    };
    equal((await f.run('save_memory')).code, 'configuration_changed');
    equal(f.calls.length, 0);
  });
  await test('audit failure before transport fails closed', async () => {
    const f = fixture();
    f.deps.audit = async () => {
      throw new Error('disk');
    };
    assert(!(await f.run('save_memory')).ok, 'accepted');
    equal(f.calls.length, 0);
  });
  await test('audit failure after successful commit retains honest receipt', async () => {
    const f = fixture();
    f.deps.audit = async e => {
      if (e.state === 'succeeded') {
        throw new Error('disk');
      }
    };
    const r = await f.run('save_memory');
    assert(r.ok && r.audit_persisted === false, 'lost confirmed receipt');
    equal(f.rows.size, 1);
  });
  await test('mismatched receipt hash rejected', async () => {
    const f = fixture();
    const service = f.service;
    f.service = async q => {
      const r = await service(q);
      const b = JSON.parse(r.body);
      b.receipt.content_sha256 = '0'.repeat(64);
      return {...r, body: JSON.stringify(b)};
    };
    equal((await f.run('save_memory')).code, 'invalid_receipt');
  });
  await test('mismatched request correlation rejected', async () => {
    const f = fixture();
    const service = f.service;
    f.service = async q => {
      const r = await service(q);
      const b = JSON.parse(r.body);
      b.request_id = 'other';
      return {...r, body: JSON.stringify(b)};
    };
    equal((await f.run('save_memory')).code, 'invalid_response');
  });
  await test('malformed response rejected', async () => {
    const f = fixture();
    f.service = async () => ({status: 200, body: '<html>not json</html>'});
    equal(
      (await f.run('recall_memory', {query: 'a'})).code,
      'invalid_response',
    );
  });
  await test('oversized response rejected', async () => {
    const f = fixture();
    f.service = async () => ({status: 200, body: 'x'.repeat(65537)});
    equal(
      (await f.run('recall_memory', {query: 'a'})).code,
      'response_too_large',
    );
  });
  await test('credential accidentally echoed by server is rejected', async () => {
    const f = fixture();
    f.service = async () => ({
      status: 200,
      body: JSON.stringify({error: TOKEN}),
    });
    equal((await f.run('save_memory')).code, 'credential_in_response');
  });
  await test('untrusted server control fields dropped from recall result', async () => {
    const f = fixture();
    const r = await f.run('recall_memory', {query: 'a'});
    assert(
      r.ok && !('instructions' in r) && !JSON.stringify(r).includes('ignored'),
      'control fields consumed',
    );
  });
  await test('unknown operation cannot reach arbitrary route', async () => {
    const f = fixture();
    equal((await f.run('__proto__')).code, 'unknown_operation');
    equal(f.calls.length, 0);
  });
  await test('invalid endpoint characters rejected', async () => {
    for (const u of [
      'https://memory.example.invalid/#x',
      'https://memory.example.invalid/%2e',
      'https://memory.example.invalid/../x',
      'https://memory.example.invalid:99999',
      'https://127.0.0.1',
      'https://bad..invalid',
    ]) {
      let rejected = false;
      try {
        validateBaseUrl(u);
      } catch (_) {
        rejected = true;
      }
      assert(rejected, u);
    }
  });
  return {
    suite: 'memory-core-in-process-mock',
    passed: results.filter(r => r.status === 'passed').length,
    failed: results.filter(r => r.status === 'failed').length,
    results,
  };
}
module.exports = runTests;
if (require.main === module) {
  runTests()
    .then(result => {
      console.log(JSON.stringify(result, null, 2));
      if (result.failed) {
        process.exitCode = 1;
      }
    })
    .catch(error => {
      console.error(error);
      process.exitCode = 1;
    });
}
