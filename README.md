# scp-helper

Small Flask web UI for copying files between your local machine and a remote device over SSH/SCP.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000.

## Use

1. Enter user, host, password, and remote path.
2. Click **Connect**.
3. Browse local and remote directories.
4. Click `→` to upload, `←` to download.

## Notes

- Stores credentials in the Flask session. Set a real `SECRET_KEY` for production use.
- Host key policy is `AutoAddPolicy`; use only on trusted networks.
# scp-helper-v2
