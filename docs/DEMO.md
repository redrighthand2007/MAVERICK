# Demo script

A 60–90 second recording of MAVERICK for the README or a portfolio. Every request below is read-only,
or works on throwaway files in a demo folder, so recording it never changes anything that matters.

## Before recording

1. Make a demo folder with a file in it:
   ```powershell
   mkdir C:\demo\backup; "hello" > C:\demo\notes.txt; cd C:\demo
   ```
2. Optional: start Ollama, so the last-resort LLM is on.
3. Use a large terminal font (about 18 pt), a dark theme and a window about 100 columns wide.
4. Record with **ScreenToGif** (free) or the Windows Snipping Tool's video mode. Keep it under 90 s.

## Requests to type (in this order)

| # | Type this | Shows |
|---|---|---|
| 1 | `how much ram do i have` | Hardware agent, instant answer |
| 2 | `is my laptop charging` | Battery reading |
| 3 | `clone notes.txt into backup` | The MiniLM brain understands "clone" = copy |
| 4 | `duplicate notes.txt into backup` | Safety: refuses to overwrite |
| 5 | `which programs use the most memory` | Process agent, copies grouped (`chrome.exe x18`) |
| 6 | `any unusual programs running` | Isolation forest anomaly detection (takes about 6 s) |
| 7 | `free up 5 gb on c drive`, then answer **n** | Optimal clean-up plan + the y/n safety prompt |
| 8 | `zip C:\demo\backup` | Archive agent (give the full path) |
| 9 | `exit` | |

## After recording

- Save the GIF as `docs/demo.gif` and add `![MAVERICK demo](docs/demo.gif)` under the first paragraph
  of the README.
- Check the recording shows nothing private (file names in Downloads, user names, Wi-Fi names).
- Your real requests during the recording are logged to `maverick/brain/data/inbox.tsv`, which stays
  on your PC and is never uploaded.
