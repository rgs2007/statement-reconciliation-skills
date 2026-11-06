/**
 * Installing the reconciliation skills into a project.
 *
 * The skills are installed **project-scoped**, into `<project>/.claude/skills/`,
 * rather than into the user's home directory. That means a project folder is
 * self-describing: copy it to another machine and the reconciliation still
 * runs the same way, against the same version of the skills it was built
 * with. A home-directory install would silently upgrade old projects to new
 * skill behaviour, which for an auditable process is the wrong default.
 *
 * All six are copied together. The orchestrator decides the flow but computes
 * nothing, so on its own it has no engine to call.
 */
import { cpSync, existsSync, mkdirSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

export const REQUIRED_SKILLS = [
  'statement-reconciliation',
  'recon-discovery',
  'recon-engine',
  'recon-item-matching',
  'recon-decisions',
  'recon-reporting'
] as const

export interface SkillInfo {
  name: string
  hasSkillMd: boolean
  scriptCount: number
}

/** Read a skill's frontmatter name, to catch a mis-packaged skill early. */
export function readSkillName(skillDir: string): string | null {
  const p = join(skillDir, 'SKILL.md')
  if (!existsSync(p)) return null
  const text = readFileSync(p, 'utf8')
  const fm = /^---\r?\n([\s\S]*?)\r?\n---/.exec(text)
  if (!fm) return null
  const m = /^name:\s*(\S+)/m.exec(fm[1])
  return m ? m[1] : null
}

function countScripts(dir: string): number {
  const scripts = join(dir, 'scripts')
  if (!existsSync(scripts)) return 0
  let n = 0
  const walk = (d: string): void => {
    for (const entry of readdirSync(d)) {
      const abs = join(d, entry)
      if (statSync(abs).isDirectory()) walk(abs)
      else if (entry.endsWith('.py')) n++
    }
  }
  walk(scripts)
  return n
}

export class SkillsInstaller {
  /** Where the bundled skills live inside the packaged app. */
  constructor(private readonly sourceRoot: string) {}

  available(): SkillInfo[] {
    if (!existsSync(this.sourceRoot)) return []
    return readdirSync(this.sourceRoot)
      .filter((d) => statSync(join(this.sourceRoot, d)).isDirectory())
      .map((name) => ({
        name,
        hasSkillMd: existsSync(join(this.sourceRoot, name, 'SKILL.md')),
        scriptCount: countScripts(join(this.sourceRoot, name))
      }))
  }

  /** Which required skills are missing from the bundle. */
  missing(): string[] {
    const have = new Set(this.available().filter((s) => s.hasSkillMd).map((s) => s.name))
    return REQUIRED_SKILLS.filter((s) => !have.has(s))
  }

  /**
   * Copy every bundled skill into the project.
   *
   * Overwrites on purpose: a project should always carry a complete, coherent
   * set, and a half-upgraded skills folder is harder to diagnose than a
   * replaced one. The user's own decisions live in decisions.jsonl, never
   * inside the skills, so nothing of theirs is at risk here.
   */
  installInto(projectFolder: string): { installed: string[]; missing: string[] } {
    const dest = join(projectFolder, '.claude', 'skills')
    mkdirSync(dest, { recursive: true })

    const installed: string[] = []
    for (const skill of this.available()) {
      if (!skill.hasSkillMd) continue
      cpSync(join(this.sourceRoot, skill.name), join(dest, skill.name), {
        recursive: true,
        force: true
      })
      installed.push(skill.name)
    }
    return { installed, missing: this.missing() }
  }

  /** Whether a project already has a usable set installed. */
  isInstalled(projectFolder: string): boolean {
    const dest = join(projectFolder, '.claude', 'skills')
    if (!existsSync(dest)) return false
    const have = new Set(
      readdirSync(dest).filter((d) => existsSync(join(dest, d, 'SKILL.md')))
    )
    return REQUIRED_SKILLS.every((s) => have.has(s))
  }
}
