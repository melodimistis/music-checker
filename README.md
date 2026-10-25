# music-checker

![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)
![Python](https://img.shields.io/badge/Python-3-informational.svg)

A Python script that **sorts your music files into one folder per album/single** and **tidies the `.lrc` lyric files** that go with them.

It is made for libraries where everything ended up in one big folder (downloads, rips, exports) and you want the result to look like this: one album, one folder, songs and their lyrics side by side!.

> [!WARNING]
> **Testing status, please read.**
> The script reads tags through [mutagen](https://mutagen.readthedocs.io/), so it can handle many audio formats, but not all of them have been tested:
>
> - **Tested on generated sample files:** FLAC, MP3, M4A (AAC), Ogg Vorbis, Opus, WMA, AIFF, WAV (with ID3 tags), WavPack.
> - **Tested on a real library:** FLAC + `.lrc` only (about 250 files from a single artist). Multi-format behavior has so far only been checked on small, generated test sets.
> - **Handled by mutagen but never tested here:** APE, MPC, TTA, TAK, OptimFROG, DSF, DSDIFF, Speex, MP2.
> - **Not supported:** formats mutagen cannot tag (AC3, Matroska/`.mka`, ...). Without an `ALBUM` tag there is nothing to sort by.
> - **Operating system:** tested on Linux only.

---

## Table of contents

- [What it does](#what-it-does)
- [Principles](#principles)
- [Requirements & installation](#requirements--installation)
- [Usage](#usage)
- [Examples](#examples)
- [How it works](#how-it-works)
- [Reading the report](#reading-the-report)
- [Limitations](#limitations)
- [Troubleshooting](#troubleshooting)
- [Ideas for the future](#ideas-for-the-future)
- [Contributing](#contributing)
- [Copyright note](#copyright-note)
- [License](#license)

---

## What it does

1. **Reads the `ALBUM` tag of every audio file** and creates one folder per album or single.
2. **Pairs each `.lrc` file with its song** by file name and puts it in the same folder.
3. **Tidies the contents of the `.lrc` files**: removes labels and tags that are not lyrics and normalizes the timestamps.
4. **Writes a report**: albums found, how many tracks you have compared to how many the tag says there should be, songs without lyrics, lyrics without songs, and warnings.
5. _(Optional)_ **Adds romanization** under Japanese/Korean/Chinese lyric lines, if the original `.lrc` already contains romanization data.

## Principles

- **Your original files are never modified or deleted.** Everything is _copied_ to a new folder.
- **File names are never changed.** Spaces, brackets, apostrophes, upper/lower case: all kept exactly as they are. The only names the script creates are **album folder names**.
- **Dry run by default.** Without `--apply` the script only prints a plan and touches nothing.
- **No guessing.** Songs without an album tag go to `_without album`; lyrics without a matching song go to `_LRC without audio`, so you can check them yourself.

---

## Requirements & installation

- Python 3 (tested with Python 3.12)
- [`mutagen`](https://mutagen.readthedocs.io/) to read tags (tested with versions 1.46 to 1.48)

Get the script:

```bash
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>
```

Install `mutagen`. Pick **one** way:

**a. From your distribution's packages (Debian/Ubuntu/Mint, easiest on recent systems)**

```bash
sudo apt install python3-mutagen
```

**b. In a virtual environment (works everywhere)**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install mutagen
```

> If plain `pip install mutagen` fails with `error: externally-managed-environment`, that is normal on modern Linux distributions. Use (a) or (b).

> Windows and macOS have not been tested. The script only uses the Python standard library plus `mutagen`, so it should work, but there is no confirmation yet.

---

## Usage

```bash
python3 music-checker.py "<source-folder>" [options]
```

**Recommended workflow:**

```bash
# 1) DRY RUN: prints the plan, touches nothing
python3 music-checker.py "/home/user/Music/mixed"

# 2) If the plan looks right, copy for real
python3 music-checker.py "/home/user/Music/mixed" --apply
```

The result goes into a new folder next to the source, named **`<source-folder> - organized`**. After `--apply`, the full report is also saved as `report.txt` inside that folder.

### Options

| Option            | What it does                                                                                                                                                                                               |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `-o`, `--output`  | Choose the destination folder. Default: `<source-folder> - organized`.                                                                                                                                     |
| `--apply`         | Actually copy the files. Without it, nothing is touched (dry run).                                                                                                                                         |
| `--romaji`        | For Japanese/Korean/Chinese songs: add the romanization in parentheses below each lyric line. Only works if the original `.lrc` already has `[x-romaji:...]` data (see [romaji example](#romaji-example)). |
| `--split-artists` | If two albums share a name but have different album artists, split them into `Album Name (Artist)`. Default: they are merged and a warning is printed.                                                     |
| `--ext EXT`       | Treat an extra file extension as music, e.g. `--ext .mp4`. Can be repeated. Only useful if mutagen can read tags from that format.                                                                         |

Example combining options:

```bash
python3 music-checker.py "/home/user/Music/mixed" -o "/home/user/Music/Sorted" --apply --romaji
```

Supported audio extensions by default: `.flac .mp3 .mp2 .m4a .m4b .ogg .oga .opus .spx .wma .wav .aiff .aif .aifc .ape .wv .mpc .tta .tak .ofr .dsf .dff` (see the testing status above for what has actually been verified). `.mp4` is deliberately not included so video files are not treated as music.

> **Tip:** paths that contain spaces **must** be quoted. In many Linux terminals you can also drag the folder from your file manager into the terminal window to fill in the path.

> **Tip:** if your music is on a memory card, copy it to your computer's disk first and run the script from there. It is much faster, and the card stays untouched as a backup.

---

## Examples

### Folder structure

Before (everything in one folder, mixed formats):

```
Music/mixed/
├── Song One - Artist A.flac
├── Song One - Artist A.lrc
├── Song Two - Artist A.mp3
├── Song Two - Artist A.lrc
├── Song Three - Artist B.m4a
├── Song Three - Artist B.lrc
└── Song Four - Artist B.flac
```

After (`--apply`):

```
Music/mixed - organized/
├── First Album/
│   ├── Song One - Artist A.flac
│   ├── Song One - Artist A.lrc
│   ├── Song Two - Artist A.mp3
│   └── Song Two - Artist A.lrc
├── Some Single - Single/
│   ├── Song Three - Artist B.m4a
│   └── Song Three - Artist B.lrc
├── _without album/
│   └── Song Four - Artist B.flac
└── report.txt
```

Folder names come from each file's `ALBUM` tag. In this example `Song Four` has no album tag, so it lands in `_without album`.

### `.lrc` before and after

`.lrc` files from some sources carry labels and tags that are not lyrics. Example (made-up text, not real lyrics):

Before:

```
[ti:Song Title]
[ar:Artist Name]
[by:Source Name (source: some-lyrics-site)]

[00:12.340]v1: <00:12.340>This <00:12.710>is <00:13.050>line <00:13.480>one
[00:16.9]v1: <00:16.900>This <00:17.250>is <00:17.600>line <00:17.900>two
[00:30.00][01:10.00]This line repeats
[bg:<00:18.100>(background vocal)<00:18.900>]
```

After:

```
[ti:Song Title]
[ar:Artist Name]
[00:12.34]This is line one
[00:16.90]This is line two
[00:30.00]This line repeats
[01:10.00]This line repeats
```

What happened:

- `v1:` / `v2:` labels at the start of a line were removed.
- Per-word timestamps (`<mm:ss.xxx>`) were removed; only the timestamp at the start of the line is kept.
- Every tag except `[ti:]`, `[ar:]`, `[al:]` and `[offset:]` was removed (for example `[by:]`, `[x-translation:]`, `[x-romaji-words:]`).
- `[bg:...]` (background vocal) lines were removed. See [limitations](#limitations).
- Lines with several timestamps (`[00:30.00][01:10.00]...`) were expanded into separate lines. The alternative format `[mm:ss:xx]` is also understood.
- Timestamps were normalized to `[mm:ss.xx]` (two digits after the dot), lines were sorted by time, empty lines were dropped, and the file was saved as UTF-8 with `LF` line endings.

Encoding is handled too: UTF-16 files are converted to UTF-8, and files that are not valid UTF-8 are flagged in the report, because some characters may already be damaged in the original.

### Romaji example

Some `.lrc` sources include romanization in a non-standard tag, `[x-romaji:<milliseconds>:<base64 text>]`. Without `--romaji` that tag is simply removed. With `--romaji`, each lyric line that contains Japanese, Korean or Chinese characters and has matching romaji data gets a second line with the same timestamp, in parentheses (made-up text):

```
[00:17.47]こんにちは、世界
[00:17.47] (konnichiwa, sekai)
```

Why parentheses? Some players merge lines that share a timestamp into one line. With the parentheses, the merged result is still easy to read:

```
こんにちは、世界 (konnichiwa, sekai)
```

> The script **does not generate romanization itself**. If the original `.lrc` has no `x-romaji` data, nothing is added.

### Example report

```
Source : /home/user/Music/mixed
Output : /home/user/Music/mixed - organized
Mode   : DRY RUN (no files touched)

Found: 10 audio files, 10 LRC files
Formats: .flac 7, .m4a 2, .mp3 1
Ignored: {'.jpg': 2}

== ALBUMS / SINGLES ==
  First Album: 8 tracks of 10  | missing no. 4, 9
  Some Single - Single: 1 track of 1
  _without album: 1 track

== AUDIO WITHOUT LRC (1) ==
  Song Four - Artist B.flac

== LRC WITHOUT MATCHING AUDIO (1) -> folder '_LRC without audio' ==
  Song Five - Artist C.lrc

This is only a plan. If it looks right, run again with --apply
```

---

## How it works

### Choosing the album folder

- Folder name = the **`ALBUM`** tag inside the audio file (not a guess from the file name). Different formats store it under different names (`album`, `WM/AlbumTitle`, `TALB`, ...); the script knows the common ones.
- Repeated spaces are cleaned up (`Title  - EP` becomes `Title - EP`).
- Characters that are not allowed in folder names are replaced or removed, **in the folder name only** (file names stay untouched): `:` `/` `\` `|` become `-`; `<` `>` `"` `?` `*` are removed; trailing dots and spaces are removed.
- Album names that differ only by upper/lower case, repeated spaces or the kind of apostrophe are merged under the most common spelling.
- No album tag (or unreadable tags) → folder `_without album`.

### Pairing `.lrc` files with audio files

The pairing uses the **file name without extension**, with this priority:

1. A name that is **exactly identical** (case included). This matters because different editions of a song can have names that differ only by case (`Song In Title` vs `Song in Title`).
2. Otherwise, a name that matches once case, repeated spaces and curly apostrophes are ignored.
3. If several candidates remain, the one in the **same source folder** as the audio file wins.
4. If it is still ambiguous, the `.lrc` is copied next to every matching audio file and listed in the report.

If two audio files share one lyric file (for example `song.flac` and `song.mp3` with a single `song.lrc`), the lyric is copied once into their folder.

`.lrc` files do not contain album information, so their destination always follows the audio file they are paired with.

### Completeness check

From the `TRACKNUMBER` tag (for example `3/12`) or `TRACKTOTAL`/`TOTALTRACKS`, the script works out how many tracks the album should have and reports `N tracks of M | missing no. ...`. At most 10 missing numbers are listed. If you hold the same track in two formats, it is counted once and shown as `1 track (2 files)`. The missing-number check only runs for single-disc albums.

---

## Reading the report

| Section                                             | Meaning                                                                                                                                         |
| --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `ALBUMS / SINGLES`                                  | The folders that will be created, how many tracks were found compared to the tag, and which track numbers are missing.                          |
| `AUDIO WITHOUT LRC`                                 | Songs that have no lyric file. Informational only.                                                                                              |
| `LRC WITHOUT MATCHING AUDIO`                        | Lyrics whose song was not found. Copied to `_LRC without audio` for you to check by hand.                                                       |
| `WARNING: same album name, different album artists` | Two different albums may have been merged just because they share a name (for example "Greatest Hits"). Use `--split-artists` to separate them. |
| `More than one LRC matches these audio files`       | A song matched several lyric files because of ambiguous names.                                                                                  |
| `SKIPPED: name collision`                           | Two different files would end up with the same name in the same folder; one of them was skipped.                                                |
| `PROBLEMS`                                          | Files whose tags could not be read. They are still copied, into `_without album`.                                                               |
| `LRC NOTES`                                         | Shown after `--apply`: lyrics whose `[bg]` lines were removed, lyrics without timestamps, and encoding conversions or problems.                 |

**About "missing no." numbers:** they do not always mean a song is missing. In one source folder a song usually exists as a single file, so a song that appears on several editions (standard and deluxe, for instance) only goes into one folder, according to the album tag inside that file. A song that was also released as a single may carry a `... - Single` album tag and land in its own single folder instead. The albums that are only one or two tracks short are the ones most worth checking.

---

## Limitations

- **Only audio and `.lrc` files are copied.** Cover images, `.cue`, `.log` and any other files are ignored and **not** copied to the output folder.
- **Results depend on tag quality.** An empty or misspelled album tag sends a song to `_without album` or splits an album into two folders with similar names. Fix the tags first (for example with MusicBrainz Picard or Mp3tag), then run again.
- **Background vocals (`[bg:...]`) are dropped.** In the original files these lines have no line timestamp, and adding them as separate lines could overwrite the main lyric on players that show only one line. Text in parentheses that is already part of a main lyric line is kept.
- **Lyrics without timestamps are not synchronized.** If a `.lrc` contains only plain text, it is kept as it is (only source tags are removed) and noted in the report. The script never invents timings.
- **No "skip existing" mode.** Running `--apply` a second time into the same output folder copies every audio file again (it overwrites the same files; it does not create duplicates, but it takes time).
- **Needs extra disk space.** Because it copies, you need roughly as much free space as the size of the library until you delete the originals yourself.
- **The missing-number check only covers single-disc albums.**
- **Romanization is never generated**, only reused from `x-romaji` data that already exists in the `.lrc`.
- **Formats without tag support** (AC3, Matroska, ...) cannot be sorted.
- **Pairing is by file name only.** If the audio and `.lrc` names differ, they will not be paired.
- **Scale and platforms:** the real-world test was a single-artist FLAC library of about 250 tracks, on Linux. Behavior on much larger or more varied collections (many artists, compilations, mixed formats) is untested. Always run a dry run first and read the report.

---

## Troubleshooting

**`The 'mutagen' library is not installed`**
Install `mutagen` (see [installation](#requirements--installation)). If it is installed but you still see this, the `python3` you run may differ from the one that has `mutagen`. Check with:

```bash
python3 -c "import mutagen; print(mutagen.version_string)"
```

**`error: externally-managed-environment`**
This is a protection in modern Linux distributions against global `pip` installs. Use `apt install python3-mutagen` or a virtual environment.

**`can't open file '.../music-checker.py': No such file or directory`**
The script is not in the folder you ran the command from, or the name is mistyped. Use the full path, for example `python3 ~/Downloads/music-checker.py "..."`.

**`Source folder not found`**
Check the path, and quote it if it contains spaces. Do not add single quotes inside the path (`'Folder Name'`); they would be read as part of the folder name.

**`The output folder must be different from the source folder`**
Pick another folder with `-o`.

**`Could not read tags: ... (format not recognised by mutagen)`**
The file is damaged, not really an audio file, or in a format mutagen cannot open. It is copied to `_without album`.

**Japanese/Korean characters look like boxes or question marks in the terminal**
That is a terminal font/encoding issue, not a problem with the files. Output files are always written as UTF-8.

**Lyrics do not show up in my music player**
Make sure the `.lrc` has exactly the same name as the audio file (apart from the extension) and sits in the same folder, then rescan your music library. Players differ in how they handle `.lrc`: some cannot display non-Latin text, and some merge lines that share a timestamp (which is why romaji is wrapped in parentheses).

---

## Ideas for the future

These are **ideas, not existing features**:

- A "skip files that already exist" mode so re-running does not copy everything again.
- An option to include `[bg]` backing vocals in some form.
- A `--move` option as an alternative to copying.
- Copying cover art and other side files into the album folders.
- Completeness checks for multi-disc albums.
- Pairing `.lrc` files by tags (title/artist) when the file names differ.
- Automated tests, and confirmed Windows/macOS support.

## Contributing

Issues and pull requests are welcome. When reporting a problem, please include:

- the relevant part of the dry-run output or `report.txt`,
- example **file names** (without uploading the music files themselves),
- your Python and `mutagen` versions, and your operating system.

## Copyright note

Music and lyrics are generally protected by copyright. This script only processes files that **you already own** on your own computer. **Please do not upload music or lyric files to this repository**, not even as bug-report examples; use made-up text or just file names.

## License

This program is free software: you can redistribute it and/or modify it under the terms of the **GNU General Public License** as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but **WITHOUT ANY WARRANTY**; without even the implied warranty of **MERCHANTABILITY** or **FITNESS FOR A PARTICULAR PURPOSE**. See the [LICENSE](LICENSE) file and <https://www.gnu.org/licenses/gpl-3.0.html> for details.

The `mutagen` dependency is licensed under GPL-2.0-or-later, which is compatible with GPL-3.0-or-later.

Copyright (C) 2026 melodimistis
