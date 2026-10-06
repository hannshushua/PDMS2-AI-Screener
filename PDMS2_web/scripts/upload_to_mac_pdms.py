# -*- coding: utf-8 -*-
import argparse
import posixpath
import socket
import sys
from pathlib import Path

import paramiko
from paramiko.ssh_exception import (
    AuthenticationException,
    NoValidConnectionsError,
    SSHException,
)


def _mkdir_p(sftp, remote_dir: str) -> None:
    parts = [p for p in remote_dir.strip("/").split("/") if p]
    current = "/"
    for part in parts:
        current = posixpath.join(current, part)
        try:
            sftp.stat(current)
        except IOError:
            sftp.mkdir(current)


def _append_if_exists(container: list[Path], seen: set[str], path: Path) -> None:
    if path.exists() and path.is_file():
        key = str(path.resolve())
        if key not in seen:
            seen.add(key)
            container.append(path)


def _collect_original_and_result_files(local_uid_dir: Path, img_id: str):
    originals: list[Path] = []
    results: list[Path] = []
    seen: set[str] = set()

    for ext in ("jpg", "jpeg", "png", "webp"):
        _append_if_exists(originals, seen, local_uid_dir / f"{img_id}.{ext}")

    result_patterns = [
        f"{img_id}_result.*",
        f"{img_id}-*_result.*",
        f"{img_id}*result*.jpg",
        f"{img_id}*result*.jpeg",
        f"{img_id}*result*.png",
        f"{img_id}*result*.webp",
    ]
    for pattern in result_patterns:
        for path in local_uid_dir.glob(pattern):
            _append_if_exists(results, seen, path)

    originals.sort(key=lambda p: p.name.lower())
    results.sort(key=lambda p: p.name.lower())
    return originals, results


def _is_port_open(host: str, port: int, timeout_sec: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True
    except OSError:
        return False


def upload_to_mac(
    uid: str,
    img_id: str,
    root: Path,
    host: str,
    port: int,
    user: str,
    password: str,
    key_path: str,
    remote_base: str,
) -> int:
    local_uid_dir = root / "kid" / uid
    if not local_uid_dir.exists():
        print(f"[UPLOAD] 本地資料夾不存在: {local_uid_dir}", file=sys.stderr)
        return 2

    originals, results = _collect_original_and_result_files(local_uid_dir, img_id)
    if not originals and not results:
        print(
            f"[UPLOAD] 找不到要上傳的檔案: uid={uid}, img_id={img_id}", file=sys.stderr
        )
        return 3

    if not _is_port_open(host, port):
        print(
            f"[UPLOAD] 無法連線到 {host}:{port}。請先在 Mac 開啟『遠端登入(SSH)』並確認防火牆允許連線。",
            file=sys.stderr,
        )
        return 4

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connect_kwargs = {
        "hostname": host,
        "port": port,
        "username": user,
        "timeout": 10,
    }
    if key_path:
        connect_kwargs["key_filename"] = key_path
    else:
        connect_kwargs["password"] = password

    try:
        ssh.connect(**connect_kwargs)
        sftp = ssh.open_sftp()

        try:
            home = sftp.normalize(".")
            base = remote_base.replace("\\", "/").strip("/")
            remote_uid_dir = posixpath.join(home, base, uid)
            _mkdir_p(sftp, remote_uid_dir)

            for path in originals:
                target = posixpath.join(remote_uid_dir, path.name)
                sftp.put(str(path), target)
                print(f"[UPLOAD] 原始圖 -> {target}")

            for path in results:
                target = posixpath.join(remote_uid_dir, path.name)
                sftp.put(str(path), target)
                print(f"[UPLOAD] 結果圖 -> {target}")

            return 0
        finally:
            sftp.close()
            ssh.close()
    except AuthenticationException:
        print(
            "[UPLOAD] SSH 登入失敗：請確認 MAC_UPLOAD_USER / MAC_UPLOAD_PASSWORD",
            file=sys.stderr,
        )
        return 5
    except NoValidConnectionsError:
        print(
            f"[UPLOAD] 無法連線到 {host}:{port}。請確認 Mac SSH 服務已啟用且網路可達。",
            file=sys.stderr,
        )
        return 4
    except SSHException as e:
        print(f"[UPLOAD] SSH 連線錯誤: {e}", file=sys.stderr)
        return 6
    except Exception as e:
        print(f"[UPLOAD] 未預期錯誤: {e}", file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Upload PDMS images to Mac Desktop/PDMS"
    )
    parser.add_argument("--uid", required=True)
    parser.add_argument("--img-id", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", default="")
    parser.add_argument("--key-path", default="")
    parser.add_argument("--remote-base", default="Desktop/PDMS")
    args = parser.parse_args()

    exit_code = upload_to_mac(
        uid=args.uid,
        img_id=args.img_id,
        root=Path(args.root),
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        key_path=args.key_path,
        remote_base=args.remote_base,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
