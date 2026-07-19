#!/usr/bin/env node
/**
 * Authenticated Catalyst admin-API transport via the logged-in CLI session
 * (CAT-002/#18).
 *
 * Why this exists: `catalyst token:generate` needs a device-code flow whose
 * verification must be completed by the same Zoho account as the CLI login,
 * which is awkward on a headless VM. The CLI's own credential is already on
 * disk after `catalyst login`, and the CLI exposes the same authenticated
 * client it uses for `ds:*` commands — so provisioning reuses it. No token
 * is stored, printed, or committed (ADR-001).
 *
 * For CI/CD the CLI honours CATALYST_TOKEN / ZC_TOKEN env vars instead, so
 * the same script works in a pipeline without a login (see #84).
 *
 * Usage:
 *   node catalyst_api.js GET  /baas/v1/project/<id>/table
 *   node catalyst_api.js POST /baas/v1/project/<id>/table '{"table_name":"X"}'
 *
 * Prints one JSON line: {"status":<http>,"body":<parsed>} or {"error":"..."}.
 * Must be run from a Catalyst app directory (one containing catalyst.json).
 */
'use strict';

const { execSync } = require('node:child_process');
const path = require('node:path');

function cliLibDir() {
  // resolve the globally-installed CLI regardless of npm prefix
  const bin = execSync('readlink -f "$(command -v catalyst)"', {
    encoding: 'utf8',
    shell: '/bin/bash',
  }).trim();
  // <prefix>/lib/node_modules/zcatalyst-cli/lib/bin/catalyst.js -> .../lib/
  return path.resolve(path.dirname(bin), '..');
}

(async () => {
  try {
    const lib = cliLibDir();
    const auth = require(path.join(lib, 'command_needs/auth.js')).default;
    const Api = require(path.join(lib, 'internal/api')).default;

    const [method, apiPath, body] = process.argv.slice(2);
    if (!method || !apiPath) {
      throw new Error('usage: catalyst_api.js <METHOD> <PATH> [JSON_BODY]');
    }

    auth([]); // loads the CLI credential (login session, or CATALYST_TOKEN)
    const opts = body ? { body: JSON.parse(body) } : undefined;
    const res = await new Api({ printError: false }).fire(method, apiPath, opts);
    console.log(JSON.stringify({ status: res.statusCode, body: res.body }));
  } catch (e) {
    console.log(JSON.stringify({ error: e.message }));
    process.exit(1);
  }
})();
