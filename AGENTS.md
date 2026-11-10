# ha-d2ha – Agent Guide

The Home Assistant integration for D2HA, in the catalogue of Home Assistant's Marketplace
(the HACS default list).
Two AI assistants work across Arborae: **Kimi** owns this repository, **Claude** owns the
app repository (`Arborae/docker2homeassistant`). The owner merges and releases.

## Layout

- `custom_components/d2ha/` – the integration:
  - `api.py` – the async client. **Use only what
    [API.md](https://github.com/Arborae/docker2homeassistant/blob/main/API.md) describes.**
    If something is missing, open an issue labelled `claude` in the app repository.
  - `config_flow.py` – URL + bearer token, re-authentication.
  - `coordinator.py` – polls `/info`, `/containers?ha=1` and `/jobs`; faster while jobs run.
  - `update.py`, `sensor.py`, `button.py`, `entity.py`, `const.py`.
  - `strings.json`, `translations/{en,it}.json` – every user-visible string, both languages.
- `tests/` – pytest with pytest-homeassistant-custom-component; the fake D2HA server in
  `tests/conftest.py` follows API.md.
- `.github/workflows/` – pytest, hassfest, HACS validation, repository checks.

## Rules (same as the main repository)

- Tasks are GitHub issues in `Arborae/docker2homeassistant` labelled `kimi`; one branch per
  issue, from an up-to-date `main`, named `<type>/<issue>-<short-name>`; the pull request
  says `Closes Arborae/docker2homeassistant#<issue>`.
- Before a pull request: facts from the source, tests pass (`pytest -q`), new behaviour has
  tests, Unix line endings, no permission changes, no secrets or personal data, read your
  whole diff.
- Every pull request is reviewed by the other agent (Claude) before the owner merges it.
- Commits use the GitHub noreply address and a `Co-Authored-By` trailer with the agent name.
- Entities are built on the container `key`, never on `id` or `name`. Never log or expose
  the token.
