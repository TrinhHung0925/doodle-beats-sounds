import hashlib
import json
import os
import re
import shutil
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sf2tool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "download", "GeneralUser-GS.sf2")
OUT = os.path.join(ROOT, "out")

GROUPS = [
    ("piano", "Piano"), ("chromatic_percussion", "Chromatic Percussion"), ("organ", "Organ"),
    ("guitar", "Guitar"), ("bass", "Bass"), ("strings", "Strings"), ("ensemble", "Ensemble"),
    ("brass", "Brass"), ("reed", "Reed"), ("pipe", "Pipe"), ("synth_lead", "Synth Lead"),
    ("synth_pad", "Synth Pad"), ("synth_effects", "Synth Effects"), ("ethnic", "Ethnic"),
    ("percussive", "Percussive"), ("sfx", "Sound Effects"), ("drums", "Drums"),
]

SKIP = {
    (11, 29): "needs CC21 pedal control to be useful (Wah Guitar)",
    (25, 75): "near-duplicate of 024:075 Tin Whistle (no-modulation variant)",
    (26, 75): "near-duplicate of 024:075 Tin Whistle (ornamented variant)",
}

CORE = [
    (0, 0), (0, 4), (0, 8), (0, 9), (0, 10), (0, 11), (0, 12), (0, 13), (0, 108),
    (0, 24), (0, 25), (0, 46), (0, 45), (0, 33), (0, 38), (0, 80), (0, 81),
    (0, 73), (0, 79), (0, 75), (0, 56), (0, 48), (0, 52), (0, 114), (0, 112),
    (128, 0),
]

ABBREV = [
    (r"\bTnwl\.?", "Tonewheel"), (r"\bPerc\.", "Percussive"), (r"\bGt\.", "Guitar"),
    (r"\bStr\.-", "Strings "), (r"\bFl\.", "Flute"), (r"\bTrem\.", "Tremolo"),
    (r"\bDetun\b", "Detuned"), (r"\bOrg\b", "Organ"), (r"\bHarpsi\b", "Harpsichord"),
    (r"\bEPs\b", "Electric Pianos"), (r"\bEP\b", "Electric Piano"), (r"\bCeleste\b", "Celesta"),
]


def display_name(p):
    n = p["name"].strip()
    for pat, rep in ABBREV:
        n = re.sub(pat, rep, n)
    n = re.sub(r"^Car-", "Car ", n)
    n = re.sub(r"\s+", " ", n).strip()
    if p["bank"] == 128 and not n.lower().endswith("kit"):
        n += " Kit"
    return n


def group_for(bank, program):
    if bank == 128:
        return "drums"
    return GROUPS[program // 8][0]


def skip_reason(sf, i, p, kept_sigs):
    if (p["bank"], None) in SKIP:
        return SKIP[(p["bank"], None)]
    if (p["bank"], p["preset"]) in SKIP:
        return SKIP[(p["bank"], p["preset"])]
    if p["bank"] not in (0, 128):
        if re.search(r"\bMono\b", p["name"]):
            return "mono duplicate of a stereo preset"
        if re.search(r"noVel", p["name"]):
            return "velocity-insensitive duplicate"
    sig = (tuple(sf.preset_instruments(i)), sf.preset_signature(i))
    if sig in kept_sigs:
        return "identical to %s" % kept_sigs[sig]
    return None


def main():
    sf = sf2tool.SF2(SRC)
    sf2_dir = os.path.join(OUT, "sf2")
    core_dir = os.path.join(OUT, "core")
    for d in (sf2_dir, core_dir):
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d)

    linked_mods = 0
    for raw in sf.pmod[:-1] + sf.imod[:-1]:
        if struct.unpack_from("<H", raw, 2)[0] & 0x8000:
            linked_mods += 1
    rom = [s["name"] for s in sf.shdr[:-1] if s["type"] & 0x8000]
    stereo = sum(1 for s in sf.shdr[:-1] if s["type"] & 0x0E)

    order = sorted(range(len(sf.presets)), key=lambda i: (
        0 if sf.phdr[i]["bank"] in (0, 128) else 1, sf.phdr[i]["bank"], sf.phdr[i]["preset"]))
    kept_sigs = {}
    instruments = []
    skipped = []
    failed = []
    for i in order:
        p = sf.phdr[i]
        key = "b%03d_p%03d" % (p["bank"], p["preset"])
        reason = skip_reason(sf, i, p, kept_sigs)
        if reason:
            skipped.append((key, p["name"], reason))
            continue
        kept_sigs[(tuple(sf.preset_instruments(i)), sf.preset_signature(i))] = key
        name = display_name(p)
        data, ni, ns = sf2tool.extract_preset(sf, i, inam="GeneralUser GS - " + name)
        path = os.path.join(sf2_dir, key + ".sf2")
        with open(path, "wb") as f:
            f.write(data)
        errs = sf2tool.validate(path, ni, ns)
        if errs:
            failed.append((key, errs))
            os.remove(path)
            continue
        instruments.append(dict(
            key=key, name=name, group=group_for(p["bank"], p["preset"]), bank=p["bank"],
            program=p["preset"], isDrum=p["bank"] == 128,
            isCore=(p["bank"], p["preset"]) in CORE, bytes=len(data),
            path="sf2/%s/%s.sf2" % (group_for(p["bank"], p["preset"]), key),
            sha256=hashlib.sha256(data).hexdigest(), _inst=ni, _samples=ns, _orig=p["name"]))

    instruments.sort(key=lambda x: ([g for g, _ in GROUPS].index(x["group"]), x["bank"] != 0 and x["bank"] != 128, x["program"], x["bank"]))
    core = [x for x in instruments if x["isCore"]]
    for x in core:
        shutil.copy2(os.path.join(sf2_dir, x["key"] + ".sf2"), os.path.join(core_dir, x["key"] + ".sf2"))

    manifest = dict(
        version=1, source="GeneralUser GS v2.0.3", baseUrl="",
        groups=[dict(id=g, name=n, order=k) for k, (g, n) in enumerate(GROUPS)],
        instruments=[{k: v for k, v in x.items() if not k.startswith("_")} for x in instruments])
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    stats = dict(
        source_presets=len(sf.presets), source_inst=len(sf.inst) - 1, source_samples=len(sf.shdr) - 1,
        sm24=sf.sm24 is not None, linked_mods=linked_mods, rom_samples=rom, stereo_samples=stereo,
        kept=len(instruments), skipped=skipped, failed=failed,
        total_bytes=sum(x["bytes"] for x in instruments), core_bytes=sum(x["bytes"] for x in core),
        core=[(x["key"], x["name"], x["bytes"]) for x in core],
        by_group={g: sum(1 for x in instruments if x["group"] == g) for g, _ in GROUPS},
        by_bank={b: sum(1 for x in instruments if x["bank"] == b) for b in sorted({x["bank"] for x in instruments})},
        renamed=[(x["key"], x["_orig"], x["name"]) for x in instruments if x["_orig"] != x["name"]],
        largest=sorted(((x["bytes"], x["key"], x["name"]) for x in instruments), reverse=True)[:8],
        dup_names=sorted({x["name"] for x in instruments if sum(1 for y in instruments if y["name"] == x["name"]) > 1}),
    )
    with open(os.path.join(OUT, "stats.json"), "w") as f:
        json.dump(stats, f, indent=1)
    print(json.dumps({k: v for k, v in stats.items() if k not in ("skipped", "renamed")}, indent=1))
    print("skipped", len(skipped))
    for s in skipped:
        print("  ", s)
    for r in stats["renamed"]:
        print("  rename", r)


if __name__ == "__main__":
    main()
