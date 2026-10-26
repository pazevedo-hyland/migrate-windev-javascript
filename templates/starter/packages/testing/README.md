# Workflow checks

`@windev-migration/testing` provides explicit Playwright helpers for persisted create/reopen,
edit/reopen, cancel, rejected save, search/selection and delete cancellation/confirmation.

Supply a real `Page`, a UI driver and an **independent** `store.read()` oracle. Rows use unique
string keys and consumer-defined `values`. Expected stored values and form drafts are explicit;
the helpers apply no trimming, NULL conversion, money rounding or business normalization.
Create discovers and returns one new database key when no key is supplied. Successful saves
reload the actual page, reopen the record and check its new model. Every store comparison
includes unaffected records and compares sets by key.

Include stored/hidden fields whose preservation matters in `values`; never derive the oracle from
browser state or return the expected fixtures. Define search scope explicitly (filtering, seek-only
lists or rendered virtual rows) and supply that scope's expected keys and selection value.

Driver actions must await the completed response and settled UI (saved editor closed, or rejection
displayed with the editor usable), so reload cannot hide a frontend failure. `assertRejected()` must
await the actual rejected response/dialog path. Confirmation callbacks
must await the real open/closed state. `stableForMs` (default 100ms) samples unchanged storage
after rejected, cancelled or read-only actions and latches observed failures. This is an explicit
bounded check; it does not claim that an arbitrary future write is impossible. `timeoutMs`
(default 5000ms) bounds eventual successful writes/search results.

These helpers add assertions to application tests. They do not generate workflows or promote
parity. Unit tests exercise helper failures with a fake reload and synthetic drivers; real
application browser/database paths must supply their own executed evidence.
