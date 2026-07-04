# Releasing

`main` is for development. `stable` is the protected release branch — every
release ships from there.

## Branch model

| Branch   | Purpose                          | Protected |
|----------|----------------------------------|-----------|
| `main`   | day-to-day development           | no        |
| `stable` | released code, publishes `:latest` | yes (PR + passing CI) |

## Cutting a release

1. **Update the changelog.** Move items from `[Unreleased]` into a new
   `[X.Y.Z]` section in `CHANGELOG.md`, dated today. Bump per SemVer:
   - `PATCH` — bug fixes only
   - `MINOR` — new features, backwards compatible
   - `MAJOR` — breaking changes (config, DB, or behavior)

2. **PR `main` → `stable`.** CI (`test`) must pass before it can merge.
   Merging publishes `ghcr.io/megabitus98/teslamate-suc-cost-sync:latest`.

3. **Tag the release** on `stable`:
   ```sh
   git checkout stable && git pull
   git tag -a v0.1.0 -m "v0.1.0"
   git push origin v0.1.0
   ```
   The tag triggers the Release workflow to publish the versioned image
   (`:0.1.0`) and a `sha-<commit>` tag.

4. **(Optional) GitHub Release notes** from the changelog section:
   ```sh
   gh release create v0.1.0 --title v0.1.0 --notes-from-tag
   ```

## Pulling a released image

```sh
docker pull ghcr.io/megabitus98/teslamate-suc-cost-sync:latest   # newest on stable
docker pull ghcr.io/megabitus98/teslamate-suc-cost-sync:0.1.0    # pinned version
```
