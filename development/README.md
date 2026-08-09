# Development workspace

This directory contains BrainOS, AI coordination, proposals, handover material,
and experimental CLI tooling. None of these paths are required to start the
production Telegram bot.

The production bot remains in `03_Bot/` and is started by `run_bot.sh`.
Changes targeting `03_Bot/` remain production-impacting and must pass the
Confirm Gate and Safety CI before merge.
