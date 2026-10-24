import assert from 'node:assert/strict'
import test from 'node:test'

import { dateText } from '../src/date.ts'

test('formats UTC timestamps in IST', () => {
  const formatted = dateText('2026-10-24T10:00:00Z')

  assert.match(formatted, /03:30:00/)
  assert.match(formatted, /IST/)
})

test('does not shift equivalent offset timestamps a second time', () => {
  assert.equal(
    dateText('2026-10-24T10:00:00Z'),
    dateText('2026-10-24T15:30:00+05:30'),
  )
})
