# Security Considerations

## Overview

This document outlines security measures implemented in the phishing detection pipeline and additional considerations for production deployment.

## PII Redaction

### Automatic Redaction

The system automatically redacts personally identifiable information:

- **Email addresses**: Replaced with `[EMAIL_REDACTED]`
- **Phone numbers**: Replaced with `[PHONE_REDACTED]`
- **IP addresses**: Optionally masked or hashed
- **Credit card numbers**: Detected and redacted
- **Social security numbers**: Pattern-based removal

### Implementation

```python
# agent/utils.py implements redaction functions
def redact_pii(text):
    # Email pattern
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 
                  '[EMAIL_REDACTED]', text)
    # Phone pattern
    text = re.sub(r'\b\d{3}-\d{3}-\d{4}\b|\b\(\d{3}\)\s*\d{3}-\d{4}\b', 
                  '[PHONE_REDACTED]', text)
    return text
```

## Secret Management

### Environment Variables

All sensitive configuration is stored in environment variables:

- `OPENAI_API_KEY`: OpenAI API authentication
- `IMAP_PASS`: Email account passwords
- `SLACK_WEBHOOK`: Webhook URLs for notifications
- `ES_PASS`: Elasticsearch credentials

### Docker Secrets

For production deployment, consider using Docker secrets:

```yaml
secrets:
  openai_key:
    external: true
  imap_password:
    external: true
```

### Key Rotation

Regular rotation of:
- OpenAI API keys (monthly)
- Email account passwords (quarterly)
- Webhook URLs (as needed)
- Elasticsearch passwords (quarterly)

## LLM Data Minimization

### Input Sanitization

Before sending to OpenAI:

1. **Content Truncation**: Email body limited to 2000 characters
2. **Header Filtering**: Only essential headers (From, To, Subject)
3. **URL Sanitization**: URLs are extracted but not sent to LLM
4. **Attachment Removal**: No file attachments processed

### Data Retention

- **API Logs**: OpenAI may retain data for 30 days
- **Local Cache**: SHA256 hashes only, no raw content
- **Elasticsearch**: Configurable retention via ILM policy

### Compliance

- **GDPR**: Automatic PII redaction and data retention policies
- **SOC 2**: Audit logs and access controls
- **HIPAA**: Additional encryption for healthcare environments

## Network Security

### Container Communication

- Internal Docker network isolation
- No external ports except UI interfaces
- Service mesh with TLS (production recommendation)

### API Security

```python
# Rate limiting implemented
@limiter.limit("10 per minute")
def score_email():
    pass

# Input validation
def validate_email_input(data):
    if len(data.get('body', '')) > 10000:
        raise ValueError("Body too large")
    return sanitize_input(data)
```

### Elasticsearch Security

Production recommendations:

```yaml
# docker-compose.yml
elasticsearch:
  environment:
    - xpack.security.enabled=true
    - xpack.security.transport.ssl.enabled=true
    - xpack.license.self_generated.type=basic
```

## Audit and Monitoring

### Security Events

Logged security events:
- Failed authentication attempts
- Unusual API usage patterns
- Large data requests
- PII detection triggers

### Metrics Collection

```python
# Security metrics
security_events = Counter('security_events_total', 
                         'Security events', ['event_type'])
pii_redactions = Counter('pii_redactions_total', 
                        'PII redactions', ['type'])
```

## Incident Response

### Data Breach Response

1. **Immediate**: Stop all processing, isolate systems
2. **Assessment**: Determine scope of potential exposure
3. **Notification**: Follow regulatory requirements
4. **Remediation**: Patch vulnerabilities, rotate secrets

### Monitoring Alerts

ElastAlert rules for security events:
- Multiple failed logins
- Unusual API call patterns
- Large data exports
- Configuration changes

## Production Hardening

### Container Security

```dockerfile
# Use non-root user
USER 1001:1001

# Read-only filesystem
RUN --mount=type=tmpfs,target=/tmp

# Minimal base image
FROM python:3.11-slim
```

### Resource Limits

```yaml
deploy:
  resources:
    limits:
      memory: 512M
      cpus: '0.5'
    reservations:
      memory: 256M
      cpus: '0.25'
```

### Health Checks

Comprehensive health monitoring:
- Service availability
- ML model integrity
- Elasticsearch cluster health
- External API connectivity

## Compliance Checklist

### Data Protection

- [ ] PII redaction implemented and tested
- [ ] Data retention policies configured
- [ ] Encryption at rest and in transit
- [ ] Access logging enabled

### Access Control

- [ ] Role-based access to Kibana
- [ ] API authentication configured
- [ ] Service account permissions minimized
- [ ] Regular access reviews

### Monitoring

- [ ] Security event alerting
- [ ] Performance monitoring
- [ ] Error rate tracking
- [ ] Capacity planning metrics

## Regular Security Tasks

### Weekly
- Review security alerts
- Check failed login attempts
- Monitor API usage patterns

### Monthly
- Rotate API keys
- Review access logs
- Update security patches
- Test incident response procedures

### Quarterly
- Security assessment
- Penetration testing
- Compliance audit
- Documentation updates

## Contact

For security issues or questions:
- Security Team: security@company.com
- Incident Response: incidents@company.com
- Emergency: +1-XXX-XXX-XXXX
