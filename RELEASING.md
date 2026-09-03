# Releasing

1. Run the test and lint commands from `CONTRIBUTING.md` on Windows.
2. Update `CHANGELOG.md` and replace the `Unreleased` heading with the new
   version when the changes are ready.
3. Create an annotated tag that follows semantic versioning, for example:

   ```powershell
   git tag -a v1.0.1 -m "Release v1.0.1"
   git push origin v1.0.1
   ```

4. The `Windows release` workflow builds the portable folder, creates the ZIP,
   writes `SHA256SUMS.txt`, and publishes both files to the GitHub Release.
5. Download the release on a clean Windows machine, extract it, launch the EXE,
   and process a permission-cleared synthetic image and video before announcing
   the release.

The workflow can also be started manually for an existing tag. It replaces the
two release assets when a release already exists, which makes a failed upload
recoverable without creating a second release.
