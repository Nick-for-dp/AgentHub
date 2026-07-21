import { readdir, readFile } from 'node:fs/promises'
import { resolve } from 'node:path'

const root = process.cwd()
const externalRoot = resolve(root, 'dist/external')
const internalRoot = resolve(root, 'dist/internal')

async function collectFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  const files = []
  for (const entry of entries) {
    const target = resolve(directory, entry.name)
    if (entry.isDirectory()) files.push(...(await collectFiles(target)))
    else files.push(target)
  }
  return files
}

async function searchableOutput(directory) {
  const files = await collectFiles(directory)
  const textFiles = files.filter((file) => /\.(html|js|css)$/.test(file))
  const contents = await Promise.all(textFiles.map((file) => readFile(file, 'utf8')))
  return {
    names: files.join('\n'),
    contents: contents.join('\n'),
  }
}

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

const external = await searchableOutput(externalRoot)
const internal = await searchableOutput(internalRoot)

for (const marker of ['ContractReviewPage', 'RiskAssistantPage', 'InternalLayout']) {
  assert(!external.names.includes(marker), `external build contains internal chunk: ${marker}`)
}
for (const marker of ['/internal/contract-review', '合同审查工作台', '风控助手']) {
  assert(!external.contents.includes(marker), `external build contains internal marker: ${marker}`)
}

assert(internal.names.includes('ContractReviewPage'), 'internal build misses contract review chunk')
assert(internal.names.includes('RiskAssistantPage'), 'internal build misses risk assistant chunk')
assert(internal.contents.includes('AgentHub 内部智能体'), 'internal build misses login branding')
assert(external.contents.includes('AgentHub 营销智能体'), 'external build misses login branding')

process.stdout.write('Profile build isolation checks passed.\n')
