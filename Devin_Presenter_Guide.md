# Devin Presenter Guide

**Session:** Developer community presentation
**Duration:** 35 minutes + Q&A

## How to run the talk
Start with the problem Devin solves: backlog pressure, repetitive coding work, migrations, and the need to move faster without adding manual effort.
Move next into what Devin is and how it works: autonomous task execution, embedded workspace, planning, editing, testing, and review.
Then cover the parts developers will care about most: DeepWiki, codebase Q&A, API usage, Slack / repo / Jira integrations, and MCP.
Finish with ACU efficiency guidance, a small demo, and a few crisp Q&A answers.

## Timing guide
| Time | Topic | What to say |
|---|---|---|
| 0–3 min | Why Devin | Explain the developer pain points: backlog, repetitive work, and migration/refactor overhead. |
| 3–10 min | What Devin is | Describe Devin as an autonomous AI software engineer that can plan, code, test, and debug. |
| 10–18 min | Features and workflow | Cover parallel sessions, embedded IDE, planning, DeepWiki, and verification. |
| 18–24 min | APIs and integrations | Show how Devin fits into Slack, repos, Jira/Linear, and MCP-enabled tools. |
| 24–30 min | ACU efficiency | Focus on clear prompts, smaller sessions, tests, and Session Insights. |
| 30–35 min | Demo recap + Q&A | Summarize value, mention limits, and invite questions. |

## Demo suggestions
Use one small example only.

- Bug fix in a tiny repo: reproduce, patch, test, and review the result.
- Ticket-to-PR walkthrough: show Devin taking a small issue to a reviewable change.
- Repo Q&A demo: ask a simple “where is this handled?” question and show DeepWiki context.

## How to avoid burning ACUs
- Give the outcome, scope, and file-level context up front.
- Ask Devin to verify with tests or a clear check before stopping.
- Split broad work into multiple focused sessions.
- Use Session Insights after each run and tighten the prompt if the session went broad.

## Likely Q&A
**How do I avoid burning ACUs?** Scope tightly, provide context early, and break large work into smaller sessions.

**Can Devin work from our tools?** Yes. Mention API, Slack, repo integration, Jira/Linear, and MCP.

**What is it best suited for?** Repetitive, multi-step engineering work with a clear definition of done.

**How much do I trust the output?** Review the diff, run tests, and keep human approval in the loop.

## Closing line
> “Devin can take a meaningful amount of engineering work off the team’s plate, but the best results come when the task is scoped, verified, and reviewed well.”
