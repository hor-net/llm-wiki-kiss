# Publishing a GitHub release

The project is distributed as a cloneable Git repository. No Docker or PyPI
publication is required.

## Checklist

1. Make sure the example wiki does not contain private data.
2. Make sure `.wiki-kiss.env`, generated skills, tokens or TLS keys are
   not tracked.
3. Bump the version in `pyproject.toml`, the REST API and `CHANGELOG.md`.
4. Run:

   ```bash
   python -m pytest -q
   python -m ruff check wiki_core mcp_server rest_api.py tests
   find scripts -type f -name '*.sh' -print0 | xargs -0 bash -n
   python tests/smoke_mcp.py
   python tests/smoke_mcp_http.py
   ```

5. Try a clean clone:

   ```bash
   scripts/setup.sh --with-dev --root ./wiki --https off
   scripts/wiki.sh list
   scripts/onboard-agent.sh --name release-smoke --mode local
   ```

6. Confirm that GitHub Actions are green.
7. Review the diff and create focused commits.
8. Create an annotated tag and push it:

   ```bash
   git tag -a v0.3.0 -m "llm-wiki-kiss v0.3.0"
   git push origin main
   git push origin v0.3.0
   ```

9. Create the GitHub Release using the matching section of `CHANGELOG.md`.

Never tag before the working tree is clean and the CI is green.
