/**
 * The skills installer.
 *
 * The property that matters: a project folder must end up self-contained, so
 * it can be copied to another machine and reconcile the same way. These tests
 * check the whole required set is installed and that a mis-packaged bundle is
 * reported rather than producing a project that half-works.
 */
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import {
  REQUIRED_SKILLS,
  SkillsInstaller,
  readSkillName
} from '../../src/main/services/skills-installer'

let root: string
let bundle: string
let project: string

function makeSkill(name: string, opts: { skillMd?: boolean; scripts?: string[] } = {}): void {
  const dir = join(bundle, name)
  mkdirSync(dir, { recursive: true })
  if (opts.skillMd !== false) {
    writeFileSync(join(dir, 'SKILL.md'), `---\nname: ${name}\ndescription: test skill\n---\n\n# ${name}\n`)
  }
  for (const s of opts.scripts ?? []) {
    const p = join(dir, 'scripts', s)
    mkdirSync(join(p, '..'), { recursive: true })
    writeFileSync(p, '# script\n')
  }
}

beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), 'fsr-skills-'))
  bundle = join(root, 'skills')
  project = join(root, 'project')
  mkdirSync(bundle, { recursive: true })
  mkdirSync(project, { recursive: true })
})
afterEach(() => rmSync(root, { recursive: true, force: true }))

describe('readSkillName', () => {
  it('reads the frontmatter name', () => {
    makeSkill('recon-engine')
    expect(readSkillName(join(bundle, 'recon-engine'))).toBe('recon-engine')
  })

  it('returns null without a SKILL.md', () => {
    mkdirSync(join(bundle, 'empty'), { recursive: true })
    expect(readSkillName(join(bundle, 'empty'))).toBeNull()
  })

  it('returns null when there is no frontmatter', () => {
    mkdirSync(join(bundle, 'plain'), { recursive: true })
    writeFileSync(join(bundle, 'plain', 'SKILL.md'), '# Just a heading\n')
    expect(readSkillName(join(bundle, 'plain'))).toBeNull()
  })
})

describe('available', () => {
  it('counts scripts recursively, including the steps folder', () => {
    makeSkill('recon-engine', { scripts: ['reconcile.py', 'steps/load.py', 'steps/equation.py'] })
    const found = new SkillsInstaller(bundle).available().find((s) => s.name === 'recon-engine')
    expect(found?.scriptCount).toBe(3)
  })

  it('returns nothing when the bundle is missing rather than throwing', () => {
    expect(new SkillsInstaller(join(root, 'nope')).available()).toEqual([])
  })
})

describe('missing', () => {
  it('names every required skill absent from the bundle', () => {
    makeSkill('recon-engine')
    const missing = new SkillsInstaller(bundle).missing()
    expect(missing).not.toContain('recon-engine')
    expect(missing).toContain('statement-reconciliation')
    expect(missing).toHaveLength(REQUIRED_SKILLS.length - 1)
  })

  it('treats a skill without SKILL.md as missing, not present', () => {
    for (const s of REQUIRED_SKILLS) makeSkill(s)
    rmSync(join(bundle, 'recon-reporting', 'SKILL.md'))
    expect(new SkillsInstaller(bundle).missing()).toEqual(['recon-reporting'])
  })

  it('is empty for a complete bundle', () => {
    for (const s of REQUIRED_SKILLS) makeSkill(s)
    expect(new SkillsInstaller(bundle).missing()).toEqual([])
  })
})

describe('installInto', () => {
  it('installs project-scoped, so the project is portable', () => {
    for (const s of REQUIRED_SKILLS) makeSkill(s, { scripts: ['x.py'] })
    const res = new SkillsInstaller(bundle).installInto(project)

    expect(res.installed.sort()).toEqual([...REQUIRED_SKILLS].sort())
    expect(res.missing).toEqual([])
    for (const s of REQUIRED_SKILLS) {
      expect(existsSync(join(project, '.claude', 'skills', s, 'SKILL.md'))).toBe(true)
    }
    expect(existsSync(join(project, '.claude', 'skills', 'recon-engine', 'scripts', 'x.py'))).toBe(true)
  })

  it('overwrites an older copy so the set stays coherent', () => {
    makeSkill('recon-engine')
    const inst = new SkillsInstaller(bundle)
    inst.installInto(project)
    const dest = join(project, '.claude', 'skills', 'recon-engine', 'SKILL.md')
    writeFileSync(dest, 'stale content')
    inst.installInto(project)
    expect(existsSync(dest)).toBe(true)
    expect(readSkillName(join(project, '.claude', 'skills', 'recon-engine'))).toBe('recon-engine')
  })

  it('reports what is missing instead of failing silently', () => {
    makeSkill('recon-engine')
    const res = new SkillsInstaller(bundle).installInto(project)
    expect(res.installed).toEqual(['recon-engine'])
    expect(res.missing.length).toBeGreaterThan(0)
  })
})

describe('isInstalled', () => {
  it('is false before installing', () => {
    expect(new SkillsInstaller(bundle).isInstalled(project)).toBe(false)
  })

  it('is true only once the whole required set is present', () => {
    for (const s of REQUIRED_SKILLS) makeSkill(s)
    const inst = new SkillsInstaller(bundle)
    inst.installInto(project)
    expect(inst.isInstalled(project)).toBe(true)

    // The orchestrator computes nothing, so a project without the engine is
    // not usable even though a skill folder exists.
    rmSync(join(project, '.claude', 'skills', 'recon-engine'), { recursive: true })
    expect(inst.isInstalled(project)).toBe(false)
  })
})
