#!/usr/bin/env python3
"""Refresh marked README sections from public GitHub data; Python 3.11+, stdlib only."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import html
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.github.com"
USERNAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z")
REPO_NAME = re.compile(r"[A-Za-z0-9_.-]+\Z")
BLOCKS = ("PROFILE", "PROJECTS", "ACTIVITY", "UPDATED")


class ProfileError(ValueError):
    """Invalid or incomplete data must not replace the last good profile."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward an Authorization header to an unexpected destination.
        return None


def get_json(path: str):
    if not path.startswith("/") or path.startswith("//"):
        raise ProfileError("Expected a path on api.github.com.")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "mragetsars-profile"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    opener = build_opener(NoRedirect())
    for attempt in range(3):
        try:
            with opener.open(Request(API + path, headers=headers), timeout=20) as response:
                return json.load(response)
        except HTTPError as exc:
            retryable = exc.code in (429, 500, 502, 503, 504) or (
                exc.code == 403
                and (exc.headers.get("X-RateLimit-Remaining") == "0" or exc.headers.get("Retry-After"))
            )
            if not retryable or attempt == 2:
                raise ProfileError(f"GitHub API returned HTTP {exc.code}; saved files were not changed.") from None
        except (URLError, TimeoutError, OSError):
            if attempt == 2:
                raise ProfileError("GitHub API could not be reached; saved files were not changed.") from None
        except (json.JSONDecodeError, UnicodeError):
            raise ProfileError("GitHub returned invalid JSON; saved files were not changed.") from None
        time.sleep(2 ** attempt)
    raise ProfileError("GitHub API request failed.")


def natural(value, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ProfileError(f"Invalid non-negative integer: {field}.")
    return value


def optional_text(value, field: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ProfileError(f"Invalid text: {field}.")
    return " ".join(value.split())


def load_config(root: Path) -> dict:
    config = json.loads((root / "profile.json").read_text(encoding="utf-8"))
    username = config.get("username", "")
    if not isinstance(username, str) or not USERNAME.fullmatch(username):
        raise ProfileError("Invalid GitHub username in profile.json.")
    if not isinstance(config.get("featured"), list) or len(config["featured"]) > 8:
        raise ProfileError("featured must contain at most eight projects.")
    seen = set()
    for item in config["featured"]:
        if not isinstance(item, dict):
            raise ProfileError("Each featured project must be an object.")
        ident = natural(item.get("id"), "featured.id")
        if ident == 0 or ident in seen:
            raise ProfileError("Featured repository IDs must be positive and unique.")
        seen.add(ident)
        if not optional_text(item.get("label"), "featured.label"):
            raise ProfileError("Each featured project needs a label.")
    if not 0 <= natural(config.get("recent_limit"), "recent_limit") <= 5:
        raise ProfileError("recent_limit must be between zero and five.")
    return config


def normalize_user(raw: dict, username: str) -> dict:
    if not isinstance(raw, dict) or str(raw.get("login", "")).lower() != username.lower():
        raise ProfileError("GitHub returned a different account.")
    return {
        "login": raw["login"],
        "bio": optional_text(raw.get("bio"), "bio"),
        "company": optional_text(raw.get("company"), "company"),
        "location": optional_text(raw.get("location"), "location"),
        "blog": optional_text(raw.get("blog"), "blog"),
        "followers": natural(raw.get("followers"), "followers"),
    }


def normalize_repo(raw: dict, username: str) -> dict | None:
    if not isinstance(raw, dict) or type(raw.get("private")) is not bool:
        raise ProfileError("A repository is missing its visibility flag.")
    # Filter private and foreign repositories BEFORE retaining any of their fields.
    if raw["private"] or raw.get("owner", {}).get("login", "").lower() != username.lower():
        return None
    name = raw.get("name", "")
    if not isinstance(name, str) or not REPO_NAME.fullmatch(name) or name in (".", ".."):
        raise ProfileError("Invalid repository name.")
    for key in ("fork", "archived"):
        if type(raw.get(key)) is not bool:
            raise ProfileError(f"Repository {name} has no valid {key} flag.")
    # Refresh commits move this repository's push time. It is never displayed,
    # so omit it rather than make each refresh generate another refresh commit.
    pushed_at = None if name.lower() == username.lower() else raw.get("pushed_at")
    if pushed_at is not None:
        if not isinstance(pushed_at, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", pushed_at):
            raise ProfileError(f"Invalid push timestamp for {name}.")
        datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
    ident = natural(raw.get("id"), "repository.id")
    if not ident:
        raise ProfileError("Repository ID must be positive.")
    return {
        "id": ident,
        "name": name,
        "description": optional_text(raw.get("description"), "description"),
        "language": optional_text(raw.get("language"), "language"),
        "stars": natural(raw.get("stargazers_count"), "stargazers_count"),
        "fork": raw["fork"],
        "archived": raw["archived"],
        "pushed_at": pushed_at,
    }


def collect(config: dict) -> dict:
    username = config["username"]
    user = normalize_user(get_json(f"/users/{username}"), username)
    repos = []
    seen = set()
    for page in range(1, 101):
        batch = get_json(f"/users/{username}/repos?type=owner&sort=full_name&per_page=100&page={page}")
        if not isinstance(batch, list):
            raise ProfileError("GitHub did not return a repository list.")
        for raw in batch:
            repo = normalize_repo(raw, username)
            if repo is None:
                continue
            if repo["id"] in seen:
                raise ProfileError("Duplicate repository across pages; retry with a consistent listing.")
            seen.add(repo["id"])
            repos.append(repo)
        if len(batch) < 100:
            break
    else:
        raise ProfileError("Repository pagination limit reached; refusing a partial snapshot.")
    return {
        "schema_version": 1,
        "updated_on": datetime.now(timezone.utc).date().isoformat(),
        "user": user,
        "repositories": sorted(repos, key=lambda r: r["name"].lower()),
    }


def validate_snapshot(data: dict, username: str) -> dict:
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ProfileError("Unsupported snapshot format.")
    if not isinstance(data.get("updated_on"), str):
        raise ProfileError("Snapshot needs a refresh date.")
    if date.fromisoformat(data["updated_on"]).isoformat() != data["updated_on"]:
        raise ProfileError("Invalid snapshot date.")
    user = normalize_user(data.get("user"), username)
    if not isinstance(data.get("repositories"), list):
        raise ProfileError("Snapshot needs a repository list.")
    repos, seen = [], set()
    for raw in data["repositories"]:
        if not isinstance(raw, dict):
            raise ProfileError("Invalid repository in snapshot.")
        repo = normalize_repo({**raw, "private": False, "owner": {"login": username},
                               "stargazers_count": raw.get("stars")}, username)
        if repo["id"] in seen:
            raise ProfileError("Duplicate repository in snapshot.")
        seen.add(repo["id"])
        repos.append(repo)
    return {"schema_version": 1, "updated_on": data["updated_on"], "user": user,
            "repositories": sorted(repos, key=lambda r: r["name"].lower())}


def text(value: str, limit: int | None = None) -> str:
    """Render API text literally, including pipes, HTML and Markdown delimiters."""
    value = " ".join(value.split())
    if limit and len(value) > limit:
        trimmed = value[:limit - 1]
        value = (trimmed.rsplit(" ", 1)[0] if " " in trimmed else trimmed) + "…"
    value = html.escape(value, quote=True)
    return re.sub(r"[\\`*_|\[\]{}]", lambda m: f"&#{ord(m[0])};", value)


def website_link(url: str) -> str | None:
    try:
        parts = urlsplit(url)
        if parts.scheme not in ("https", "http") or not parts.hostname or parts.username or parts.password:
            return None
        if any(c.isspace() or ord(c) < 32 for c in url):
            return None
        label = "Telegram" if parts.hostname.lower() in ("t.me", "telegram.me") else "Website"
        return f"[{label}]({quote(url, safe=':/?=&%#+-._~')})"
    except ValueError:
        return None


def repo_url(username: str, repo: dict) -> str:
    return f"https://github.com/{username}/{quote(repo['name'], safe='')}"


def description_summary(value: str) -> str:
    # The first sentence explains the project; later sentences often repeat coursework context.
    value = re.sub(r"\s+([,.!?;:])", r"\1", " ".join(value.split()))
    value = re.split(r"(?<=[.!?])\s+(?=[A-Z])", value, maxsplit=1)[0]
    if value:
        value = value[0].upper() + value[1:]
    return text(value, 230) or "Explore the source code and documentation."


def eligible_repos(data: dict) -> list[dict]:
    return [r for r in data["repositories"]
            if not r["fork"] and r["name"].lower() != data["user"]["login"].lower()]


def render_blocks(data: dict, config: dict) -> dict[str, str]:
    user = data["user"]
    username = user["login"]
    identity = " · ".join(text(user[k]) for k in ("bio", "company", "location") if user[k])
    contact = [f"[Explore my repositories](https://github.com/{username}?tab=repositories)"]
    website = website_link(user["blog"])
    if website:
        contact.append(website)
    profile = (f"**{identity}**\n\n" if identity else "") + " · ".join(contact)

    own = eligible_repos(data)
    lookup = {repo["id"]: repo for repo in own}
    projects, selected = [], set()
    for item in config["featured"]:
        repo = lookup.get(item["id"])
        if repo is None:
            # Deleted/private/transferred/forked projects disappear without stale links.
            continue
        selected.add(repo["id"])
        description = description_summary(repo["description"])
        pushed = repo["pushed_at"][:10] if repo["pushed_at"] else "No push recorded"
        language = text(repo["language"]) or "Not reported"
        star_label = "star" if repo["stars"] == 1 else "stars"
        stars = f" · {repo['stars']:,} {star_label}" if repo["stars"] else ""
        archived = " · Archived" if repo["archived"] else ""
        url = repo_url(username, repo)
        projects.append(f"- **[{text(item['label'])}]({url})** — {description}  \n"
                        f"  <sub>{language}{stars} · Last push: {pushed}{archived}</sub>")

    activity = (f"**{len(data['repositories']):,} public repositories** · "
                f"**{user['followers']:,} followers** · "
                f"**{sum(r['stars'] for r in own):,} stars received**\n\n"
                f"Stars received are counted across my {len(own):,} public non-fork project repositories "
                "(excluding this profile repository).\n\n")
    recent = sorted((r for r in own if r["id"] not in selected and not r["archived"] and r["pushed_at"]),
                    key=lambda r: (r["pushed_at"], r["name"]), reverse=True)[:config["recent_limit"]]
    if recent:
        activity += "**More projects with recent pushes**\n\n" + "\n".join(
            f"- [{text(r['name'].replace('-', ' '))}]({repo_url(username, r)}) — {r['pushed_at'][:10]}"
            for r in recent)
    else:
        activity += f"[Browse all projects](https://github.com/{username}?tab=repositories)."
    updated = (f"<sub>Public GitHub data refreshed: {data['updated_on']} (UTC). "
               "Scheduled daily · repository descriptions, primary languages, stars and push dates update automatically. "
               "[Refresh status](https://github.com/" + username + "/" + username +
               "/actions/workflows/update-profile.yml).</sub>")
    return {"PROFILE": profile, "PROJECTS": "\n\n".join(projects) or "No selected public projects are currently available.",
            "ACTIVITY": activity, "UPDATED": updated}


def replace_blocks(readme: str, blocks: dict[str, str]) -> str:
    spans = []
    for name in BLOCKS:
        start, end = f"<!-- {name}:START -->", f"<!-- {name}:END -->"
        if readme.count(start) != 1 or readme.count(end) != 1:
            raise ProfileError(f"Expected exactly one pair of {name} markers.")
        left, right = readme.index(start), readme.index(end)
        if right < left:
            raise ProfileError(f"Reversed {name} markers.")
        spans.append((left, right + len(end), f"{start}\n{blocks[name]}\n{end}"))
    ordered = sorted(spans)
    if any(a[1] > b[0] for a, b in zip(ordered, ordered[1:])):
        raise ProfileError("Generated blocks cannot overlap or nest.")
    for left, right, replacement in reversed(ordered):
        readme = readme[:left] + replacement + readme[right:]
    return readme


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        temporary.chmod(0o644)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def update(root: Path, *, offline: bool = False, check: bool = False) -> bool:
    config = load_config(root)
    snapshot_path = root / "data/profile.json"
    raw = json.loads(snapshot_path.read_text(encoding="utf-8")) if offline else collect(config)
    data = validate_snapshot(raw, config["username"])
    readme_path = root / "README.md"
    current = readme_path.read_text(encoding="utf-8")
    rendered = replace_blocks(current, render_blocks(data, config))
    snapshot = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    files = [(readme_path, rendered), (snapshot_path, snapshot)]
    changed = [(path, content) for path, content in files
               if not path.exists() or path.read_text(encoding="utf-8") != content]
    # Every API call, validation and render has finished before any file is touched.
    if not check:
        for path, content in changed:
            atomic_write(path, content)
    return bool(changed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Render the committed public snapshot without network access.")
    parser.add_argument("--check", action="store_true", help="Do not write files; exit 1 if generated output differs.")
    args = parser.parse_args()
    try:
        changed = update(ROOT, offline=args.offline, check=args.check)
    except (ProfileError, ValueError, OSError, TypeError, KeyError, AttributeError) as exc:
        print(f"Profile refresh failed: {exc}", file=sys.stderr)
        return 1
    if args.check and changed:
        print("Generated output differs. Run: python3 scripts/update_profile.py --offline", file=sys.stderr)
        return 1
    print("Profile updated." if changed else "Profile is already up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
