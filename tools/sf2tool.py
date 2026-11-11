import struct
import sys
import os

GEN_INSTRUMENT = 41
GEN_SAMPLE_ID = 53
SAMPLE_PAD = 46


def _cstr(b):
    return b.split(b"\0", 1)[0].decode("latin-1")


def _chunks(data, off, end):
    while off + 8 <= end:
        cid = data[off:off + 4]
        size = struct.unpack_from("<I", data, off + 4)[0]
        yield cid, off + 8, size
        off += 8 + size + (size & 1)


class SF2:
    def __init__(self, path):
        with open(path, "rb") as f:
            data = f.read()
        if data[:4] != b"RIFF" or data[8:12] != b"sfbk":
            raise ValueError("not an sf2 file")
        riff_size = struct.unpack_from("<I", data, 4)[0]
        self.info = []
        self.smpl = b""
        self.sm24 = None
        pdta = {}
        for cid, off, size in _chunks(data, 12, min(len(data), 8 + riff_size)):
            if cid != b"LIST":
                continue
            ltype = data[off:off + 4]
            for scid, soff, ssize in _chunks(data, off + 4, off + size):
                body = data[soff:soff + ssize]
                if ltype == b"INFO":
                    self.info.append((scid, body))
                elif ltype == b"sdta":
                    if scid == b"smpl":
                        self.smpl = body
                    elif scid == b"sm24":
                        self.sm24 = body
                elif ltype == b"pdta":
                    pdta[scid] = body
        for k in (b"phdr", b"pbag", b"pmod", b"pgen", b"inst", b"ibag", b"imod", b"igen", b"shdr"):
            if k not in pdta:
                raise ValueError("missing pdta chunk %s" % k)
        self.phdr = [
            dict(name=_cstr(r[0]), preset=r[1], bank=r[2], bag=r[3], library=r[4], genre=r[5], morphology=r[6])
            for r in struct.iter_unpack("<20sHHHIII", pdta[b"phdr"])
        ]
        self.pbag = list(struct.iter_unpack("<HH", pdta[b"pbag"]))
        self.pmod = [pdta[b"pmod"][i:i + 10] for i in range(0, len(pdta[b"pmod"]), 10)]
        self.pgen = list(struct.iter_unpack("<Hh", pdta[b"pgen"]))
        self.pgen_raw = [pdta[b"pgen"][i:i + 4] for i in range(0, len(pdta[b"pgen"]), 4)]
        self.inst = [dict(name=_cstr(r[0]), bag=r[1]) for r in struct.iter_unpack("<20sH", pdta[b"inst"])]
        self.ibag = list(struct.iter_unpack("<HH", pdta[b"ibag"]))
        self.imod = [pdta[b"imod"][i:i + 10] for i in range(0, len(pdta[b"imod"]), 10)]
        self.igen = list(struct.iter_unpack("<Hh", pdta[b"igen"]))
        self.igen_raw = [pdta[b"igen"][i:i + 4] for i in range(0, len(pdta[b"igen"]), 4)]
        self.shdr = [
            dict(name=_cstr(r[0]), start=r[1], end=r[2], loopstart=r[3], loopend=r[4], rate=r[5],
                 pitch=r[6], corr=r[7], link=r[8], type=r[9])
            for r in struct.iter_unpack("<20sIIIIIBbHH", pdta[b"shdr"])
        ]

    @property
    def presets(self):
        return self.phdr[:-1]

    def preset_zones(self, pi):
        return range(self.phdr[pi]["bag"], self.phdr[pi + 1]["bag"])

    def inst_zones(self, ii):
        return range(self.inst[ii]["bag"], self.inst[ii + 1]["bag"])

    def zone_gens(self, bags, gens, z):
        return range(bags[z][0], bags[z + 1][0])

    def zone_mods(self, bags, z):
        return range(bags[z][1], bags[z + 1][1])

    def preset_instruments(self, pi):
        out = []
        for z in self.preset_zones(pi):
            for g in self.zone_gens(self.pbag, self.pgen, z):
                if self.pgen[g][0] == GEN_INSTRUMENT:
                    i = self.pgen[g][1] & 0xFFFF
                    if i not in out:
                        out.append(i)
        return out

    def instrument_samples(self, ii):
        out = []
        for z in self.inst_zones(ii):
            for g in self.zone_gens(self.ibag, self.igen, z):
                if self.igen[g][0] == GEN_SAMPLE_ID:
                    s = self.igen[g][1] & 0xFFFF
                    if s not in out:
                        out.append(s)
        return out

    def preset_signature(self, pi):
        parts = []
        for z in self.preset_zones(pi):
            parts.append(tuple(self.pgen_raw[g] for g in self.zone_gens(self.pbag, self.pgen, z)))
            parts.append(tuple(self.pmod[m] for m in self.zone_mods(self.pbag, z)))
        return tuple(parts)


def _sub(cid, body):
    if len(body) & 1:
        body += b"\0"
    return cid + struct.pack("<I", len(body)) + body


def _list(ltype, chunks):
    body = ltype + b"".join(chunks)
    return b"LIST" + struct.pack("<I", len(body)) + body


def _zstr(s, even=True):
    b = s.encode("latin-1", "replace") + b"\0"
    if even and len(b) & 1:
        b += b"\0"
    return b


def _name20(s):
    return s.encode("latin-1", "replace")[:20].ljust(20, b"\0")


def extract_preset(sf, pi, inam=None):
    p = sf.phdr[pi]
    inst_list = sf.preset_instruments(pi)
    sample_list = []
    for ii in inst_list:
        for s in sf.instrument_samples(ii):
            if s not in sample_list:
                sample_list.append(s)
    i = 0
    while i < len(sample_list):
        sh = sf.shdr[sample_list[i]]
        if sh["type"] & 0x0E and not sh["type"] & 0x8000:
            ln = sh["link"]
            if ln < len(sf.shdr) - 1 and ln not in sample_list:
                sample_list.append(ln)
        i += 1
    inst_map = {old: new for new, old in enumerate(inst_list)}
    samp_map = {old: new for new, old in enumerate(sample_list)}

    smpl = bytearray()
    sm24 = bytearray() if sf.sm24 is not None else None
    shdr = bytearray()
    for old in sample_list:
        sh = sf.shdr[old]
        n = sh["end"] - sh["start"]
        new_start = len(smpl) // 2
        smpl += sf.smpl[sh["start"] * 2:sh["end"] * 2]
        smpl += b"\0" * (SAMPLE_PAD * 2)
        if sm24 is not None:
            sm24 += sf.sm24[sh["start"]:sh["end"]]
            sm24 += b"\0" * SAMPLE_PAD
        link = sh["link"]
        if sh["type"] & 0x0E and not sh["type"] & 0x8000:
            link = samp_map.get(link, 0)
        else:
            link = 0
        shdr += struct.pack(
            "<20sIIIIIBbHH", _name20(sh["name"]), new_start, new_start + n,
            new_start + (sh["loopstart"] - sh["start"]), new_start + (sh["loopend"] - sh["start"]),
            sh["rate"], sh["pitch"], sh["corr"], link, sh["type"])
    shdr += struct.pack("<20sIIIIIBbHH", _name20("EOS"), 0, 0, 0, 0, 0, 0, 0, 0, 0)

    inst = bytearray()
    ibag = bytearray()
    imod = bytearray()
    igen = bytearray()
    nbag = ngen = nmod = 0
    for old in inst_list:
        inst += struct.pack("<20sH", _name20(sf.inst[old]["name"]), nbag)
        for z in sf.inst_zones(old):
            ibag += struct.pack("<HH", ngen, nmod)
            nbag += 1
            for g in sf.zone_gens(sf.ibag, sf.igen, z):
                op = sf.igen[g][0]
                if op == GEN_SAMPLE_ID:
                    igen += struct.pack("<HH", op, samp_map[sf.igen[g][1] & 0xFFFF])
                else:
                    igen += sf.igen_raw[g]
                ngen += 1
            for m in sf.zone_mods(sf.ibag, z):
                imod += sf.imod[m]
                nmod += 1
    inst += struct.pack("<20sH", _name20("EOI"), nbag)
    ibag += struct.pack("<HH", ngen, nmod)
    imod += b"\0" * 10
    igen += b"\0" * 4

    pbag = bytearray()
    pmod = bytearray()
    pgen = bytearray()
    nbag = ngen = nmod = 0
    for z in sf.preset_zones(pi):
        pbag += struct.pack("<HH", ngen, nmod)
        nbag += 1
        for g in sf.zone_gens(sf.pbag, sf.pgen, z):
            op = sf.pgen[g][0]
            if op == GEN_INSTRUMENT:
                pgen += struct.pack("<HH", op, inst_map[sf.pgen[g][1] & 0xFFFF])
            else:
                pgen += sf.pgen_raw[g]
            ngen += 1
        for m in sf.zone_mods(sf.pbag, z):
            pmod += sf.pmod[m]
            nmod += 1
    pbag += struct.pack("<HH", ngen, nmod)
    pmod += b"\0" * 10
    pgen += b"\0" * 4
    phdr = struct.pack("<20sHHHIII", _name20(p["name"]), p["preset"], p["bank"], 0,
                       p["library"], p["genre"], p["morphology"])
    phdr += struct.pack("<20sHHHIII", _name20("EOP"), 0, 0, nbag, 0, 0, 0)

    info = []
    seen = set()
    for cid, body in sf.info:
        if cid == b"INAM":
            body = _zstr(inam or p["name"])
        info.append(_sub(cid, body))
        seen.add(cid)
    if b"ifil" not in seen:
        info.insert(0, _sub(b"ifil", struct.pack("<HH", 2, 1)))
    if b"isng" not in seen:
        info.append(_sub(b"isng", _zstr("EMU8000")))
    if b"INAM" not in seen:
        info.append(_sub(b"INAM", _zstr(inam or p["name"])))

    sdta = [_sub(b"smpl", bytes(smpl))]
    if sm24 is not None:
        sdta.append(_sub(b"sm24", bytes(sm24)))
    pdta = [_sub(b"phdr", phdr), _sub(b"pbag", bytes(pbag)), _sub(b"pmod", bytes(pmod)),
            _sub(b"pgen", bytes(pgen)), _sub(b"inst", bytes(inst)), _sub(b"ibag", bytes(ibag)),
            _sub(b"imod", bytes(imod)), _sub(b"igen", bytes(igen)), _sub(b"shdr", bytes(shdr))]
    body = b"sfbk" + _list(b"INFO", info) + _list(b"sdta", sdta) + _list(b"pdta", pdta)
    return b"RIFF" + struct.pack("<I", len(body)) + body, len(inst_list), len(sample_list)


def validate(path, exp_inst, exp_samples):
    sf = SF2(path)
    errs = []
    if len(sf.presets) != 1:
        errs.append("presets=%d" % len(sf.presets))
    if len(sf.inst) - 1 != exp_inst:
        errs.append("inst=%d expected %d" % (len(sf.inst) - 1, exp_inst))
    if len(sf.shdr) - 1 != exp_samples:
        errs.append("samples=%d expected %d" % (len(sf.shdr) - 1, exp_samples))
    if sf.phdr[-1]["name"] != "EOP" or sf.inst[-1]["name"] != "EOI" or sf.shdr[-1]["name"] != "EOS":
        errs.append("terminal records")
    ni = len(sf.inst) - 1
    ns = len(sf.shdr) - 1
    if sf.phdr[-1]["bag"] != len(sf.pbag) - 1 or sf.inst[-1]["bag"] != len(sf.ibag) - 1:
        errs.append("bag terminal index")
    if sf.pbag[-1][0] != len(sf.pgen) - 1 or sf.pbag[-1][1] != len(sf.pmod) - 1:
        errs.append("pbag terminal")
    if sf.ibag[-1][0] != len(sf.igen) - 1 or sf.ibag[-1][1] != len(sf.imod) - 1:
        errs.append("ibag terminal")
    for op, amt in sf.pgen[:-1]:
        if op == GEN_INSTRUMENT and not 0 <= (amt & 0xFFFF) < ni:
            errs.append("pgen instrument out of range")
    for op, amt in sf.igen[:-1]:
        if op == GEN_SAMPLE_ID and not 0 <= (amt & 0xFFFF) < ns:
            errs.append("igen sample out of range")
    total = len(sf.smpl) // 2
    for si, s in enumerate(sf.shdr[:-1]):
        if not (s["start"] <= s["end"] <= total - SAMPLE_PAD):
            errs.append("sample bounds %s" % s["name"])
        if s["type"] & 0x0E and not 0 <= s["link"] < ns:
            errs.append("link out of range %s" % s["name"])
        if s["type"] & 0x0E and sf.shdr[s["link"]]["link"] != si:
            errs.append("link not reciprocal %s" % s["name"])
    if sf.sm24 is not None and len(sf.sm24) not in (total, total + 1):
        errs.append("sm24 size")
    return errs


if __name__ == "__main__":
    sf = SF2(sys.argv[1])
    print("presets", len(sf.presets), "inst", len(sf.inst) - 1, "samples", len(sf.shdr) - 1,
          "smpl", len(sf.smpl), "sm24", sf.sm24 is not None)
    for i, p in sorted(enumerate(sf.presets), key=lambda t: (t[1]["bank"], t[1]["preset"])):
        print("%03d:%03d %-20s inst=%s" % (p["bank"], p["preset"], p["name"], sf.preset_instruments(i)))
