# Case Study Feature — AI Handoff Context

Paste this ALONG WITH `03_Bot/AI_CONTEXT.md` at the start of any session
where you want an AI to work on the "📚 কেস স্টাডি" feature. This stops
every AI from re-asking the same questions.

## What this feature is supposed to do

User acts as a BPT student. They send a live patient case. The bot must
teach that ONE case across 10 fixed Lessons, one at a time, only moving
to the next Lesson when the user replies "দাও". Full lesson-by-lesson
spec (topics, rules, tone, evidence-based guardrails) is in the file
`CASE_STUDY_LESSON_SPEC.md` — paste that too if the AI needs to write or
edit the lesson content/prompt itself.

## Current state (as of last check)

- `case_study_ai.py` — only has a single-shot `answer_case_study()` that
  calls OpenRouter once and returns a subject-relevance summary. No lesson
  tracking, no state, no "দাও" continuation.
- `bot.py`:
  - `import case_study_ai` → line 50
  - `roles.MENU_CASE_STUDY` menu entry → line 123
  - generic "🚧 এখনো তৈরি হচ্ছে" stub → line 2785 (need to confirm if this
    IS the "দাও" continuation or an unrelated stub — check before editing)
  - case study conversation handler logic → around lines 3280–3330
  - handler registration in `main()` → line 3620

Line numbers drift as the file changes — always re-grep, don't assume.

## Commands to run FIRST in any new session on this feature

Run these in Termux, paste the full output to the AI before asking for
any code:

```
cd ~/relife-clinic-os/03_Bot
cat case_study_ai.py
```

```
grep -n "কেস স্টাডি\|case_study\|CASE_STUDY\|তৈরি হচ্ছে" bot.py
```

```
sed -n '3260,3340p' bot.py
```

```
sed -n '2760,2800p' bot.py
```

```
grep -n "CASE" roles.py
```

## Standard patch/deploy workflow (same as main AI_CONTEXT.md)

1. AI writes a standalone `patchN.py` (function-span or exact-string
   replace), tests it against a sandbox copy first.
2. AI gives you a `cat > patchN.py <<'PY' ... PY` heredoc to paste.
3. You run `python patchN.py`, screenshot/paste the output back.
4. AI confirms or fixes.
5. You run:
   ```
   python -m py_compile bot.py && echo OK
   ```
6. Then exactly 2 commands to deploy:
   ```
   git add -A && git commit -m "short message"
   ```
   ```
   git push
   ```
   Render auto-deploys from `main` after the push.

## Rule for this feature specifically

Don't touch `answer_case_study()`'s existing single-shot behavior unless
asked — it may still be used elsewhere. The 10-Lesson flow needs NEW
functions/state (e.g. store current lesson number + original case text
in `context.user_data`), not a rewrite of the existing function.
