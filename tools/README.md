# Tools

Python 3, standard library only. Always run with `python3 -I` (isolated mode) because the inputs are third-party downloads.

| File | Purpose |
|---|---|
| `sf2tool.py` | SF2 parser + single-preset extractor + validator. `python3 -I tools/sf2tool.py <file.sf2>` lists presets. |
| `build.py` | Splits `download/GeneralUser-GS.sf2` into `out/sf2/<key>.sf2`, writes `out/manifest.json`, copies core instruments to `out/core/`, writes `out/stats.json`. Skip rules, core list and name clean-up live at the top of this file. |
| `publish.py` | Builds the public repo layout (`manifest.json` with `path`, `sf2/<group>/<key>.sf2`, license, credits, README) from `out/`. Usage: `python3 -I tools/publish.py <dest>` (`.` = this repo). |
| `README_TEMPLATE.md`, `CREDITS.md` | Sources for the repo README (group table filled in automatically) and credits. |

## Regenerate everything

```sh
mkdir -p download
REV=684543d5e5efaef08d02be50dcda8d552478fa60
curl -fL -o download/GeneralUser-GS.sf2 https://raw.githubusercontent.com/mrbumpy409/GeneralUser-GS/$REV/GeneralUser-GS.sf2
curl -fL -o download/LICENSE.txt https://raw.githubusercontent.com/mrbumpy409/GeneralUser-GS/$REV/documentation/LICENSE.txt
shasum -a 256 download/GeneralUser-GS.sf2   # 9575028c7a1f589f5770fccc8cff2734566af40cd26ed836944e9a5152688cfe
python3 -I tools/build.py
python3 -I tools/publish.py .
```

`download/` and `out/` are git-ignored. For a new GeneralUser GS release: change `REV`, update the `source` string in `build.py`, rebuild, bump `version` in the manifest.

## What the splitter does

For each preset it keeps only that preset, the instruments its zones reference (generator 41) and the samples those reference (generator 53, plus linked stereo partners). Indices are remapped, sample data is copied with 46 zero padding points after each sample, loop points keep their offset relative to the sample start, `sm24` is carried along when present, and EOP/EOI/EOS terminal records are written. Every output is re-parsed and checked (1 preset, expected instrument/sample counts, all generator indices in range, terminal records, sample bounds, stereo links reciprocal).

Presets that are skipped: drum bank 120 (identical to bank 128), "Mono" and "noVel" duplicates, `011:029` Wah Guitar (needs CC21), and the `025/026:075` Tin Whistle near-duplicates. Any preset whose generators/modulators/instruments are byte-identical to an already kept one is skipped too.
