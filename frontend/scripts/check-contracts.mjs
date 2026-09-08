import { createRequire } from 'node:module'
import { mkdtemp, rm } from 'node:fs/promises'
import { resolve } from 'node:path'
import { spawnSync } from 'node:child_process'
const require = createRequire(import.meta.url)
const { build } = createRequire(require.resolve('vite/package.json'))('esbuild')
const output = await mkdtemp(resolve('node_modules/.frontend-check-'))
try {
  const file = resolve(output,'contracts.mjs')
  await build({ entryPoints:['tests/contracts.ts'], outfile:file, bundle:true, platform:'node', format:'esm', packages:'external', alias:{'@':resolve('src')}, define:{'import.meta.env.VITE_USE_MOCK':'"false"','import.meta.env.VITE_API_BASE_URL':'""'} })
  const result=spawnSync(process.execPath,['--test',file],{stdio:'inherit'})
  process.exitCode=result.status ?? 1
} finally { await rm(output,{recursive:true,force:true}) }

