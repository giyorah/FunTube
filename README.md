# FunTube

My personal [TizenTube](https://github.com/reisxd/TizenTube) standalone package with a custom
FunTube icon and name. Playback functionality comes from upstream TizenTube.

## Install or update

**Updates are optional.** If FunTube works well, you can keep your current version.
Some behavior changes through the online TizenTube script without installing a new WGT.
GitHub notifications announce available packages; they do not update your TV.

### 1. Prepare the TV for installation

1. Download the `.wgt` file from the [latest FunTube release](https://github.com/giyorah/FunTube/releases/latest).
2. Find the current local network IP address of the Windows PC running Apps2Samsung.
3. On the TV, open the Developer Mode settings:
   - Keep **Developer Mode enabled**.
   - Set **Host PC IP** to your Windows PC’s local network IP address.
4. Fully restart the TV, then connect to it from Apps2Samsung.

### 2. Install the package

1. In Apps2Samsung, select **Custom WGT** and choose the downloaded file.
2. Keep the same certificate settings used for your existing FunTube installation.
   Apps2Samsung’s **Jelly2Sams** default has worked on my Samsung QN90B running Tizen 6.5.
3. For an update, enable **Overwrite existing version**.
4. Install the package and wait for the success message. **Do not open FunTube yet.**

The package is unsigned; Apps2Samsung signs it during installation.
If installation fails, investigate the error before uninstalling the existing app.

### 3. Restore the playback setting

1. Return to the TV’s Developer Mode settings.
2. Change **Host PC IP** back to **`127.0.0.1`**, leaving Developer Mode enabled.
3. Fully restart the TV again.
4. Open FunTube and check that a video plays.

Keep **`127.0.0.1`** set during normal use. It selects the debugger/injection playback mode.

### Settings and sign-in

The two playback modes use separate browser storage. Opening FunTube before restoring
`127.0.0.1` can therefore make your saved settings and sign-in appear missing.

**Overwrite existing version** attempts an in-place update, but does not guarantee
that settings and sign-in data will survive every update.

## Chosen playback mode

Keep Developer Mode **on**, with its **Host PC IP set to `127.0.0.1`**. This selects upstream
TizenTube Old's debugger/injection mode: it opens `https://youtube.com/tv` and injects the TizenTube
script. This setting is on the TV; the FunTube package does not force or change it.

If Apps2Samsung cannot connect or install with this setting, temporarily set the Developer Mode
Host PC IP to your Windows PC's current LAN address and restart the TV as required. After installing,
restore **`127.0.0.1`** and fully restart the TV **before launching FunTube**.

With a non-loopback Host PC IP, the upstream version instead uses the local proxy page
`http://localhost:8100/tv`. Here, `localhost` still means the TV itself; it is not the PC's address.
The Host PC IP setting selects the playback method rather than the proxy server's address.

The proxy page and `https://youtube.com/tv` have separate browser storage and cookie contexts.
Switching modes can therefore look like losing settings or being signed out; it does not by itself
prove the previous data was deleted. Keep the selected mode consistent after signing in and configuring
FunTube.

## How updates work

The workflow checks the latest stable [upstream release](https://github.com/reisxd/TizenTube/releases)
once daily at **15:00 UTC** when enabled. It downloads **TizenTubeOld.wgt**, customizes the icon,
displayed name and app identifiers, removes upstream signatures, and publishes a FunTube WGT.
Historical releases through v2.0.1 can use the original `TizenTube.wgt` filename.
Cobalt packages are not selected. If the expected asset or package structure changes, packaging
stops for review rather than choosing another variant.

The workflow checks **releases, not commits**. It does not merge upstream branches or build the app
from this fork's source. Commits appear in FunTube only when included in the selected upstream
release package. If several stable releases arrive between daily checks, only the latest is selected;
an earlier tag can be processed manually.

App versions match upstream exactly. The internal package ID stays **FunTube001**, including the
app and service prefixes, so future packages keep the same installation identity. Release tags use
`funtube/vX.Y.Z`; this does not change the TV's version number.

## Notifications

On this repository, choose **Watch → Custom → Releases**, and enable **Email** for Watching in
[GitHub notification settings](https://github.com/settings/notifications).
Release notifications announce an optional update and contain the WGT link, installation instructions
and upstream release notes.
Those upstream notes may describe changes to other variants as well as Old.
Also enable GitHub Actions failure emails so a failed check or build is visible.

## Maintaining this fork

Open **Actions → Package FunTube from upstream release → Run workflow**.

- Use `latest` or a specific upstream tag, such as `v2.1.1`.
- Leave **Publish a release** unchecked to generate a preview in the run's **Artifacts** section.
- Install and test a preview before adopting a new packaging recipe.
- Check **Publish a release** to publish after package verification.

To enable daily automatic publishing, create the repository variable **FUNTUBE_AUTO_RELEASE** with
value **true** under **Settings → Secrets and variables → Actions → Variables**.
Set it to **false** to pause automatic publishing while keeping manual previews available.
No personal access token or signing certificate is stored in this repository.

GitHub may delay scheduled runs and disables scheduled workflows in public repositories after
60 days without repository activity. If checks stop, open this workflow in Actions and choose
**Enable workflow**, then run it manually. Watching upstream releases separately is a useful backup.

## Files and verification

- `standalone/icon.png`: the single 512 × 512 FunTube icon.
- `build_funtube.py`: release download, customization, verification and publishing.
- `.github/workflows/build-release.yaml`: manual and daily triggers.
- Release assets `provenance.json` and `SHA256SUMS.txt`: upstream asset, versions and file hashes.

All retained package files except `config.xml`, `icon.png` and the loading-screen name in
`index.html` are preserved byte for byte. Frontend JavaScript is checked separately and remains
unchanged. Automatic verification checks package contents; it cannot test playback on a TV.

Upstream TizenTube and its contributors retain credit for the application. See the upstream
source and license linked from each FunTube release.
