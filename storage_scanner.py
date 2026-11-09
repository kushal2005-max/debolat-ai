"""
Debolat AI - Storage Scanner

Real disk data, with honest accounting:
- get_drives()          : every fixed drive with total / used / free (instant).
- scan_children(path)   : EVERY subfolder and file directly inside `path`,
                          with full recursive sizes, computed in parallel.
                          Used for the first level of a drive and for
                          drill-down into any folder.
- scan_top_level_folders: older helper, kept for compatibility.

Every function counts what it could NOT read (`denied`) so the UI can say
"X folders were not readable" instead of implying it saw everything.

Performance: os.scandir (no extra stat per file) + a thread pool across
sibling folders, since the work is I/O-bound.

Correctness on Windows:
- Symlinks AND junction points / reparse points are skipped. Junctions like
  "Application Data" point back up the tree and would otherwise be counted
  twice (or loop forever).
- OneDrive "online-only" placeholder files report their full size but take
  no disk space, so they are skipped and counted separately.
"""

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import psutil

FILE_ATTRIBUTE_REPARSE_POINT = 0x400
FILE_ATTRIBUTE_OFFLINE = 0x1000
FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x40000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x400000
_CLOUD_ONLY = (FILE_ATTRIBUTE_OFFLINE | FILE_ATTRIBUTE_RECALL_ON_OPEN
               | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS)


def _scan_dir(path):
    """Recursive size of `path`. Returns (size_bytes, denied_count, cloud_only_count)."""
    total = 0
    denied = 0
    cloud = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if entry.is_symlink():
                        continue
                    st = entry.stat(follow_symlinks=False)
                    attrs = getattr(st, "st_file_attributes", 0)
                    if attrs & FILE_ATTRIBUTE_REPARSE_POINT:
                        continue  # junction / mount point / other reparse point
                    if entry.is_dir(follow_symlinks=False):
                        s, d, c = _scan_dir(entry.path)
                        total += s
                        denied += d
                        cloud += c
                    elif attrs & _CLOUD_ONLY:
                        cloud += 1
                    else:
                        total += st.st_size
                except OSError:
                    denied += 1
    except OSError:
        denied += 1
    return total, denied, cloud


def get_folder_size(path):
    """Recursive size in bytes (kept for compatibility)."""
    return _scan_dir(path)[0]


def get_drives():
    """All fixed drives: mountpoint, total/used/free in GB."""
    drives = []
    for part in psutil.disk_partitions(all=False):
        opts = (part.opts or "").lower()
        if "cdrom" in opts or "removable" in opts or not part.fstype:
            continue
        try:
            u = psutil.disk_usage(part.mountpoint)
        except OSError:
            continue
        drives.append({
            "mountpoint": part.mountpoint,
            "total_gb": round(u.total / (1024 ** 3), 2),
            "used_gb": round(u.used / (1024 ** 3), 2),
            "free_gb": round(u.free / (1024 ** 3), 2),
            "percent_used": u.percent,
        })
    return drives


def _split_dir(path):
    """One directory level: returns (file_bytes, denied, cloud, subdir_paths)."""
    file_bytes = 0
    denied = 0
    cloud = 0
    subdirs = []
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if entry.is_symlink():
                        continue
                    st = entry.stat(follow_symlinks=False)
                    attrs = getattr(st, "st_file_attributes", 0)
                    if attrs & FILE_ATTRIBUTE_REPARSE_POINT:
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        subdirs.append(entry.path)
                    elif attrs & _CLOUD_ONLY:
                        cloud += 1
                    else:
                        file_bytes += st.st_size
                except OSError:
                    denied += 1
    except OSError:
        denied += 1
    return file_bytes, denied, cloud, subdirs


def scan_children(path, max_workers=16):
    """
    Everything directly inside `path`, with full sizes, largest first.

    Work is spread over a thread pool TWO levels deep (each top-level folder's
    own subfolders are separate tasks), so one huge folder such as Users or
    Windows does not leave the other threads idle.

    Returns:
      path, total_gb (sum of entries), denied (unreadable items anywhere below),
      cloud_only_skipped, entries: [{name, path, is_dir, size_bytes, size_gb}]
    or {"error": ...} if the folder itself can't be read.
    """
    try:
        listing = list(os.scandir(path))
    except OSError as e:
        return {"path": path, "error": f"Could not read this folder: {e}"}

    entries = []
    denied = 0
    cloud = 0
    dirs = []

    for e in listing:
        try:
            if e.is_symlink():
                continue
            st = e.stat(follow_symlinks=False)
            attrs = getattr(st, "st_file_attributes", 0)
            if attrs & FILE_ATTRIBUTE_REPARSE_POINT:
                continue
            if e.is_dir(follow_symlinks=False):
                dirs.append(e)
            elif attrs & _CLOUD_ONLY:
                cloud += 1
            else:
                entries.append({"name": e.name, "path": e.path, "is_dir": False,
                                "size_bytes": st.st_size})
        except OSError:
            denied += 1

    # totals per top-level folder, filled in as the tasks finish
    totals = {d.path: 0 for d in dirs}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {}
        for d in dirs:
            file_bytes, den, cl, subdirs = _split_dir(d.path)
            totals[d.path] += file_bytes
            denied += den
            cloud += cl
            for sub in subdirs:
                futures[ex.submit(_scan_dir, sub)] = d.path
        for fut in as_completed(futures):
            owner = futures[fut]
            try:
                size, den, cl = fut.result()
            except Exception:
                size, den, cl = 0, 1, 0
            totals[owner] += size
            denied += den
            cloud += cl

    for d in dirs:
        entries.append({"name": d.name, "path": d.path, "is_dir": True,
                        "size_bytes": totals[d.path]})

    for item in entries:
        item["size_gb"] = round(item["size_bytes"] / (1024 ** 3), 3)
    entries.sort(key=lambda x: x["size_bytes"], reverse=True)

    return {
        "path": path,
        "total_gb": round(sum(x["size_bytes"] for x in entries) / (1024 ** 3), 3),
        "denied": denied,
        "cloud_only_skipped": cloud,
        "entries": entries,
    }


def scan_top_level_folders(root_path, max_workers=8):
    """Older helper: subfolders only, as {name, path, size_gb}."""
    result = scan_children(root_path, max_workers=max_workers)
    if "error" in result:
        print(result["error"], file=sys.stderr)
        return []
    return [{"name": x["name"], "path": x["path"], "size_gb": x["size_gb"]}
            for x in result["entries"] if x["is_dir"]]


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~")
    print(f"=== Drives ===")
    for d in get_drives():
        print(f"{d['mountpoint']:<8} {d['used_gb']:>8.1f} / {d['total_gb']:.1f} GB used")
    print(f"\n=== {target} ===")
    r = scan_children(target)
    if "error" in r:
        print(r["error"])
    else:
        for x in r["entries"]:
            print(f"{x['size_gb']:>10.3f} GB  {'[dir] ' if x['is_dir'] else '      '}{x['name']}")
        print(f"\nUnreadable items: {r['denied']}   Cloud-only files skipped: {r['cloud_only_skipped']}")
