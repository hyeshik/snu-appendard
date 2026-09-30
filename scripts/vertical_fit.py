"""Final uniform Hangul/Latin sizing and macOS-compatible vertical metrics.

Applied to the main family, without changing its name or release version.
"""
from __future__ import annotations

import copy
import json
import math
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from fontTools.misc.roundTools import otRound
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.scaleUpem import ScalerVisitor
from fontTools.ttLib.tables import otTables


# Coordinates use UPM 1000. Scale x and y equally to retain aspect ratio.
VERTICAL_FIT = {
    "hangul": {"scale": 1.0071513706793802, "dy": 9.432657926102479},
    "latin": {"scale": 0.987723485470458, "dy": 0.0},
}


def _vertical_is_hangul(cp):
    return any(a <= cp <= b for a, b in [(0x1100, 0x11ff), (0x3130, 0x318f),
               (0xa960, 0xa97f), (0xac00, 0xd7a3), (0xd7b0, 0xd7ff), (0xffa0, 0xffdc)])


def _vertical_hangul_glyphs(font):
    glyphs = {g for cp, g in font.getBestCmap().items() if _vertical_is_hangul(cp)}
    if 'GSUB' not in font:
        return glyphs
    while True:
        found = set()
        for lookup in font['GSUB'].table.LookupList.Lookup:
            for sub in lookup.SubTable:
                sub = getattr(sub, 'ExtSubTable', sub)
                for source, target in getattr(sub, 'mapping', {}).items():
                    if source in glyphs:
                        found.update([target] if isinstance(target, str) else target)
                for source, targets in getattr(sub, 'alternates', {}).items():
                    if source in glyphs:
                        found.update(targets)
                for first, ligatures in getattr(sub, 'ligatures', {}).items():
                    for ligature in ligatures:
                        if first in glyphs and all(g in glyphs for g in ligature.Component):
                            found.add(ligature.LigGlyph)
        found -= glyphs
        if not found:
            return glyphs
        glyphs.update(found)


def _vertical_walk(obj, seen=None):
    if seen is None:
        seen = set()
    if id(obj) in seen or isinstance(obj, (str, bytes, int, float, type(None))):
        return
    seen.add(id(obj))
    yield obj
    values = obj.values() if isinstance(obj, dict) else obj if isinstance(obj, (list, tuple)) else vars(obj).values() if hasattr(obj, '__dict__') else []
    for value in values:
        yield from _vertical_walk(value, seen)


def _vertical_scale_layout(font, hangul, fits):
    """Scale Latin layout and split mixed first-glyph classes in collision guards."""
    fit = fits['latin']
    scale, dy = fit['scale'], fit['dy']
    mixed_pairs = []
    for lookup in font['GPOS'].table.LookupList.Lookup:
        for sub in lookup.SubTable:
            sub = getattr(sub, 'ExtSubTable', sub)
            for key, value in vars(sub).items():
                if hasattr(value, 'glyphs'):
                    if set(value.glyphs) & hangul:
                        assert isinstance(sub,otTables.PairPos) and sub.Format == 2 and key == 'Coverage', ('unsupported Hangul positioning', key)
                        mixed_pairs.append((sub,copy.deepcopy(sub)))
            if hasattr(sub, 'PairSet'):
                for pairset in sub.PairSet:
                    for pair in pairset.PairValueRecord:
                        if pair.SecondGlyph in hangul and pair.Value2:
                            assert not any(vars(pair.Value2).values())
            if hasattr(sub, 'Class2Record'):
                raise AssertionError('Unexpected GPOS structure')
            if hasattr(sub, 'Class1Record'):
                classes = {sub.ClassDef2.classDefs.get(g, 0) for g in hangul}
                for row in sub.Class1Record:
                    for index in classes:
                        value = row.Class2Record[index].Value2
                        assert value is None or not any(vars(value).values())
    anchors = [(o, o.YCoordinate) for o in _vertical_walk(font['GPOS']) if isinstance(o, otTables.Anchor)]
    assert all(o.Format == 1 for o, _ in anchors)
    assert not any(isinstance(o, otTables.Device) for o in _vertical_walk(font['GPOS']))
    ScalerVisitor(scale).visit(font['GPOS'])
    for sub, original in mixed_pairs:
        groups = {}
        for glyph in original.Coverage.glyphs:
            key = (original.ClassDef1.classDefs.get(glyph,0), 'hangul' if glyph in hangul else 'latin')
            groups.setdefault(key,[]).append(glyph)
        sub.ClassDef1 = otTables.ClassDef()
        sub.ClassDef1.classDefs = {}
        sub.Class1Record = []
        for index, ((old_class,kind),glyphs) in enumerate(sorted(groups.items())):
            row = copy.deepcopy(original.Class1Record[old_class])
            for pair in row.Class2Record:
                if pair.Value1:
                    ScalerVisitor(fits[kind]['scale']).visit(pair.Value1)
                if pair.Value2:
                    ScalerVisitor(scale).visit(pair.Value2)
            sub.Class1Record.append(row)
            if index:
                sub.ClassDef1.classDefs.update(dict.fromkeys(glyphs,index))
        sub.Class1Count = len(sub.Class1Record)
    for anchor, old_y in anchors:
        anchor.YCoordinate = otRound(old_y * scale + dy)
    if 'GDEF' in font:
        caret = font['GDEF'].table.LigCaretList
        if caret:
            assert not set(caret.Coverage.glyphs) & hangul
        ScalerVisitor(scale).visit(font['GDEF'])


def _vertical_update_private(cff, fit):
    """Global hint zones describe the Latin; local glyph stems were transformed."""
    top = cff.topDictIndex[0]
    privates = [d.Private for d in top.FDArray] if hasattr(top, 'FDArray') else [top.Private]
    scale, dy = fit['scale'], fit['dy']
    for private in privates:
        for attr in ['BlueValues', 'OtherBlues', 'FamilyBlues', 'FamilyOtherBlues']:
            value = getattr(private, attr, None)
            if value:
                setattr(private, attr, [otRound(v*scale+dy) for v in value])
        for attr in ['StdHW', 'StdVW', 'StemSnapH', 'StemSnapV']:
            value = getattr(private, attr, None)
            if value is not None:
                setattr(private, attr, [otRound(v*scale) for v in value] if isinstance(value, list) else otRound(value*scale))
        if 'BlueScale' in private.rawDict:
            private.BlueScale /= scale


def _vertical_bounds(glyphs, name):
    pen = BoundsPen(glyphs)
    glyphs[name].draw(pen)
    return pen.bounds


def _transform_vertical_outlines(plan_path):
    import fontforge
    plan = json.loads(Path(plan_path).read_text())
    font = fontforge.open(plan['source'])
    if font.iscid:
        assert font.cidsubfontcnt == 1
        font.cidsubfont = 0
    order = plan['glyph_order']
    order_set = set(order)
    hangul = set(plan['hangul_glyphs'])
    seen = set()
    for glyph in font.glyphs():
        if font.iscid:
            name = '.notdef' if glyph.glyphname == '.notdef' else 'cid'+glyph.glyphname.rsplit('.',1)[1].zfill(5)
        else:
            gid = glyph.originalgid
            assert 0 <= gid < len(order), (glyph.glyphname, gid)
            name = order[gid]
        assert name in order_set and name not in seen, name
        seen.add(name)
        fit = plan['hangul'] if name in hangul else plan['latin']
        scale, dy = fit['scale'], fit['dy']
        width = glyph.width
        glyph.transform((scale, 0, 0, scale, 0, dy), ('round',))
        glyph.width = math.floor(width * scale + 0.5)
    assert seen == order_set
    font.generate(plan['outline_output'], flags=('opentype', 'round'))
    font.close()


def apply_vertical_fit(path):
    """Apply the adopted uniform script fit once, after all design/layout stages.

    Keep the main family identity and release version. The second FontForge
    export transforms CFF outlines and local hints; all other source tables
    stay in fontTools so cmap and GSUB are preserved exactly.
    """
    path = Path(path).resolve()
    with TemporaryDirectory(prefix='.vertical-fit-', dir=path.parent) as work:
        with TTFont(path, recalcTimestamp=False) as font:
            assert font['head'].unitsPerEm == 1000
            fit = VERTICAL_FIT
            hangul = _vertical_hangul_glyphs(font)
            intermediate = Path(work) / 'outlines.otf'
            plan = {'source': str(path), 'outline_output': str(intermediate),
                    'glyph_order': font.getGlyphOrder(),
                    'hangul_glyphs': sorted(hangul), **fit}
            plan_path = Path(work) / 'plan.json'
            plan_path.write_text(json.dumps(plan))
            worker = ("import runpy,sys; "
                      "runpy.run_path(sys.argv[1], run_name='vertical_worker')"
                      "['_transform_vertical_outlines'](sys.argv[2])")
            result = subprocess.run(
                ['fontforge', '-lang=py', '-c', worker,
                 str(Path(__file__).resolve()), str(plan_path)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            if result.returncode:
                raise RuntimeError(f"Outline fitting failed for {path}:\n{result.stdout}")
            _finish_vertical_fit(font, intermediate, path, hangul, fit)
            output = Path(work) / 'finished.otf'
            font.save(output)
        output.replace(path)


def _finish_vertical_fit(font, intermediate, path, hangul, fit):
    with TTFont(intermediate, recalcTimestamp=False) as outlines:
        assert set(outlines.getGlyphOrder()) == set(font.getGlyphOrder())
        assert outlines.getBestCmap() == font.getBestCmap()
        # Preserve source cmap and OpenType layout, avoiding a layout round-trip.
        original_glyphs = font.getGlyphSet()
        new_glyphs = outlines.getGlyphSet()
        for name in font.getGlyphOrder():
            transform = fit['hangul' if name in hangul else 'latin']
            s, dy = transform['scale'], transform['dy']
            assert outlines['hmtx'][name][0] == otRound(font['hmtx'][name][0]*s), name
            old, new = _vertical_bounds(original_glyphs, name), _vertical_bounds(new_glyphs, name)
            assert bool(old) == bool(new), name
            if old:
                expected = [old[0]*s, old[1]*s+dy, old[2]*s, old[3]*s+dy]
                error = max(abs(a-b) for a,b in zip(expected,new))
                assert error <= 1.01, (path.name, name, error)
                if 'vmtx' in font:
                    advance, tsb = font['vmtx'][name]
                    font['vmtx'][name] = advance, otRound(tsb+old[3]-new[3])
        old_cff = font['CFF '].cff
        old_top = old_cff.topDictIndex[0]
        new_cff = outlines['CFF '].cff
        new_top = new_cff.topDictIndex[0]
        # Only CFF and name-keyed hmtx are imported; preserve source glyph IDs.
        new_top.charset = font.getGlyphOrder()
        new_cff.fontNames = list(old_cff.fontNames)
        for attr in ('version', 'FamilyName', 'FullName', 'Weight', 'Notice',
                     'Copyright', 'CIDFontVersion'):
            if hasattr(old_top, attr):
                setattr(new_top, attr, getattr(old_top, attr))
        if hasattr(old_top, 'FDArray'):
            for old_fd, new_fd in zip(old_top.FDArray, new_top.FDArray):
                if hasattr(old_fd, 'FontName'):
                    new_fd.FontName = old_fd.FontName
        font['CFF '] = outlines['CFF ']
        font['hmtx'] = outlines['hmtx']
        _vertical_update_private(font['CFF '].cff, fit['latin'])
        _vertical_scale_layout(font, hangul, fit)
        hhea, os2 = font['hhea'], font['OS/2']
        hhea.ascent, hhea.descent, hhea.lineGap = 952, -241, 0
        os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap = 952, -241, 0
        os2.fsSelection |= 128
        os2.version = max(4, os2.version)
        bbox = font['CFF '].cff.topDictIndex[0].FontBBox
        os2.usWinAscent = max(os2.usWinAscent, math.ceil(bbox[3]), outlines['head'].yMax, 952)
        os2.usWinDescent = max(os2.usWinDescent, -math.floor(bbox[1]), -outlines['head'].yMin, 241)
        for attr in ['ySubscriptXSize','ySubscriptYSize','ySubscriptXOffset','ySubscriptYOffset',
                     'ySuperscriptXSize','ySuperscriptYSize','ySuperscriptXOffset','ySuperscriptYOffset',
                     'yStrikeoutSize']:
            setattr(os2, attr, otRound(getattr(os2,attr)*fit['latin']['scale']))
        os2.yStrikeoutPosition = otRound(os2.yStrikeoutPosition*fit['latin']['scale']+fit['latin']['dy'])
        cmap = font.getBestCmap()
        os2.sCapHeight = otRound(_vertical_bounds(new_glyphs,cmap[ord('H')])[3])
        os2.sxHeight = otRound(_vertical_bounds(new_glyphs,cmap[ord('x')])[3])
        os2.recalcAvgCharWidth(font)
        post = font['post']
        post.underlineThickness = otRound(post.underlineThickness*fit['latin']['scale'])
        post.underlinePosition = otRound(post.underlinePosition*fit['latin']['scale']+fit['latin']['dy'])
        top = font['CFF '].cff.topDictIndex[0]
        top.UnderlinePosition, top.UnderlineThickness = post.underlinePosition, post.underlineThickness
        if 'BASE' in font:
            axis = font['BASE'].table.HorizAxis
            if axis:
                tags = axis.BaseTagList.BaselineTag
                roman = tags.index('romn')
                for record in axis.BaseScriptList.BaseScriptRecord:
                    values = record.BaseScript.BaseValues
                    values.DefaultIndex = roman
                    for tag, coord in zip(tags, values.BaseCoord):
                        assert coord.Format == 1
                        coord.Coordinate = 0 if tag == 'romn' else otRound(coord.Coordinate*fit['hangul']['scale']+fit['hangul']['dy'])
