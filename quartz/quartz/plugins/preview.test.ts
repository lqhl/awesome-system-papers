import assert from "node:assert/strict"
import test from "node:test"
import { devWebsocketExpression } from "./preview"

test("local preview hot reload follows the page hostname", () => {
  const expression = devWebsocketExpression(undefined, 8788)

  assert.match(expression, /window\.location\.hostname/)
  assert.match(expression, /:8788/)
})

test("an explicit remote development host remains HTTPS", () => {
  assert.equal(devWebsocketExpression("notes.example.com", 3001), '"wss://notes.example.com:3001"')
})
