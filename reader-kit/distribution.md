# Bibliography reader kit — 0.2 preview

Use four public research references to write a bounded, checkable decision.
Open `index.html`, compare the source cards, and download your own draft as
Markdown or editable JSON. The plain `guide.md` and `sources.bib` also work
without JavaScript. Import BibTeX into a reference manager as a new collection;
check the work and version before citing it.

Notes stay in tab memory until downloaded. Save before closing or refreshing.
There is no account, autosave, telemetry, browser storage or submission service.
Import refuses to overwrite nonempty notes. A local decision file belongs to
its reader; exporting it is not consent to share it.

Explore the broader citation inventory in the
[public bibliography](https://github.com/hummbl-io/hummbl-bibliography-public).
This is a small reading path, not search over the full bibliography. The source
cards distinguish findings, limitations and outstanding review holds. Applying
a study to your own work requires an argument about context. The Walton source
remains held pending substantive erratum review. No human learning result or
admitted improvement policy is claimed.

## Check your copy

With Python 3.11 or newer, run from the extracted directory:

```text
python -B verify.py
```

The verifier checks the exact ten-file inventory, release file sizes/hashes,
the three build output hashes and consistency of source provenance metadata.
Keep your saved notes elsewhere; extra files cause this inventory check to fail.
It does not retrieve or check the unbundled repository source bytes. Release
file rows and build output rows use fixed filename order; source provenance
retains its authored list order. Changing either requires matching manifests.

If you have a release-manifest hash from an independently trusted channel:

```text
python -B verify.py --expected-release-sha256 HASH_FROM_TRUSTED_CHANNEL
```

Hashes detect changed bytes against the supplied reference. They do not
establish who supplied that reference or make the included verifier trusted.
Check publisher provenance before running downloaded code. They also do not
prove scientific truth, source applicability or reader learning.

The preview browser walkthrough used synthetic notes over a localhost server.
To use an extracted release, run this from its directory:

```text
python -m http.server 8765 --bind 127.0.0.1
```

Open `http://127.0.0.1:8765/` and stop the server with Ctrl+C. This localhost
route was exercised for the preview. Direct `file://` opening is optional and
unverified. No-JavaScript
behavior has source review only. Use the local server only while working with the kit.

## Contents and reuse

`MANIFEST.json` describes the three reading outputs and their source provenance.
`RELEASE.json` checks those four files, this README, the verifier and three
license files. Neither manifest is an authenticity signature. Source paths in
the build manifest are repository references; they are not bundled private data
and are not needed to use the kit.

Original authored code and documentation retain the repository's
`MIT OR Apache-2.0` license choice; see the included license files. The archive
does not contain paper text, PDFs, private corpus records or reader notes.
These licenses do not grant rights in the linked third-party works.

Before collecting observations, arrange named evaluation and data-custody
roles, specific consent, withdrawal/restore checks and independently authored,
frozen tasks. This kit has no participant collection system. Feedback or
corrections may challenge HUMMBL's interpretation without endorsing it.
