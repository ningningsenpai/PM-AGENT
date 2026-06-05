import { v4 as uuidv4 } from 'uuid'

export function createTraceId() {
  return uuidv4().replaceAll('-', '')
}

export function createIdempotencyKey() {
  return uuidv4()
}
