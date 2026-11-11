import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")
TOOLS = os.path.join(ROOT, "tools")
LICENSE = os.path.join(ROOT, "download", "LICENSE.txt")


def mb(n):
    return "%.2f MB" % (n / 1048576)


def main(dest):
    with open(os.path.join(OUT, "manifest.json")) as f:
        manifest = json.load(f)
    if os.path.isdir(os.path.join(dest, "sf2")):
        shutil.rmtree(os.path.join(dest, "sf2"))
    os.makedirs(os.path.join(dest, "tools"), exist_ok=True)
    for x in manifest["instruments"]:
        x["path"] = "sf2/%s/%s.sf2" % (x["group"], x["key"])
        target = os.path.join(dest, x["path"])
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(os.path.join(OUT, "sf2", x["key"] + ".sf2"), target)
    with open(os.path.join(dest, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    shutil.copy2(LICENSE, os.path.join(dest, "LICENSE-GeneralUser-GS.txt"))
    if os.path.realpath(TOOLS) != os.path.realpath(os.path.join(dest, "tools")):
        for name in ("sf2tool.py", "build.py", "publish.py", "README.md", "README_TEMPLATE.md", "CREDITS.md"):
            shutil.copy2(os.path.join(TOOLS, name), os.path.join(dest, "tools", name))
    with open(os.path.join(dest, ".gitignore"), "w") as f:
        f.write("download/\nout/\n__pycache__/\n.DS_Store\n")

    rows = []
    total_n = total_b = 0
    for g in manifest["groups"]:
        items = [x for x in manifest["instruments"] if x["group"] == g["id"]]
        b = sum(x["bytes"] for x in items)
        total_n += len(items)
        total_b += b
        rows.append("| `%s` | %s | %d | %s |" % (g["id"], g["name"], len(items), mb(b)))
    rows.append("| | **Total** | **%d** | **%s** |" % (total_n, mb(total_b)))
    table = "\n".join(["| id | Name | Count | Size |", "|---|---|---:|---:|"] + rows)
    core = [x for x in manifest["instruments"] if x["isCore"]]
    with open(os.path.join(TOOLS, "README_TEMPLATE.md")) as f:
        readme = f.read()
    readme = (readme.replace("{{TABLE}}", table)
              .replace("{{SOURCE}}", manifest["source"])
              .replace("{{TOTAL_COUNT}}", str(total_n))
              .replace("{{TOTAL_SIZE}}", mb(total_b))
              .replace("{{CORE_COUNT}}", str(len(core)))
              .replace("{{CORE_SIZE}}", mb(sum(x["bytes"] for x in core))))
    with open(os.path.join(dest, "README.md"), "w") as f:
        f.write(readme)
    shutil.copy2(os.path.join(TOOLS, "CREDITS.md"), os.path.join(dest, "CREDITS.md"))
    print("published", total_n, "instruments", mb(total_b), "to", dest)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(ROOT), "doodle-beats-sounds"))
