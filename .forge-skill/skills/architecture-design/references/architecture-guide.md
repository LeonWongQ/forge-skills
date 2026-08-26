# Architecture Design Guide

## System and Component Design

Define bounded responsibilities and ownership before choosing process boundaries. A service boundary should justify independent lifecycle, scaling, security, data ownership, or team ownership; otherwise prefer a module. Trace critical paths and failure propagation. Make consistency, availability, recovery, and observability explicit.

## API and Integration Design

Specify request/response or event schemas, validation, errors, pagination, authentication, authorization, idempotency, versioning, timeout, retry, and rate limits. For asynchronous delivery, define ordering scope, duplicate handling, poison messages, replay, schema evolution, and reconciliation.

## Data and Technology Decisions

State ownership and consistency before storage technology. Evaluate technology against required semantics, team capability, operational burden, ecosystem maturity, lock-in, and migration cost. Avoid introducing distributed coordination for speculative scale.

## Evaluation

Use scenarios to test the design: dependency outage, partial deployment, duplicate request/event, load spike, data corruption, credential compromise, and rollback. Tie each material risk to a mitigation and observable validation signal.
