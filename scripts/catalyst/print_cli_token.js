#!/usr/bin/env node
/**
 * Print the logged-in CLI's portable Catalyst token (CAT/#84).
 *
 * WHY: CI needs a `CATALYST_TOKEN`, normally minted with
 * `catalyst token:generate`. That command uses a device-code flow whose
 * verification must be completed by the SAME Zoho account the CLI is
 * logged in as — awkward on a headless VM and a repeated failure here.
 * The credential `catalyst login` already stored is the same kind of
 * refresh token, just encrypted with a machine-local key. This decrypts
 * it into the portable form the CLI accepts via CATALYST_TOKEN.
 *
 * SECURITY: the token grants full access to your Catalyst project.
 * It is written to stdout ONLY, so pipe it directly into a secret store —
 * never paste it into a file, a chat, an issue, or a PR:
 *
 *     node scripts/catalyst/print_cli_token.js | gh secret set CATALYST_TOKEN
 *
 * Revoke with `catalyst token:list` / `catalyst token:revoke <id>`, or by
 * logging out (`catalyst logout`), which invalidates the refresh token.
 *
 * Run from a directory containing catalyst.json.
 */
'use strict';

const { execSync } = require('node:child_process');
const path = require('node:path');

function cliLibDir() {
  const bin = execSync('readlink -f "$(command -v catalyst)"', {
    encoding: 'utf8',
    shell: '/bin/bash',
  }).trim();
  return path.resolve(path.dirname(bin), '..');
}

try {
  const lib = cliLibDir();
  const configStore = require(path.join(lib, 'util_modules/config-store.js')).default;
  const { getActiveDC } = require(path.join(lib, 'util_modules/dc.js'));
  const Credential = require(path.join(lib, 'authentication/credential.js')).default;

  const stored = configStore.get(`${getActiveDC()}.credential`);
  if (!stored) {
    console.error('No stored credential — run `catalyst login` first.');
    process.exit(1);
  }

  const tokenObj = Credential.decrypt(stored);
  const token = typeof tokenObj === 'string' ? tokenObj : tokenObj && tokenObj.token;
  if (!token) {
    console.error('Could not decrypt the stored credential on this machine.');
    process.exit(1);
  }

  // stdout only — intended to be piped
  process.stdout.write(String(token));
} catch (e) {
  console.error(`Failed to read CLI token: ${e.message}`);
  process.exit(1);
}
