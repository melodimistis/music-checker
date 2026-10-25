#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 melodimistis
"""
music-checker.py

Sorts music files into one folder per album/single and tidies the .lrc lyric
files that belong to them. Written with the help of Claude (AI assistant by
Anthropic).

Setup (one time):
    pip install mutagen

Usage:
    python3 music-checker.py "/path/to/mixed/music"                 # DRY RUN: only shows the plan
    python3 music-checker.py "/path/to/mixed/music" --apply         # actually copies the files
    python3 music-checker.py "/path/to/mixed/music" -o "/path/out" --apply

Options:
    -o, --output      Destination folder. Default: "<source> - organized".
    --apply           Really copy the files. Without it nothing is touched (dry run).
    --romaji          For Japanese/Korean/Chinese songs: add the romanization in
                      parentheses under each lyric line. Only works when the original
                      .lrc already contains [x-romaji:...] data; nothing is generated.
    --split-artists   If two albums share a name but have different album artists,
                      split them into "Album Name (Artist)". Default: they are merged
                      and a warning is printed.
    --ext EXT         Treat an extra file extension as music (repeatable), e.g.
                      --ext .mp4 --ext .mka. Only useful if mutagen can read its tags.

Rules:
    1. Original files are NEVER modified or deleted. Everything is copied.
    2. Audio and .lrc file names are NEVER changed. Only the album folder name is new.
    3. Folder name = the ALBUM tag inside the audio file. Double spaces are cleaned up
       and characters that are not allowed in folder names (: / \\ | ? " < > *) are
       replaced or removed.
    4. A .lrc is paired with an audio file by identical file name (without extension).

Audio formats: every file whose extension is in AUDIO_EXTENSIONS is read through
mutagen. Tested: FLAC, MP3, M4A (AAC), Ogg Vorbis, Opus, WMA, AIFF, WAV, WavPack.
The remaining formats in the list (APE, MPC, TTA, TAK, OptimFROG, DSF, DSDIFF,
Speex, MP2) are handled by mutagen but have not been tested here.
"""
import argparse
import base64
import codecs
import collections
import os
import re
import shutil
import sys
import unicodedata

try:
    import mutagen
except ImportError:
    sys.exit("The 'mutagen' library is not installed. Install it with:  pip install mutagen")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

NO_ALBUM = "_without album"
ORPHAN_LRC = "_LRC without audio"

AUDIO_EXTENSIONS = {
    ".flac", ".mp3", ".mp2", ".m4a", ".m4b", ".ogg", ".oga", ".opus", ".spx",
    ".wma", ".wav", ".aiff", ".aif", ".aifc", ".ape", ".wv", ".mpc", ".tta",
    ".tak", ".ofr", ".dsf", ".dff",
}

FIELD_KEYS = {
    "album": ("album", "wm/albumtitle", "talb", "album title"),
    "albumartist": ("albumartist", "album_artist", "album artist", "wm/albumartist", "tpe2"),
    "artist": ("artist", "author", "tpe1"),
    "track": ("tracknumber", "track", "wm/tracknumber", "trck"),
    "total": ("tracktotal", "totaltracks", "track_total", "totaltrack"),
    "disc": ("discnumber", "disc", "wm/partofset", "tpos"),
}


# helpers
def norm_key(s):
    """Matching key: ignores case, repeated spaces and curly quotes/apostrophes."""
    s = unicodedata.normalize("NFC", s)
    s = s.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", s).strip().casefold()


def clean_folder(name):
    """Turn a tag value into a safe folder name."""
    name = unicodedata.normalize("NFC", name)
    name = re.sub(r"[\x00-\x1f]", "", name)
    name = re.sub(r"\s*[:/\\|]\s*", " - ", name)
    name = re.sub(r'[<>"?*]', "", name)
    name = re.sub(r"\s+", " ", name).strip().rstrip(". ")
    return name or NO_ALBUM


def to_int(s):
    m = re.match(r"\d+", s or "")
    return int(m.group()) if m else None


def plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


# tag reading
def value_to_text(v):
    """Convert whatever a tag container returns (list, tuple, frame, attribute) to a string."""
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        if not v:
            return ""
        if isinstance(v, tuple) and all(isinstance(x, int) for x in v):
            return "/".join(str(x) for x in v if x)
        return value_to_text(v[0])
    frame_text = getattr(v, "text", None)
    if isinstance(frame_text, list):
        return value_to_text(frame_text[0]) if frame_text else ""
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace").strip()
    return str(v).strip()


def read_tags(path):
    """Return ({field: text}, error_or_None) for any audio format mutagen understands."""
    result = {field: "" for field in FIELD_KEYS}
    try:
        audio = mutagen.File(path, easy=True) or mutagen.File(path)
    except Exception as exc:
        return result, f"{type(exc).__name__}: {exc}"
    if audio is None:
        return result, "format not recognised by mutagen"
    tags = getattr(audio, "tags", None)
    if not tags:
        return result, None
    lowered = {}
    try:
        for key, value in tags.items():
            lowered.setdefault(str(key).lower(), value)
    except Exception as exc:
        return result, f"could not read tags ({type(exc).__name__}: {exc})"
    for field, names in FIELD_KEYS.items():
        for name in names:
            if name in lowered:
                text = value_to_text(lowered[name])
                if text:
                    result[field] = text
                    break
    return result, None


# lrc tidying
LEADING_STAMPS = re.compile(r"^((?:\[\d+:\d+(?:[.:]\d+)?\])+)(.*)$")
STAMP = re.compile(r"\[(\d+):(\d+(?:[.:]\d+)?)\]")
WORD_STAMP = re.compile(r"<\d+:\d+(?:\.\d+)?>")
NON_LATIN = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]")


def stamp_to_ms(minutes, seconds):
    return int(round((int(minutes) * 60 + float(seconds.replace(":", "."))) * 1000))


def format_stamp(ms):
    cs = (ms + 5) // 10
    return f"[{cs // 6000:02d}:{(cs // 100) % 60:02d}.{cs % 100:02d}]"


def read_lrc_text(path):
    """Return (text, issue). issue is None, 'utf16' or 'invalid-utf8'."""
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return raw.decode("utf-16", errors="replace"), "utf16"
    try:
        return raw.decode("utf-8-sig"), None
    except UnicodeDecodeError:
        return raw.decode("utf-8-sig", errors="replace"), "invalid-utf8"


def tidy_lrc(text, romaji=False):
    """Return (new_text, info).

    Removes v1:/v2: labels, per-word timestamps, source tags ([by:], [x-...]) and
    [bg:...] lines, expands lines carrying several timestamps, normalizes timestamps
    to [mm:ss.xx] and sorts by time. Lyrics without any timestamp are kept as they are.
    """
    head, lines, plain, romanized = [], [], [], {}
    info = {"bg": 0, "unsynced": False}
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if re.match(r"^\[(ti|ar|al|offset):", s):
            head.append(s)
            continue
        if s.startswith("[bg"):
            info["bg"] += 1
            continue
        m = re.match(r"^\[x-romaji:(\d+):(.*)\]$", s)
        if m:
            try:
                romanized[int(m.group(1))] = base64.b64decode(m.group(2)).decode("utf-8").strip()
            except Exception:
                pass
            continue
        if re.match(r"^\[[A-Za-z][\w-]*:", s):
            continue
        m = LEADING_STAMPS.match(s)
        if not m:
            plain.append(s)
            continue
        lyric = WORD_STAMP.sub("", m.group(2))
        lyric = re.sub(r"^\s*v\d+:\s*", "", lyric)
        lyric = re.sub(r"\s+", " ", lyric).strip()
        if lyric:
            for minutes, seconds in STAMP.findall(m.group(1)):
                lines.append((stamp_to_ms(minutes, seconds), lyric))
    lines.sort(key=lambda item: item[0])
    if not lines and plain:
        info["unsynced"] = True
        body = plain
    else:
        body, used = [], set()
        for ms, lyric in lines:
            body.append(format_stamp(ms) + lyric)
            if romaji and NON_LATIN.search(lyric):
                candidates = [k for k in romanized if k not in used and abs(k - ms) <= 60]
                if candidates:
                    best = min(candidates, key=lambda k: abs(k - ms))
                    used.add(best)
                    body.append(f"{format_stamp(ms)} ({romanized[best]})")
    return "\n".join(head + body) + "\n", info


# main
def main():
    ap = argparse.ArgumentParser(
        description="Sort music files into one folder per album/single and tidy their .lrc lyrics.")
    ap.add_argument("source", help="folder with the mixed music files (searched recursively)")
    ap.add_argument("-o", "--output", help='destination folder (default: "<source> - organized")')
    ap.add_argument("--apply", action="store_true", help="really copy the files (without it: dry run)")
    ap.add_argument("--romaji", action="store_true",
                    help="add romanization in parentheses below non-Latin lyric lines (needs [x-romaji] data)")
    ap.add_argument("--split-artists", action="store_true",
                    help="split albums that share a name but have different album artists")
    ap.add_argument("--ext", action="append", default=[], metavar="EXT",
                    help="extra audio extension to treat as music, e.g. --ext .mp4 (repeatable)")
    args = ap.parse_args()

    src = os.path.abspath(args.source)
    if not os.path.isdir(src):
        sys.exit(f"Source folder not found: {src}")
    if args.output:
        out = os.path.abspath(args.output)
    else:
        out = os.path.join(os.path.dirname(src), (os.path.basename(src) or "music") + " - organized")
    if out == src:
        sys.exit("The output folder must be different from the source folder.")

    audio_exts = set(AUDIO_EXTENSIONS)
    for e in args.ext:
        e = e.strip().lower()
        if e:
            audio_exts.add(e if e.startswith(".") else "." + e)

    # scan
    audio, lrcs, ignored = [], [], collections.Counter()
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if os.path.abspath(os.path.join(root, d)) != out]
        for fn in sorted(files):
            path = os.path.join(root, fn)
            stem, ext = os.path.splitext(fn)
            ext = ext.lower()
            if ext in audio_exts:
                audio.append({"path": path, "name": fn, "stem": stem, "dir": root, "ext": ext})
            elif ext == ".lrc":
                lrcs.append({"path": path, "name": fn, "stem": stem, "dir": root, "used": False})
            else:
                ignored[ext or "(no extension)"] += 1

    if not audio and not lrcs:
        print(f"No audio or .lrc files found in: {src}")
        return

    # read tags
    problems = []
    for item in audio:
        tags, error = read_tags(item["path"])
        if error:
            problems.append(f"Could not read tags: {item['name']} ({error})")
        item["folder"] = clean_folder(tags["album"]) if tags["album"] else NO_ALBUM
        item["album_artist"] = tags["albumartist"] or tags["artist"]
        item["track"] = to_int(tags["track"])
        m = re.match(r"\d+\s*/\s*(\d+)", tags["track"])
        item["total"] = to_int(tags["total"]) or (int(m.group(1)) if m else None)
        item["disc"] = to_int(tags["disc"]) or 1

    # unify folder spelling, handle same album name with different album artists
    warn_artist = []
    groups = collections.defaultdict(list)
    for item in audio:
        groups[norm_key(item["folder"])].append(item)
    for members in groups.values():
        spelling = collections.Counter(i["folder"] for i in members).most_common(1)[0][0]
        artists = {norm_key(i["album_artist"]) for i in members if i["album_artist"]}
        if len(artists) > 1 and spelling != NO_ALBUM:
            warn_artist.append((spelling, sorted({i["album_artist"] for i in members})))
            if args.split_artists:
                for i in members:
                    who = clean_folder(i["album_artist"]) if i["album_artist"] else "no artist"
                    i["folder"] = f"{spelling} ({who})"
                continue
        for i in members:
            i["folder"] = spelling

    # pair .lrc with audio by file name
    by_name = collections.defaultdict(list)
    for l in lrcs:
        by_name[norm_key(l["stem"])].append(l)
    ambiguous, no_lrc = [], []
    for item in audio:
        candidates = by_name.get(norm_key(item["stem"]), [])
        exact = [c for c in candidates if c["stem"] == item["stem"]]
        pool = exact or candidates
        same_dir = [c for c in pool if c["dir"] == item["dir"]]
        picked = same_dir or pool
        item["lrcs"] = picked
        if not picked:
            no_lrc.append(item["name"])
        elif len(picked) > 1:
            ambiguous.append(item["name"])
        for c in picked:
            c["used"] = True
    orphans = [l for l in lrcs if not l["used"]]

    # build the copy plan
    plan, collisions = [], []
    planned = {}

    def add(kind, source_path, folder, name):
        key = (norm_key(folder), norm_key(name))
        if key in planned:
            if planned[key] != source_path:
                collisions.append(f"{folder}/{name}  <- {source_path}")
            return
        planned[key] = source_path
        plan.append((kind, source_path, folder, name))

    for item in audio:
        add("audio", item["path"], item["folder"], item["name"])
        for c in item["lrcs"]:
            add("lrc", c["path"], item["folder"], c["name"])
    for l in orphans:
        add("lrc", l["path"], ORPHAN_LRC, l["name"])

    # report
    albums = collections.OrderedDict()
    for item in sorted(audio, key=lambda x: (norm_key(x["folder"]), x["disc"], x["track"] or 0)):
        albums.setdefault(item["folder"], []).append(item)

    formats = collections.Counter(i["ext"] for i in audio)
    report = [
        f"Source : {src}",
        f"Output : {out}",
        f"Mode   : {'COPY (--apply)' if args.apply else 'DRY RUN (no files touched)'}",
        "",
        f"Found: {plural(len(audio), 'audio file')}, {plural(len(lrcs), 'LRC file')}",
    ]
    if formats:
        report.append("Formats: " + ", ".join(f"{ext} {n}" for ext, n in sorted(formats.items())))
    if ignored:
        report.append(f"Ignored: {dict(ignored)}")
    report += ["", "== ALBUMS / SINGLES =="]
    for folder, members in albums.items():
        numbered = {(i["disc"], i["track"]) for i in members if i["track"]}
        distinct = len(numbered) + sum(1 for i in members if not i["track"])
        total = max([i["total"] for i in members if i["total"]] or [0])
        text = f"  {folder}: {plural(distinct, 'track')}"
        if distinct != len(members):
            text += f" ({plural(len(members), 'file')})"
        if total:
            text += f" of {total}"
            if len({i["disc"] for i in members}) == 1:
                missing = sorted(set(range(1, total + 1)) - {n for _, n in numbered})
                if missing:
                    shown = ", ".join(map(str, missing[:10]))
                    if len(missing) > 10:
                        shown += f" (+{len(missing) - 10} more)"
                    text += f"  | missing no. {shown}"
        report.append(text)
    if no_lrc:
        report += ["", f"== AUDIO WITHOUT LRC ({len(no_lrc)}) =="] + [f"  {n}" for n in no_lrc]
    if orphans:
        report += ["", f"== LRC WITHOUT MATCHING AUDIO ({len(orphans)}) -> folder '{ORPHAN_LRC}' =="]
        report += [f"  {l['name']}" for l in orphans]
    if warn_artist:
        report += ["", "== WARNING: same album name, different album artists =="]
        report += [f"  {name}: {', '.join(artists)}" for name, artists in warn_artist]
        if not args.split_artists:
            report.append("  (merged. Run with --split-artists to separate them)")
    if ambiguous:
        report += ["", "== More than one LRC matches these audio files (all of them are copied) =="]
        report += [f"  {n}" for n in ambiguous]
    if collisions:
        report += ["", "== SKIPPED: name collision in the destination folder =="]
        report += [f"  {c}" for c in collisions]
    if problems:
        report += ["", "== PROBLEMS =="] + [f"  {p}" for p in problems]

    # copy
    if args.apply:
        notes = []
        os.makedirs(out, exist_ok=True)
        for kind, source_path, folder, name in plan:
            dest_dir = os.path.join(out, folder)
            os.makedirs(dest_dir, exist_ok=True)
            dest = os.path.join(dest_dir, name)
            if kind == "audio":
                shutil.copy2(source_path, dest)
                continue
            text, issue = read_lrc_text(source_path)
            new_text, info = tidy_lrc(text, romaji=args.romaji)
            with open(dest, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(new_text)
            if info["bg"]:
                notes.append(f"  {name}: {plural(info['bg'], '[bg] backing-vocal line')} removed")
            if info["unsynced"]:
                notes.append(f"  {name}: lyrics have NO timestamps (left as they are)")
            if issue == "utf16":
                notes.append(f"  {name}: was UTF-16, converted to UTF-8")
            elif issue == "invalid-utf8":
                notes.append(f"  {name}: not valid UTF-8, some characters may be damaged (check the original encoding)")
        if notes:
            report += ["", "== LRC NOTES =="] + notes
        with open(os.path.join(out, "report.txt"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(report) + "\n")

    print("\n".join(report))
    if not args.apply:
        print("\nThis is only a plan. If it looks right, run again with --apply")


if __name__ == "__main__":
    main()
