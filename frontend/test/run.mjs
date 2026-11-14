// The frontend test suite. `npm test`.
//
// It is deliberately small and dependency-light: esbuild bundles each case so the application's
// own extensionless imports resolve the way Vite resolves them, and jsdom stands in for the
// browser. There is no test framework — a failed assertion is a non-zero exit, which is all a CI
// gate needs.
//
// What it covers is what a dependency bump actually breaks here, and both cases are real: js-yaml 5
// dropped its default export, and vue-router 5 is a major this application navigates through on
// every page.
import { build } from 'esbuild'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, rmSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
// Inside node_modules on purpose, not the system temp directory: the bundles import jsdom, vue and
// vue-router at run time (see `packages: 'external'` below), and Node resolves those by walking up
// from the file it is running. A bundle in /tmp would find nothing.
const out = mkdtempSync(join(here, '..', 'node_modules', '.test-'))
const cases = ['homer.mjs', 'router.mjs']
let failed = 0

try {
  for (const name of cases) {
    console.log(`\n=== ${name} ===`)
    const bundle = join(out, name)
    try {
      await build({
        entryPoints: [join(here, name)],
        bundle: true,
        platform: 'node',
        format: 'esm',
        outfile: bundle,
        logLevel: 'warning',
        // Only this repository's own source is bundled, which is the point: it is what resolves
        // the extensionless imports Vite resolves. Everything in node_modules stays external and
        // is loaded by Node itself — bundling a CommonJS package such as jsdom into an ESM file
        // breaks its internal require() calls.
        packages: 'external',
      })
      execFileSync(process.execPath, [bundle], { stdio: 'inherit' })
    } catch {
      failed++
    }
  }
} finally {
  rmSync(out, { recursive: true, force: true })
}

if (failed) {
  console.log(`\n${failed} of ${cases.length} test file(s) failed`)
  process.exit(1)
}
console.log(`\nall ${cases.length} test files passed`)
