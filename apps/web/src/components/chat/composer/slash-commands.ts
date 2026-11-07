export const SLASH_COMMANDS = [
  { cmd: "/research", hint: "Find winning content", template: "Research the top TikTok UGC videos for " },
  { cmd: "/patterns", hint: "Extract hooks and structure", template: "Break these videos into hook, script structure and CTA patterns: " },
  { cmd: "/script", hint: "Write scripts", template: "Write 5 original 30-second UGC scripts for " },
  { cmd: "/generate", hint: "Generate media", template: "Generate 3 vertical UGC-style videos for " },
  { cmd: "/publish", hint: "Schedule posts", template: "Schedule the approved videos to " },
  { cmd: "/analyze", hint: "Review performance", template: "How did our recent posts perform? Analyze " },
] as const;

/** Commands matching the draft when it is a lone "/word" token. */
export const matchSlash = (draft: string) =>
  /^\/\w*$/.test(draft) ? SLASH_COMMANDS.filter((c) => c.cmd.startsWith(draft.toLowerCase())) : [];
