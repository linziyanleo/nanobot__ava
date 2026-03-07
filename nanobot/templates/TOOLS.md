# Tool Usage Notes

Tool signatures are provided automatically via function calling.
This file documents non-obvious constraints and usage patterns.

## exec — Safety Limits

- Commands have a configurable timeout (default 60s)
- Dangerous commands are blocked (rm -rf, format, dd, shutdown, etc.)
- Output is truncated at 10,000 characters
- `restrictToWorkspace` config can limit file access to the workspace

## image_gen — Image Generation & Editing

- Generate images from text prompts using Gemini's native image generation
- Edit existing images by providing a reference image + edit instruction
- Generated images are saved to `~/.nanobot/media/generated/`
- Use the `message` tool with `media` parameter to send generated images to the user

## cron — Scheduled Reminders

- Please refer to cron skill for usage.
