# InferLM 0.2 workspace

The desktop takes inspiration from OpenCode's terminal workspace: monospaced
text, flat neutral surfaces, restrained accent color, a focused conversation,
and keyboard access. InferLM keeps its own name, mark, copy, and local-model
workflow. No OpenCode code, fonts, icons, or brand assets are bundled.

## Layout
- One 232px sidebar contains navigation, session search, saved sessions, and
  observed device information. Ctrl+B hides/restores it.
- A compact header identifies the current screen and runtime state.
- Chat uses a centered reading column, capped at 900px. The composer holds the
  model picker, Load/Unload, and Send; secondary actions live in menus.
- The welcome screen links directly to model import, runtime setup, and tuning.
- Utility screens scroll at smaller sizes instead of hiding controls.
- A thin task footer reports progress and shows Stop only during a task.

## Tokens
| Token | Dark | Light |
| --- | --- | --- |
| Background | #141413 | #faf9f5 |
| Sidebar | #191918 | #f0efe9 |
| Surface | #20201e | #f5f4ee |
| Text | #e5e3dd | #262520 |
| Muted text | #a7a59d | #656258 |
| Accent | #e0b184 | #7c4d20 |
| Border | #353531 | #d8d5c9 |

System font preference: Cascadia Code, Consolas, DejaVu Sans Mono. Native Qt
scaling is retained. Dark/light palettes are independently defined; changing
appearance saves immediately without requiring a configured runtime.
Controls have visible focus states and accessible names. There is no decorative
animation; the existing 80ms stream batching remains.

## Shortcuts
| Key | Action |
| --- | --- |
| Ctrl+P | Search commands |
| Ctrl+B | Toggle sidebar |
| Ctrl+N | New session |
| Ctrl+1 … Ctrl+5 | Chat, Models, Optimize, Benchmarks, Settings |
| Enter | Send a message / run selected command |
| Shift+Enter | Newline in composer |
| Esc | Stop task; close command picker when it is open |

Menus keep rename/export/delete and copy/code/retry/edit/trim available.
Commands that mutate state are unavailable while a background job is running.

## Preview and evidence
README screenshots are actual offscreen Qt window captures. The chat screenshot
uses a clearly labeled example session, not measured model output. These images
verify layout in the build environment, not physical Windows compatibility.
Automated interactions cover command search/dispatch, keyboard focus, session
search/navigation, theme persistence, busy menus, cancellation, and composer
visibility at 960×620. All five screens were also inspected at 1320×840 and
960×620, in dark/light themes, with an additional QT_SCALE_FACTOR=2 capture pass.

## Reference
Anomaly. “OpenCode.” *GitHub*, github.com/anomalyco/opencode. Accessed 12 Oct. 2026.
Official README screenshot: packages/web/src/assets/lander/screenshot.png.
