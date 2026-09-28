# Encoded response capture, 2026-09-27

Before this revision, `Transport._exchange` read `httpx.Response.iter_bytes()`
and named its SHA-256 `wire_sha256`. HTTPX transparently decompresses that
iterator. A gzip response therefore made the field hash decoded JSON, not the
encoded response entity. The same digest name could mean different bytes
depending on the provider's `Content-Encoding`, weakening response provenance.

The transport requests `Accept-Encoding: identity`, then reads `iter_raw()`
for the encoded HTTP entity and records its `wire_sha256` and `wire_bytes`.
It accepts identity, gzip and deflate responses. Gzip and deflate use bounded
zlib decompression with end-of-stream and trailing-data checks; other
content encodings are ambiguous deliveries. The transport records
`decoded_body_sha256` and `response_bytes`, then parses the decoded UTF-8
JSON. Both encoded and decoded sizes are bounded separately by the frozen
response limit; a small compressed body cannot make the transport allocate
an unbounded decoded chunk. `response_capture_version: encoded_entity_v2`
identifies this behavior.
The captured entity excludes TLS records and HTTP transfer framing, so the
`wire_sha256` name is historical shorthand, not a packet-capture hash.

An injected client may supply an already consumed and decoded `httpx.Response`.
In that case the encoded entity cannot be recovered. The transport marks
`preconsumed_decoded_v1`, leaves the wire hash absent and wire length unknown,
and still bounds, hashes, redacts and parses the decoded content. A consumed
response without cached decoded content is ambiguous. The transport never
substitutes the decoded digest for a claimed encoded digest. Provider responses
with malformed or truncated compression or either size-limit violation remain
ambiguous deliveries and are not automatically retried. Already-decoded content
has already been allocated by the injected client before GrayBench receives it;
the transport can reject an over-limit value but cannot undo that allocation.

The focused tests cover a gzip success with unequal encoded and decoded
digests, a small gzip entity exceeding the decoded size limit, malformed and
truncated gzip, wrapped and raw deflate, unsupported encoding, and preconsumed
fixtures. Existing credential-redaction, provider,
discovery, campaign and ledger tests remain part of regression verification.
These are local HTTPX fixtures, not provider attestation or model generations.

Historical source-frozen ledgers retain their original evidence. In particular,
an older `wire_sha256` may describe decoded bytes for a compressed response;
this change must not relabel it retroactively. New hashes alone cannot prove
that a remote provider received a request or identify its model weights.
