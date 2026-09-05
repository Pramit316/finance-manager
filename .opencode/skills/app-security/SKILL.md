---
name: app-security
description: Review or implement authentication, secrets handling, financial-data security and privacy controls.
---

# Application Security

This application contains sensitive financial information.

## Never Store

- internet banking passwords
- eSewa passwords
- PIN numbers
- CVV numbers

## Secrets

Secrets belong in environment variables.

Never commit:

.env

API keys

database passwords

authentication secrets

## Database

Use parameterised queries or ORM functionality.

Never construct SQL using raw user input.

## File Uploads

Validate:

- file type
- file size
- CSV structure
- encoding

Uploaded files must never be executable.

## Logging

Never log:

- passwords
- API keys
- authentication tokens
- complete sensitive financial payloads

## Principle

Use least privilege wherever possible.