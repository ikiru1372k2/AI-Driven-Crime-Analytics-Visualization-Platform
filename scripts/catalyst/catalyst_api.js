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
const fs = require('node:fs');

// Locate the globally-installed zcatalyst-cli's lib/ directory cross-platform.
// The original `readlink -f "$(command -v catalyst)"` ran under
// {shell:'/bin/bash'}, which native Windows Node cannot spawn (ENOENT), so the
// resolution below avoids bash and POSIX-only tools entirely.
function cliLibDir() {
  const candidates = [];
  // 1) Node's module resolver against the global search paths (cross-platform).
  try {
    const pkg = require.resolve('zcatalyst-cli/package.json', {
      paths: require('node:module').globalPaths,
    });
    candidates.push(path.join(path.dirname(pkg), 'lib'));
  } catch { /* fall through */ }
  // 2) npm's global root (uses the default shell — cmd.exe on Windows, not bash).
  try {
    const root = execSync('npm root -g', { encoding: 'utf8' }).trim();
    candidates.push(path.join(root, 'zcatalyst-cli', 'lib'));
  } catch { /* fall through */ }
  // 3) Walk up from the resolved CLI binary (platform-aware lookup, no bash).
  try {
    const finder = process.platform === 'win32' ? 'where catalyst' : 'command -v catalyst';
    const raw = execSync(finder, { encoding: 'utf8' }).trim().split(/\r?\n/)[0];
    candidates.push(path.resolve(path.dirname(fs.realpathSync(raw)), '..'));
  } catch { /* fall through */ }
  for (const dir of candidates) {
    if (fs.existsSync(path.join(dir, 'internal'))) return dir;
  }
  throw new Error(
    'could not locate the zcatalyst-cli lib directory — is the Catalyst CLI ' +
    'installed globally (npm i -g zcatalyst-cli)?'
  );
}

(async () => {
  try {
    const lib = cliLibDir();
    const auth = require(path.join(lib, 'command_needs/auth.js')).default;
    const Api = require(path.join(lib, 'internal/api')).default;

    const [method, apiPath, body] = process.argv.slice(2);
    if (!method || !apiPath) {
      throw new Error('usage: catalyst_api.js <METHOD> <PATH> [JSON_BODY | -]');
    }

    // A large row-insert body can exceed the OS command-line length limit
    // (Windows WinError 206), so "-" means "read the JSON body from stdin".
    const bodyRaw = body === '-' ? fs.readFileSync(0, 'utf8') : body;

    auth([]); // loads the CLI credential (login session, or CATALYST_TOKEN)
    const opts = bodyRaw ? { body: JSON.parse(bodyRaw) } : undefined;
    const res = await new Api({ printError: false }).fire(method, apiPath, opts);
    console.log(JSON.stringify({ status: res.statusCode, body: res.body }));
  } catch (e) {
    console.log(JSON.stringify({ error: e.message }));
    process.exit(1);
  }
})();
