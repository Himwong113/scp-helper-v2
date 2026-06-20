import os
import posixpath
import stat
from pathlib import Path

import paramiko
from flask import Flask, jsonify, render_template, request, session
from scp import SCPClient

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")


def _error(message, code=400):
    return jsonify({"error": message}), code


def _safe_local_path(path):
    if not path or "\x00" in path:
        raise ValueError("bad path")
    p = Path(path).expanduser().resolve()
    if not p.is_absolute():
        raise ValueError("path must be absolute")
    return p


def _ssh_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        session["host"],
        username=session["user"],
        password=session["password"],
        timeout=10,
        banner_timeout=10,
        allow_agent=False,
        look_for_keys=False,
    )
    return client


def _expand_remote_path(sftp, path):
    if path.startswith("~"):
        home = sftp.normalize(".")
        if path == "~":
            return home
        return posixpath.join(home, path[2:] if path.startswith("~/") else path[1:])
    return path


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/connect", methods=["POST"])
def connect():
    data = request.get_json(silent=True) or {}
    user = data.get("user", "").strip()
    host = data.get("host", "").strip()
    password = data.get("password", "")
    remote_path = data.get("remote_path", "~").strip() or "~"

    if not user or not host:
        return _error("user and host required")

    session["user"] = user
    session["host"] = host
    session["password"] = password
    session["remote_path"] = remote_path
    session["local_path"] = str(Path.home())
    return jsonify({"status": "ok"})


@app.route("/api/local/list", methods=["GET"])
def local_list():
    path = request.args.get("path", session.get("local_path", str(Path.home())))
    try:
        base = _safe_local_path(path)
    except ValueError as e:
        return _error(str(e))

    if not base.is_dir():
        return _error("not a directory", 404)

    items = []
    for name in sorted(os.listdir(base)):
        p = base / name
        items.append({"name": name, "type": "dir" if p.is_dir() else "file"})
    return jsonify({"path": str(base), "items": items})


@app.route("/api/remote/list", methods=["POST"])
def remote_list():
    data = request.get_json(silent=True) or {}
    path = data.get("path", session.get("remote_path", "~")).strip() or "~"

    if not session.get("user") or not session.get("host"):
        return _error("not connected", 401)

    try:
        with _ssh_client() as client:
            sftp = client.open_sftp()
            path = _expand_remote_path(sftp, path)
            attrs = sftp.listdir_attr(path)
            items = []
            for attr in attrs:
                if attr.filename in (".", ".."):
                    continue
                items.append({
                    "name": attr.filename,
                    "type": "dir" if stat.S_ISDIR(attr.st_mode) else "file",
                })
            return jsonify({"path": path, "items": items})
    except paramiko.AuthenticationException:
        return _error("authentication failed", 401)
    except paramiko.SSHException as e:
        return _error(str(e), 500)
    except OSError as e:
        return _error(str(e), 500)


@app.route("/api/transfer", methods=["POST"])
def transfer():
    data = request.get_json(silent=True) or {}
    direction = data.get("direction")
    source_dir = data.get("source_dir", "").strip()
    target_dir = data.get("target_dir", "").strip()
    name = data.get("name", "").strip()

    if direction not in ("local_to_remote", "remote_to_local"):
        return _error("bad direction")
    if not source_dir or not target_dir or not name:
        return _error("source_dir, target_dir and name required")

    if not session.get("user") or not session.get("host"):
        return _error("not connected", 401)

    try:
        with _ssh_client() as client:
            with SCPClient(client.get_transport()) as scp:
                if direction == "local_to_remote":
                    source = _safe_local_path(os.path.join(source_dir, name))
                    remote_target = _expand_remote_path(client.open_sftp(), target_dir)
                    scp.put(str(source), remote_target, recursive=True)
                else:
                    sftp = client.open_sftp()
                    remote_source = _expand_remote_path(sftp, posixpath.join(source_dir, name))
                    local_target = _safe_local_path(target_dir)
                    scp.get(remote_source, str(local_target), recursive=True)

            return jsonify({"status": "ok"})
    except paramiko.AuthenticationException:
        return _error("authentication failed", 401)
    except paramiko.SSHException as e:
        return _error(str(e), 500)
    except OSError as e:
        return _error(str(e), 500)
    except Exception as e:
        return _error(str(e), 500)


if __name__ == "__main__":
    app.run(debug=True)
