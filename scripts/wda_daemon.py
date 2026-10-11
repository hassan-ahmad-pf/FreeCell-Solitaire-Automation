#!/usr/bin/env python3
"""Start a command in a new session so a Cursor/terminal exit cannot kill it.

Usage: wda_daemon.py <pidfile> <logfile|-> <command> [args...]
Writes the grandchild pid, then returns.
"""
from __future__ import annotations

import os
import sys


def main() -> int:
    if len(sys.argv) < 4:
        sys.stderr.write("usage: wda_daemon.py <pidfile> <logfile|-> <cmd>...\n")
        return 2
    pid_path, log_path, *cmd = sys.argv[1:]
    reader, writer = os.pipe()
    first = os.fork()
    if first > 0:
        os.close(writer)
        raw = os.read(reader, 32)
        os.close(reader)
        os.waitpid(first, 0)
        with open(pid_path, "w", encoding="utf-8") as handle:
            handle.write(raw.decode().strip() + "\n")
        return 0
    os.close(reader)
    os.setsid()
    second = os.fork()
    if second > 0:
        os.write(writer, str(second).encode())
        os.close(writer)
        os._exit(0)
    os.close(writer)
    xcode = os.environ.get(
        "DEVELOPER_DIR",
        "/Applications/Xcode.app/Contents/Developer",
    )
    os.environ["DEVELOPER_DIR"] = xcode
    os.environ["PATH"] = (
        f"{xcode}/usr/bin:{xcode}/Toolchains/XcodeDefault.xctoolchain/usr/bin:"
        f"{os.environ.get('PATH', '/usr/bin:/bin:/usr/sbin:/sbin')}"
    )
    null = os.open(os.devnull, os.O_RDWR)
    os.dup2(null, 0)
    if log_path and log_path != "-":
        log = os.open(log_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        os.dup2(log, 1)
        os.dup2(log, 2)
        os.close(log)
    else:
        os.dup2(null, 1)
        os.dup2(null, 2)
    os.close(null)
    os.execvp(cmd[0], cmd)
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
