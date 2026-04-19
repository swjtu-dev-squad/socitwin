const TARGET_SECTION_TITLES = ['SELF-DESCRIPTION', 'RESPONSE METHOD'] as const

function normalizeMemoryText(value: string | null | undefined) {
  return String(value ?? '')
    .replace(/\r\n/g, '\n')
    .trim()
}

export function getDisplayMemoryContent(content: string | null | undefined) {
  const normalized = normalizeMemoryText(content)
  if (!normalized) return ''

  const lines = normalized.split('\n')
  const sections: string[] = []
  let currentTitle = ''
  let currentLines: string[] = []

  const flushSection = () => {
    if (!currentTitle) return
    const body = currentLines.join('\n').trim()
    sections.push(body ? `# ${currentTitle}\n${body}` : `# ${currentTitle}`)
  }

  for (const rawLine of lines) {
    const line = rawLine.trimEnd()
    const headingMatch = line.match(/^\s*#\s+(.+?)\s*$/)
    if (headingMatch) {
      flushSection()
      currentTitle = headingMatch[1].trim()
      currentLines = []
      continue
    }

    if (currentTitle && TARGET_SECTION_TITLES.some(title => currentTitle === title)) {
      currentLines.push(line)
    }
  }

  flushSection()

  const targetedSections = sections.filter(section =>
    TARGET_SECTION_TITLES.some(title => section.startsWith(`# ${title}`))
  )

  if (targetedSections.length > 0) {
    return targetedSections.join('\n\n')
  }

  return normalized
}
