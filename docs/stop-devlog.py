"""Stop hook: appends a dated header to docs/devlog.md once per calendar day."""
import datetime
import pathlib

devlog = pathlib.Path(__file__).parent / "devlog.md"
devlog.parent.mkdir(exist_ok=True)

today = datetime.date.today().isoformat()
now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

content = devlog.read_text(encoding="utf-8") if devlog.exists() else ""
if today not in content:
    with devlog.open("a", encoding="utf-8") as f:
        f.write(f"\n## {today}\n\n- Session active at {now}\n")
