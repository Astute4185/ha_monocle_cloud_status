# Intelli companion compatibility contract

`ha_monocle_cloud_status_intelli` is private and needs a vendor Basic Authorization
credential, so the public project must not require that repository or credential to test.

The supported parent/companion contract is intentionally limited to
`custom_components.ha_monocle_cloud_status.extension`:

- `get_parent_coordinator(hass, entry_id)` resolves the configured parent through
  `ConfigEntry.runtime_data`.
- `get_extension_state(coordinator)` exposes `connected`, `actor_id`, and `location_id`.
- The parent coordinator exposes `location_id` for the shared device-registry identity.
- Companion runtime code consumes `MonocleExtensionState` instead of reaching into the parent
  client state directly.

`tests/test_intelli_contract.py` locks this surface. Any parent refactor that changes these
requirements must update the companion integration and this contract in the same change.
No vendor password or live Intelli endpoint is used by CI.
