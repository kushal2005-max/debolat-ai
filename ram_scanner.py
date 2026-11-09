"""
Debolat AI - RAM Scanner

Raw data collection, no AI involved.

get_all_ram_apps() scans EVERY process, groups them into apps (so Chrome's
40 processes become one "chrome.exe" row), and reports an honest
reconciliation: how much of the used RAM could be attributed to apps, and
how much is system/kernel/cache memory that no process list can show.

Memory metric: we use USS ("unique set size" = memory that belongs only to
that process, close to Task Manager's "Memory" column). It needs permission;
when Windows refuses it we fall back to the working set (RSS), which includes
memory shared with other processes, and the group is flagged
`includes_shared` so the UI can say so. Processes we cannot read at all are
counted in `unreadable_processes` - never silently dropped.
"""

import os
import psutil

_ACCESS_ERRORS = (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError)


def _read_process_memory(proc):
    """Returns (megabytes, metric) or (None, None) if unreadable.
    metric is 'private' (USS) or 'working_set' (RSS, includes shared)."""
    try:
        return proc.memory_full_info().uss / (1024 * 1024), "private"
    except _ACCESS_ERRORS:
        pass
    try:
        return proc.memory_info().rss / (1024 * 1024), "working_set"
    except _ACCESS_ERRORS:
        return None, None


def get_all_ram_apps():
    """
    Scans every process and groups by executable path (falls back to the
    process name when the path is unreadable).

    Returns dict:
      apps: [{name, exe_path, ram_mb, process_count, pids, includes_shared}]
            sorted by ram_mb descending - ALL of them, nothing capped
      unreadable_processes: int
      accounted_mb: sum of all apps
    """
    groups = {}
    unreadable = 0

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            pid = proc.info["pid"]
            name = proc.info["name"] or f"pid {pid}"

            exe = None
            try:
                exe = proc.exe() or None
            except _ACCESS_ERRORS:
                pass

            mb, metric = _read_process_memory(proc)
            if mb is None:
                unreadable += 1
                continue

            key = (exe or name).lower()
            g = groups.get(key)
            if g is None:
                g = groups[key] = {
                    "name": name,
                    "exe_path": exe,
                    "ram_mb": 0.0,
                    "process_count": 0,
                    "pids": [],
                    "includes_shared": False,
                }
            g["ram_mb"] += mb
            g["process_count"] += 1
            g["pids"].append(pid)
            if metric == "working_set":
                g["includes_shared"] = True
        except _ACCESS_ERRORS:
            unreadable += 1
            continue

    apps = list(groups.values())
    for a in apps:
        a["ram_mb"] = round(a["ram_mb"], 2)
    apps.sort(key=lambda a: a["ram_mb"], reverse=True)

    return {
        "apps": apps,
        "unreadable_processes": unreadable,
        "accounted_mb": round(sum(a["ram_mb"] for a in apps), 2),
    }


def get_top_ram_processes(limit=15):
    """Kept for the command-line demo: individual processes, not grouped."""
    processes = []
    for proc in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            mem_info = proc.info["memory_info"]
            if mem_info is None:
                continue
            processes.append({
                "pid": proc.info["pid"],
                "name": proc.info["name"],
                "ram_mb": round(mem_info.rss / (1024 * 1024), 2),
            })
        except _ACCESS_ERRORS:
            continue
    processes.sort(key=lambda p: p["ram_mb"], reverse=True)
    return processes[:limit]


def get_total_ram_usage():
    """Overall system RAM usage stats."""
    vm = psutil.virtual_memory()
    return {
        "total_gb": round(vm.total / (1024 ** 3), 2),
        "used_gb": round(vm.used / (1024 ** 3), 2),
        "used_mb": round(vm.used / (1024 * 1024), 2),
        "available_gb": round(vm.available / (1024 ** 3), 2),
        "percent_used": vm.percent,
    }


if __name__ == "__main__":
    totals = get_total_ram_usage()
    scan = get_all_ram_apps()
    print("=== System RAM Overview ===")
    print(f"Total: {totals['total_gb']} GB   Used: {totals['used_gb']} GB ({totals['percent_used']}%)")
    print(f"Attributed to apps: {scan['accounted_mb'] / 1024:.2f} GB   "
          f"Unreadable processes: {scan['unreadable_processes']}\n")
    print("=== All apps (grouped) ===")
    for a in scan["apps"]:
        shared = "*" if a["includes_shared"] else " "
        print(f"{a['ram_mb']:>9.1f} MB{shared} {a['name']:<32} x{a['process_count']}")
    print("\n* includes memory shared with other processes (permission fallback)")
