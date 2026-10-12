# Data model

- **Config entry data**: Existing `name`, `stop_id`; no station-member snapshot.
- **Options**: Existing `lines`, `destination`, `walking_minutes`, plus
  `transport_types`, a nonempty selection of `bus`, `tram`, `metro`. Missing key
  means all modes for legacy entries. Empty form input is rejected. No selector
  claims an unobserved mode is served locally.
- **Identity**: Legacy three-field canonical identity is retained for all modes.
  Restricted mode sets append a canonical sorted discriminator. Name/walking time
  remain presentation preferences, not uniqueness criteria.
- **Reservation**: Existing replacement-aware token/target/entry ownership.
  Every claimant must independently back replacement credit; cancellation cannot
  lend a future free slot to another add.
- **Validation work**: Shared background task with waiter accounting. Pending
  stop counts protect remaining waiters on cancellation. After dispatch, a new
  target joins the next eligible batch. Real request errors return rather than loop.
- **Waiting state**: `lookup`, `budget_wait`, `server_pause`, with the actual
  computed eligible wall-clock instant derived from the monotonic deadlines.
- **Departure cache**: Original source timestamp and dual 29-minute expiry;
  transport preferences never refresh timestamps or fetch.
- **Status sensor/device**: Existing unique ID and `departure_board` object-ID
  suffix. Clear translated feed-status name and static timing-point device model.
- **Station model**: Deferred to #5. No new member lists, IDs or coverage claims.
