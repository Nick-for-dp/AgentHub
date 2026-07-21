import { spawnSync } from 'node:child_process'
import { resolve } from 'node:path'

const supportedProfiles = new Set(['external', 'internal'])
const requestedProfiles = process.argv.slice(2)
const profiles = requestedProfiles.length > 0 ? requestedProfiles : ['external', 'internal']

for (const profile of profiles) {
  if (!supportedProfiles.has(profile)) {
    throw new Error(`Unsupported deployment profile: ${profile}`)
  }
}

const root = process.cwd()
const vueTsc = resolve(root, 'node_modules/vue-tsc/bin/vue-tsc.js')
const vite = resolve(root, 'node_modules/vite/bin/vite.js')

function run(command, args, env = process.env) {
  const result = spawnSync(command, args, {
    env,
    stdio: 'inherit',
    shell: false,
  })
  if (result.error) throw result.error
  if (result.status !== 0) process.exit(result.status ?? 1)
}

run(process.execPath, [vueTsc, '-b'])

for (const profile of profiles) {
  run(process.execPath, [vite, 'build'], {
    ...process.env,
    VITE_DEPLOYMENT_PROFILE: profile,
    VITE_BUILD_OUT_DIR: `dist/${profile}`,
  })
}
