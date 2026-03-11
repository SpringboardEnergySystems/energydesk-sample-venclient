#!/bin/sh
set -e

echo "Waiting for NATS..."
until nc -z nats 4222 >/dev/null 2>&1; do
  sleep 1
done
sleep 1

echo "Creating streams (idempotent)..."
nats --server "$NATS_URL" stream add --config /streams/cmd-stream.json --if-not-exists
nats --server "$NATS_URL" stream add --config /streams/evt-stream.json --if-not-exists

echo "Creating consumer for influx sink (idempotent)..."
nats --server "$NATS_URL" consumer add EVT \
  --config /streams/influx-sink-consumer.json \
  --if-not-exists

echo "Creating consumer for modbus workers (idempotent)..."
nats --server "$NATS_URL" consumer add CMD \
  --config /streams/modus-workers-consumer.json \
  --if-not-exists

echo "NATS init done."
