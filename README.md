# Resume Formatter

A tiny desktop app that turns any PDF resume into a clean, standardized Word document.

## Download (macOS)

- Apple Silicon (arm64):
  https://github.com/MacMcMurphy/Resume-Formatter/releases/download/v0.2.0/Resume-Formatter-macOS-arm64-v0.2.0.zip
- Intel (x86_64):
  https://github.com/MacMcMurphy/Resume-Formatter/releases/download/v0.2.1/Resume-Formatter-macOS-x86_64-v0.2.1.zip

Unzip, then double‑click "Resume Formatter.app" to launch.

## What it does

- Upload a PDF resume → get a formatted DOCX using the built‑in Word template
- Optional PII scrub panel to delete names, emails, phones, addresses, and URLs before processing
- Smart summary handling:
  - Generates a professional summary based on the resume content and the provided title
  - Always starts with the proper honorific ("Mr." or "Ms.")
  - Can lightly polish an existing summary
- Bullet consistency:
  - Spell‑checks and fixes spacing
  - Enforces punctuation by majority rule
    - If most bullets end with periods, it adds periods to the rest
    - If most do not, it removes the extra periods
- Experience title leveling:
  - If a candidate has 11+ years of experience and their title contains "Senior", it is automatically adjusted to "SME" for the final document
- Skills handling:
  - If the resume includes a skills section, those are used as‑is by default
  - If not, the app infers and organizes core skills from the resume content

All processing happens locally except the OpenAI calls used for structured extraction and light text polishing.

## How to open the app on macOS (first time)

Because this build isn’t notarized yet, macOS Gatekeeper may warn on first launch.

- Right‑click (or Control‑click) "Resume Formatter.app" → Open → Open
- Or: System Settings → Privacy & Security → scroll down to "Resume Formatter was blocked" → Open Anyway → Open
- Power users: you can remove the quarantine flag via Terminal and then open:
  ```bash
  xattr -dr com.apple.quarantine "$HOME/Downloads/Resume Formatter.app"
  open "$HOME/Downloads/Resume Formatter.app"
  ```

After the first successful open, you can launch it normally.

## First run

1) Your browser opens automatically to the setup page
2) Paste your OpenAI API key and click Save
3) Upload a PDF and follow the on‑screen steps

Outputs are saved to your local user data directory and linked on the results page.

## Create an OpenAI API key (quick guide)

1) Sign in at https://platform.openai.com
2) Go to your API keys page (Account → View API keys)
3) Click "Create new secret key" and copy it (starts with "sk-")
4) Keep it private. Usage is billed by OpenAI per their pricing

Paste this key into the app’s setup screen when prompted. You can rotate or revoke keys anytime in your OpenAI account.

## Notes

- Self‑contained app: no Python, Homebrew, or command line required
- The shipped template controls final fonts/styles; adjust the template if you want a different look
